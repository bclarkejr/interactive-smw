"""Gross resolution: history + live chart merged by max, carry-forward, Guard C (spec §6.1–6.3)."""
import json
import math
from datetime import date, timedelta
from pathlib import Path

from smw.config.season import Season
from smw.ingest.boxoffice import ChartRow


class ResolutionError(RuntimeError):
    pass


def load_history(path: Path) -> dict[str, list[tuple[date, float]]]:
    path = Path(path)
    if not path.exists():
        return {}
    per_date: dict[str, dict[date, float]] = {}
    for n, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        row = _history_row(line, path, n)
        d, gross = row["date"], row["cumulative_gross"]
        by_date = per_date.setdefault(row["movie"], {})
        # §5.5: same-date rows collapse to the max, so a same-day re-run can never
        # inflate a film's snapshot count or skew the observed-decay weight.
        by_date[d] = max(gross, by_date.get(d, 0.0))
    return {
        title: sorted(by_date.items())
        for title, by_date in per_date.items()
    }


def _history_row(line: str, path: Path, n: int) -> dict:
    """Schema check at the load boundary (§5.5): movie str, ISO date, finite gross ≥ 0."""
    try:
        row = json.loads(line)
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}:{n}: not valid JSON ({e.msg})") from None
    if not isinstance(row, dict):
        raise ValueError(f"{path}:{n}: each line must be a JSON object")
    movie = row.get("movie")
    if not isinstance(movie, str) or not movie.strip():
        raise ValueError(f"{path}:{n}: 'movie' must be a non-empty string")
    try:
        d = date.fromisoformat(row.get("date"))
    except (TypeError, ValueError):
        raise ValueError(f"{path}:{n}: 'date' must be YYYY-MM-DD") from None
    gross = row.get("cumulative_gross")
    if isinstance(gross, bool) or not isinstance(gross, (int, float)) \
            or not math.isfinite(gross) or gross < 0:
        raise ValueError(f"{path}:{n}: 'cumulative_gross' must be a finite number >= 0")
    return {"movie": movie, "date": d, "cumulative_gross": float(gross)}


def resolve_grosses(
    season: Season,
    history: dict[str, list[tuple[date, float]]],
    chart_rows: list[ChartRow],
    floor: float,
    today: date,
) -> tuple[dict[str, float], set[str], bool]:
    cutoff = min(today, season.window_end + timedelta(days=1))
    chart_usable = (today - timedelta(days=1)) <= season.window_end

    grosses: dict[str, float] = {}
    for title, observations in history.items():
        in_range = [g for (d, g) in observations if d <= cutoff]
        if in_range:
            grosses[title] = max(in_range)  # highest, not latest

    chart_titles: set[str] = set()
    if chart_usable:
        for row in chart_rows:
            chart_titles.add(row.title)
            grosses[row.title] = max(row.gross, grosses.get(row.title, 0.0))

    carried = {t for t in grosses if t not in chart_titles}

    if chart_usable and chart_rows:  # no chart → nothing to be absent from (Guard A covers empty)
        impossible = sorted(t for t in carried if grosses[t] >= floor)
        if impossible:
            blocks = "\n\n".join(
                f'"<current upstream title for {t!r}>":\n  alias_of: "{t}"'
                for t in impossible
            )
            raise ResolutionError(
                "Guard C: carried-forward film(s) with a gross at or above the chart floor "
                f"(${floor:,.0f}) — a film that large must still be on the chart, so its "
                "absence means the source renamed it. Find the new title on the chart and "
                "add to movies_overrides.yaml:\n\n" + blocks
            )
    return grosses, carried, chart_usable


def with_snapshot(history: dict[str, list[tuple[date, float]]],
                  grosses: dict[str, float], today: date) -> dict[str, list[tuple[date, float]]]:
    """Today's resolved grosses folded into the observation series (same-date max, sorted),
    so the observed-decay blend sees the current refresh, not just persisted ones."""
    # No look-ahead: a back-dated build must not blend grosses observed after `today`.
    past = {t: [(d, g) for d, g in obs if d <= today] for t, obs in history.items()}
    out: dict[str, list[tuple[date, float]]] = {}
    for title, gross in grosses.items():
        if gross <= 0:
            continue
        by_date = dict(past.get(title, []))
        by_date[today] = max(gross, by_date.get(today, 0.0))
        out[title] = sorted(by_date.items())
    for title, obs in past.items():
        if obs:
            out.setdefault(title, obs)
    return out
