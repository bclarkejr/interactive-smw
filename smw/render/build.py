"""Pipeline glue: the only module that knows the order of operations (Appendix B)."""
import json
import math
from datetime import date, timedelta
from pathlib import Path

from smw.catalog.normalize import (apply_chart_aliases, build_films, canonical,
                                   canonical_group, load_overrides, load_preopening)
from smw.catalog.resolve import load_history, resolve_grosses, with_snapshot
from smw.config.groups import Group
from smw.config.season import Season, load_season_dir
from smw.ingest.boxoffice import chart_floor, fetch_chart, parse_chart, windowed
from smw.model.project import MovieCatalog, build_catalog
from smw.model.simulate import MIN_FILMS_FOR_TOP_TEN, SimResult, simulate
from smw.render.chart import build_history_data
from smw.render.page import (Site, base_context, build_scenarios_view, build_whatif_data,
                             make_env, render_history, render_leaderboard,
                             render_redirect, render_rules, render_scenarios,
                             render_whatif)
from smw.render.views import build_leaderboard_view
from smw.score.rules import score_player

fetch = fetch_chart  # network seam; tests monkeypatch this


def build_data_json(season, group, catalog, sim, current_points,
                    non_zero, reason, today) -> dict:
    players = sorted(group.players)
    if sim is None:
        null_map = {u: None for u in players}
        forecast = {
            "win_prob": dict(null_map), "tie_prob": dict(null_map),
            "median_final_pts": dict(null_map), "p10_final_pts": dict(null_map),
            "p90_final_pts": dict(null_map), "winning_scenarios": dict(null_map),
        }
    else:
        forecast = {
            "win_prob": sim.win_prob, "tie_prob": sim.tie_prob,
            "median_final_pts": sim.median_pts, "p10_final_pts": sim.p10_pts,
            "p90_final_pts": sim.p90_pts,
            "winning_scenarios": {
                u: None if sc is None else {
                    "films": sc.films, "grid": sc.grid, "totals": sc.totals,
                    "win_pct": sc.win_pct, "margin": sc.margin}
                for u, sc in sim.scenarios.items()},
        }
    out = {
        "captured_at": today.isoformat(),
        "current_points": current_points,
        "forecast_available": sim is not None,
        "non_zero_projections": non_zero,
        "projections": [
            {"movie_title": p.title, "median_in_window_gross": p.median,
             "sigma": p.sigma, "floor": p.floor}
            for p in catalog.projections],
        **forecast,
    }
    if sim is None:
        out["forecast_unavailable_reason"] = reason
    return out


def append_box_office_history(path: Path, grosses: dict[str, float], today: date):
    with open(path, "a") as f:
        for title in sorted(grosses):
            if grosses[title] > 0:
                f.write(json.dumps({"movie": title, "date": today.isoformat(),
                                    "cumulative_gross": grosses[title]}) + "\n")


def append_forecast_history(path: Path, sim: SimResult, today: date):
    with open(path, "a") as f:
        for u in sorted(sim.win_prob):
            f.write(json.dumps({
                "date": today.isoformat(), "player": u,
                "win_prob": sim.win_prob[u],
                "median_final_pts": sim.median_pts[u],
                "p10": sim.p10_pts[u], "p90": sim.p90_pts[u]}) + "\n")


def _load_forecast_rows(path: Path) -> list[dict]:
    """Schema check at the load boundary (§5.6): date, player, win_prob in [0, 1],
    finite point values."""
    if not path.exists():
        return []
    rows = []
    for n, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}:{n}: not valid JSON ({e.msg})") from None
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{n}: each line must be a JSON object")
        try:
            date.fromisoformat(row.get("date"))
        except (TypeError, ValueError):
            raise ValueError(f"{path}:{n}: 'date' must be YYYY-MM-DD") from None
        if not isinstance(row.get("player"), str) or not row["player"].strip():
            raise ValueError(f"{path}:{n}: 'player' must be a non-empty string")
        for key in ("win_prob", "median_final_pts", "p10", "p90"):
            v = row.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"{path}:{n}: '{key}' must be a finite number")
        if not 0.0 <= row["win_prob"] <= 1.0:
            raise ValueError(f"{path}:{n}: 'win_prob' must be within [0, 1]")
        rows.append(row)
    return rows


def run_build(data_dir: Path, out_dir: Path, today: date, local: bool) -> None:
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    seasons_root = data_dir / "seasons"
    season_dirs = sorted(p for p in seasons_root.glob("*") if p.is_dir()) \
        if seasons_root.is_dir() else []
    if not season_dirs:
        raise ValueError(f"{seasons_root}: no seasons found (an empty site is an error)")
    loaded = [load_season_dir(p) for p in season_dirs]  # dir name == year, so sorted by year
    env = make_env()
    years = tuple((s.year, s.default_group) for s, _ in sorted(loaded, key=lambda x: -x[0].year))
    for season_dir, (season, groups) in zip(season_dirs, loaded):
        _build_season(env, season_dir, out_dir / str(season.year), season, groups,
                      years, today, local)
    newest, _ = loaded[-1]
    render_redirect(env, out_dir, f"{newest.year}/{newest.default_group}/index.html")


