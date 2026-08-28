"""Play-along pages (play-along spec §5–§6): build-time embed + two renderers.
No scoring here — the client scores against the embedded lists (§5.3)."""
from datetime import date
from pathlib import Path

from jinja2 import Environment
from markupsafe import Markup

from smw.config.groups import Group
from smw.config.play import PlayConfig
from smw.config.season import Season
from smw.model.project import MovieCatalog
from smw.render.page import STATIC, base_context, write_page
from smw.render.views import projected_ranks

# The play pages belong to no roster (§4.1): this stand-in only satisfies
# base_context, whose group-specific keys play_context drops.
_NO_GROUP = Group(group_id="play", display_name="Play Along", players={})
# What the play pages reuse from the friends-site context; everything else there
# (nav, year/group pickers, forecast note) is friends-only.
_SHARED_KEYS = ("css", "theme_js", "year", "window_label", "refreshed")


def season_state(final: bool, forecastable: bool) -> str:
    """Base §10.1: Final wins, then the forecast gate decides Early vs Live."""
    if final:
        return "final"
    return "live" if forecastable else "early"


def build_play_data(season: Season, catalog: MovieCatalog, actual_top: list[str],
                    forecastable: bool, reason: str | None, today: date,
                    cfg: PlayConfig, *, season_over: bool) -> dict:
    """What the play pages embed (§6.4). `season_over` is the build's Final flag
    (base §10.1), computed once in build.py and passed in."""
    state = season_state(season_over, forecastable)
    ranks = projected_ranks(catalog) if state != "early" else {}
    medians = {p.title: p.median for p in catalog.projections}
    projected_top = [t for t, _ in sorted(ranks.items(), key=lambda kv: kv[1])][:10]
    films = sorted(catalog.films, key=lambda f: (f.release_date, f.title))
    return {
        "year": season.year,
        "state": state,
        "reason": reason,
        "build_date": today.isoformat(),
        "api_base_url": cfg.api_base_url,
        "default_group": list(cfg.default_group),
        "catalog": [
            {"title": f.title,
             "release_date": f.release_date.isoformat(),
             "release_label": f.release_date.strftime("%b %-d"),
             "projected_rank": ranks.get(f.title),
             "projected_median": medians[f.title],
             "status": f.status}
            for f in films],
        "actual_top": list(actual_top),
        "projected_top": projected_top,
    }


def play_context(season: Season, today: date, rules_href: str) -> dict:
    ctx = base_context(season, _NO_GROUP, "rules", today)
    return {k: ctx[k] for k in _SHARED_KEYS} | {
        "play_css": Markup((STATIC / "play.css").read_text()),
        "rules_href": rules_href,
    }


def render_play(env: Environment, out_dir: Path, ctx: dict, data: dict) -> None:
    write_page(env, "play.html.j2", out_dir, "play.html", {
        **ctx, "active": "play", "title": "Play Along", "data": data,
        "scoring_js": Markup((STATIC / "scoring.js").read_text()),
        "play_js": Markup((STATIC / "play.js").read_text()),
    })


def render_join(env: Environment, out_dir: Path, ctx: dict, data: dict,
                season_over: bool) -> None:
    write_page(env, "join.html.j2", out_dir, "join.html", {
        **ctx, "active": "join", "title": "Join", "data": data,
        "season_over": season_over,
        "join_js": Markup((STATIC / "join.js").read_text()),
    })
