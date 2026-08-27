"""Jinja environment, shared context, page writer (spec §11.4, §13.1–13.2).
The render layer MUST NOT sort, rank, or compute — view models arrive finished."""
import json
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from smw.config.groups import Group
from smw.config.season import Season
from smw.model.project import MovieCatalog
from smw.model.simulate import SimResult
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


def base_context(season: Season, group: Group, active: str, today: date) -> dict:
    return {
        # Repo-controlled build assets, inlined verbatim; everything external
        # still flows through autoescape.
        "css": Markup((STATIC / "site.css").read_text()),
        "theme_js": Markup((STATIC / "theme.js").read_text()),
        "nav": NAV,
        "active": active,
        "display_name": group.display_name,
        "season_label": f"Summer {season.year}",
        "window_label": (
            f"{season.window_start.strftime('%b %-d')} – "
            f"{season.window_end.strftime('%b %-d, %Y')}"
        ),
        "refreshed": today.isoformat(),
        "wide_shell": False,
    }


def write_page(env: Environment, template_name: str, out_dir: Path,
               filename: str, context: dict) -> None:
    html = env.get_template(template_name).render(**context)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / filename).write_text(html)


def render_rules(env: Environment, out_dir: Path, ctx: dict) -> None:
    write_page(env, "rules.html.j2", out_dir, "rules.html",
               {**ctx, "title": "Scoring rules"})


def render_leaderboard(env: Environment, out_dir: Path, ctx: dict, view) -> None:
    write_page(env, "index.html.j2", out_dir, "index.html",
               {**ctx, "title": "Leaderboard", "wide_shell": True, "view": view})


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