def _build_season(env, season_dir: Path, out_dir: Path, season: Season,
                  groups: list[Group], years: tuple[tuple[int, str], ...],
                  today: date, local: bool) -> None:
    overrides = load_overrides(season_dir / "movies_overrides.yaml")
    groups = [canonical_group(g, overrides) for g in groups]  # §6.5 point 2
    preopening = load_preopening(season_dir / "preopening_projections.yaml")
    history_path = season_dir / "box_office_history.jsonl"
    if not history_path.exists():
        print(f"warning: {season.year}: no box-office history file yet (normal on the first run)")
    history = load_history(history_path)

    fetch_window = season.window_start <= today - timedelta(days=1) <= season.window_end
    # Persist from opening day through the final eligible run (window_end + 1); the chart
    # fetch keeps its yesterday-based boundary (§6.1). A frozen or not-yet-open season
    # renders but persists nothing (§2.2).
    persist = not local and (
        season.window_start <= today <= season.window_end + timedelta(days=1))
    if fetch_window:
        raw = apply_chart_aliases(parse_chart(fetch(season.year), season.year), overrides)
        chart_rows = windowed(raw, season)  # Guards A and B — before the floor, so an
        floor = chart_floor(raw)            # empty parse fails with Guard A, not min()
    else:
        # §6.1: chart frozen from window_end + 2 — MUST NOT be read at all. Before the
        # window opens no in-window row can exist either (§10.1 pre-season is just
        # Early/Live on analyst numbers), so skip the fetch instead of tripping Guard B.
        chart_rows, floor = [], 0.0

    grosses, carried, chart_usable = resolve_grosses(
        season, history, chart_rows, floor, today)

    films = build_films(season, groups, chart_rows, grosses, carried,
                        overrides, preopening, today)
    picked = {canonical(t, overrides)
              for g in groups for p in g.players.values()
              for t in p.ranked + p.dark_horses}
    # Today's snapshot joins the series in memory (persisted only for production runs).
    catalog = build_catalog(season, films, with_snapshot(history, grosses, today),
                            picked, overrides, today)
    for w in catalog.warnings:
        print(f"warning: {w}")

    gross_ranked = sorted(((g, t) for t, g in grosses.items() if g > 0),
                          key=lambda x: (-x[0], x[1]))
    actual_top = [t for _, t in gross_ranked[:10]]

    non_zero = sum(1 for p in catalog.projections if p.median > 0)
    # §10.1: Final first, then the projection count decides Early vs Live.
    # The structural floor (§9.5) also degrades here: a site build must not crash
    # merely because the season is young.
    final = today > season.window_end + timedelta(days=1)
    forecastable = non_zero >= MIN_FILMS_FOR_TOP_TEN and (
        final or non_zero >= season.min_projections_for_forecast)
    reason = None
    if not forecastable:
        reason = (f"only {non_zero} films have non-zero projections "
                  f"({MIN_FILMS_FOR_TOP_TEN if final else season.min_projections_for_forecast}"
                  " required for a meaningful top-ten ranking)")

    site = Site(
        years=years,
        groups=tuple((g.group_id, g.display_name)
                     for g in sorted(groups, key=lambda g: (g.display_name, g.group_id))),
        forecast_note=(f"Forecast: {season.monte_carlo_trials:,} seeded Monte Carlo seasons "
                       f"over {non_zero} projected films." if forecastable
                       else f"Forecast: unavailable — {reason}."),
    )

    # Date axis = every production refresh (box-office history), so a degraded
    # refresh shows as a gap in each line rather than vanishing (§12.4).
    refresh_dates = {d.isoformat() for obs in history.values() for d, _ in obs}
    if persist:
        refresh_dates.add(today.isoformat())  # this refresh persists after rendering

    for group in groups:
        group_out = out_dir / group.group_id
        sim = simulate(season, group, catalog) if forecastable else None
        current_points = {u: score_player(group.players[u], actual_top)
                          for u in group.players}
        view = build_leaderboard_view(season, group, catalog, sim, current_points,
                                      actual_top, reason, today)
        ctx = lambda page: base_context(season, group, page, today, site)  # noqa: E731
        render_leaderboard(env, group_out, ctx("leaderboard"), view)
        render_whatif(env, group_out, ctx("whatif"),
                      build_whatif_data(season, group, catalog, sim) if sim else None,
                      reason)
        render_scenarios(env, group_out, ctx("scenarios"),
                         build_scenarios_view(group, sim) if sim else None, reason)
        forecast_path = season_dir / "forecast_history" / f"{group.group_id}.jsonl"
        if persist and sim is not None:
            # Appended before the history page renders so the page includes this refresh.
            forecast_path.parent.mkdir(exist_ok=True)
            append_forecast_history(forecast_path, sim, today)
        render_history(env, group_out, ctx("history"),
                       build_history_data(_load_forecast_rows(forecast_path), refresh_dates))
        render_rules(env, group_out, ctx("rules"))
        (group_out / "data.json").write_text(json.dumps(
            build_data_json(season, group, catalog, sim, current_points,
                            non_zero, reason, today),
            indent=2, sort_keys=True))

    if persist:
        # Roster-independent: appended once per season, never once per group.
        append_box_office_history(history_path, grosses, today)
