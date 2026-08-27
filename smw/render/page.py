"""Jinja environment, shared context, page writer (spec §11.4, §13.1–13.2).
The render layer MUST NOT sort, rank, or compute — view models arrive finished."""
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from smw.config.groups import Group
from smw.config.season import Season
from smw.model.project import MovieCatalog
from smw.model.simulate import SimResult
from smw.render.chart import render_chart_svg
from smw.render.views import projected_ranks
from smw.score.rules import score_player

TEMPLATES = Path(__file__).parent / "templates"
STATIC = Path(__file__).parent / "static"

NAV = [
    ("index.html", "🏆 Leaderboard", "leaderboard"),
    ("whatif.html", "🎬 What If?", "whatif"),
    ("scenarios.html", "🔮 Winning Scenarios", "scenarios"),
    ("history.html", "📈 Odds Over Time", "history"),
]
PAGES = {  # active key → (filename, page title)
    "leaderboard": ("index.html", "Leaderboard"),
    "whatif": ("whatif.html", "What If?"),
    "scenarios": ("scenarios.html", "Winning Scenarios"),
    "history": ("history.html", "Odds Over Time"),
    "rules": ("rules.html", "Scoring rules"),
}


def json_embed(obj) -> Markup:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return Markup(text.replace("<", "\\u003c"))


def fmt_money(x: float) -> str:
    x = float(x)
    if x >= 1e9:
        return f"${x / 1e9:.1f}B"
    if x >= 1e6:
        return f"${x / 1e6:.1f}M"
    if x >= 1e3:
        return f"${x / 1e3:.0f}K"
    return f"${x:.0f}"


def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=True,  # forced unconditionally; titles come from an external site
        keep_trailing_newline=True,
    )
    env.filters["money"] = fmt_money
    env.filters["json_embed"] = json_embed
    return env


@dataclass(frozen=True)
class Site:
    """Cross-season / cross-group facts a page needs for its masthead (spec §4)."""
    years: tuple[tuple[int, str], ...]     # (year, default_group_id), newest first
    groups: tuple[tuple[str, str], ...]    # (group_id, display_name), by display_name
    forecast_note: str


def base_context(season: Season, group: Group, active: str, today: date,
                 site: Site | None = None) -> dict:
    if site is None:  # single-page renders (tests): one year, one group
        site = Site(((season.year, group.group_id),),
                    ((group.group_id, group.display_name),),
                    "Forecast: unavailable — no forecast.")
    filename = PAGES[active][0]
    return {
        # Repo-controlled build assets, inlined verbatim; everything external
        # still flows through autoescape.
        "css": Markup((STATIC / "site.css").read_text()),
        "theme_js": Markup((STATIC / "theme.js").read_text()),
        "nav": NAV,
        "active": active,
        "display_name": group.display_name,
        "year": season.year,
        "window_label": (
            f"{season.window_start.strftime('%b %-d')} – "
            f"{season.window_end.strftime('%b %-d, %Y')}"
        ),
        "window_and": (
            f"{season.window_start.strftime('%b %-d')} and "
            f"{season.window_end.strftime('%b %-d, %Y')}"
        ),
        "refreshed": today.strftime("%b %-d, %Y"),
        "trials": f"{season.monte_carlo_trials:,}",
        "year_options": [
            {"value": f"../../{y}/{g}/index.html", "label": str(y), "selected": y == season.year}
            for y, g in site.years],
        "group_options": [
            {"value": f"../{gid}/{filename}", "label": name, "selected": gid == group.group_id}
            for gid, name in site.groups],
        "forecast_note": site.forecast_note,
    }


def write_page(env: Environment, template_name: str, out_dir: Path,
               filename: str, context: dict) -> None:
    html = env.get_template(template_name).render(**context)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / filename).write_text(html)


def render_redirect(env: Environment, out_dir: Path, target: str) -> None:
    write_page(env, "redirect.html.j2", out_dir, "index.html", {
        "css": Markup((STATIC / "site.css").read_text()),
        "theme_js": Markup((STATIC / "theme.js").read_text()),
        "target": target,
    })


