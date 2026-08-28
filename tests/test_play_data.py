from datetime import date

from smw.config.play import PlayConfig
from smw.render.play import build_play_data, play_context, season_state
from tests.test_views import _catalog

TODAY = date(2026, 8, 15)
CFG = PlayConfig("https://smw-players.example.workers.dev", ("alice", "bob"))


def _actual(cat):
    return [f.title for f in sorted(cat.films, key=lambda f: -f.cumulative_gross)][:10]


def test_season_state():
    assert season_state(final=True, forecastable=True) == "final"
    assert season_state(final=True, forecastable=False) == "final"
    assert season_state(final=False, forecastable=True) == "live"
    assert season_state(final=False, forecastable=False) == "early"


def test_live_shape(season):
    cat = _catalog()
    d = build_play_data(season, cat, _actual(cat), True, None, TODAY, CFG,
                        season_over=False)
    assert d["year"] == 2026 and d["state"] == "live" and d["reason"] is None
    assert d["build_date"] == "2026-08-15"
    assert d["api_base_url"] == CFG.api_base_url
    assert d["default_group"] == ["alice", "bob"]
    assert d["projected_top"] == [f"M{i:02d}" for i in range(1, 11)]
    assert d["actual_top"] == _actual(cat)
    assert len(d["catalog"]) == 18
    row = next(c for c in d["catalog"] if c["title"] == "M01")
    assert row == {"title": "M01", "release_date": "2026-05-01", "release_label": "May 1",
                   "projected_rank": 1, "projected_median": 400e6, "status": "in_theaters"}


def test_season_over_is_final_state(season):
    cat = _catalog()
    d = build_play_data(season, cat, _actual(cat), True, None, TODAY, CFG,
                        season_over=True)
    assert d["state"] == "final"
    assert d["projected_top"] == [f"M{i:02d}" for i in range(1, 11)]


def test_catalog_sorted_by_release_then_title(season):
    cat = _catalog()
    d = build_play_data(season, cat, _actual(cat), True, None, TODAY, CFG,
                        season_over=False)
    keys = [(c["release_date"], c["title"]) for c in d["catalog"]]
    assert keys == sorted(keys)


def test_early_state_has_no_projected_top(season):
    cat = _catalog()
    d = build_play_data(season, cat, _actual(cat), False, "only 3 films", TODAY, CFG,
                        season_over=False)
    assert d["state"] == "early" and d["reason"] == "only 3 films"
    assert d["projected_top"] == []
    assert all(c["projected_rank"] is None for c in d["catalog"])


def test_play_context(season):
    ctx = play_context(season, TODAY, "smw-friends/rules.html")
    assert ctx["year"] == 2026 and ctx["refreshed"] == "Aug 15, 2026"
    assert ctx["rules_href"] == "smw-friends/rules.html"
    assert ctx["window_label"] == "May 1 – Sep 7, 2026"
    assert "css" in ctx and "theme_js" in ctx and "play_css" in ctx


def test_play_context_carries_no_friends_site_keys(season):
    """Spec §4.1: the play pages have their own nav and no year/group pickers."""
    ctx = play_context(season, TODAY, "smw-friends/rules.html")
    for key in ("nav", "year_options", "group_options", "display_name"):
        assert key not in ctx, key