def render_rules(env: Environment, out_dir: Path, ctx: dict) -> None:
    write_page(env, "rules.html.j2", out_dir, "rules.html",
               {**ctx, "title": "Scoring rules"})


def render_leaderboard(env: Environment, out_dir: Path, ctx: dict, view) -> None:
    write_page(env, "index.html.j2", out_dir, "index.html",
               {**ctx, "title": "Leaderboard", "view": view})


def build_whatif_data(season: Season, group: Group,
                      catalog: MovieCatalog, sim: SimResult) -> dict:
    ranks = projected_ranks(catalog)
    films = [t for t, _ in sorted(ranks.items(), key=lambda kv: kv[1])
             ][: season.matrix_rows]
    order = sorted(group.players, key=lambda u: (-sim.median_pts[u], u))
    top10 = films[:10]
    return {
        "films": films,
        "players": [
            {"name": u,
             "ranked": list(group.players[u].ranked),
             "dark": list(group.players[u].dark_horses)}
            for u in order
        ],
        "baseline": {u: score_player(group.players[u], top10) for u in order},
    }


def render_whatif(env: Environment, out_dir: Path, ctx: dict,
                  data: dict | None, reason: str | None) -> None:
    write_page(env, "whatif.html.j2", out_dir, "whatif.html", {
        **ctx, "title": "What If?", "data": data, "reason": reason,
        "scoring_js": Markup((STATIC / "scoring.js").read_text()),
        "whatif_js": Markup((STATIC / "whatif.js").read_text()),
    })


def build_scenarios_view(group: Group, sim: SimResult) -> list[dict]:
    tabs = []
    order = sorted(group.players, key=lambda u: (-sim.win_prob[u], u))
    for u in order:
        sc = sim.scenarios[u]
        entry = {"username": u, "win_pct": round(sim.win_prob[u] * 100, 1),
                 "scenario": None}
        if sc is not None:
            cols = sorted(sc.totals, key=lambda v: (-sc.totals[v], v))
            entry["scenario"] = {
                "caption": (
                    f"Most likely finish in which {u} wins the wager 🏆 — {u} edges "
                    f"the field by just {sc.margin} pt"
                    f"{'s' if sc.margin != 1 else ''}; they win ~{entry['win_pct']}% "
                    "of all sims."),
                "columns": cols,
                "rows": [{"title": t, "cells": [sc.grid[v][i] for v in cols]}
                         for i, t in enumerate(sc.films)],
                "totals": [sc.totals[v] for v in cols],
            }
        tabs.append(entry)
    return tabs


def render_scenarios(env: Environment, out_dir: Path, ctx: dict,
                     tabs: "list[dict] | None", reason: str | None) -> None:
    write_page(env, "scenarios.html.j2", out_dir, "scenarios.html", {
        **ctx, "title": "Winning Scenarios", "tabs": tabs, "reason": reason,
        "scenarios_js": Markup((STATIC / "scenarios.js").read_text()),
    })


def render_history(env: Environment, out_dir: Path, ctx: dict,
                   data: "dict | None") -> None:
    extra: dict = {"title": "Odds Over Time", "data": data}
    if data is not None:
        legend = []
        for s in data["series"]:
            vals = [v for v in s["values"] if v is not None]
            legend.append({"name": s["name"], "color": s["color"],
                           "latest_pct": round(vals[-1] * 100, 1) if vals else 0.0})
        legend.sort(key=lambda e: -e["latest_pct"])
        table_rows = [
            {"date": d,
             "cells": [
                 (round(s["values"][i] * 100, 1) if s["values"][i] is not None else None)
                 for s in data["series"]]}
            for i, d in enumerate(data["dates"])
        ]
        extra.update({
            "svg": Markup(render_chart_svg(data)),
            "legend": legend,
            "table_rows": table_rows,
            "history_js": Markup((STATIC / "history.js").read_text()),
        })
    write_page(env, "history.html.j2", out_dir, "history.html", {**ctx, **extra})
