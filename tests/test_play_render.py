from datetime import date

from smw.config.play import PlayConfig
from smw.model.project import MovieCatalog
from smw.render.page import make_env
from smw.render.play import build_play_data, play_context, render_play
from tests.conftest import FIXTURES
from tests.test_views import _catalog, _film, _proj

TODAY = date(2026, 8, 15)
CFG = PlayConfig("https://smw-players.example.workers.dev", ("alice",))


def _actual(cat):
    return [f.title for f in sorted(cat.films, key=lambda f: -f.cumulative_gross)][:10]


def _render(tmp_path, season, cat=None, forecastable=True, reason=None, today=TODAY,
            season_over=False):
    cat = cat or _catalog()
    env = make_env()
    data = build_play_data(season, cat, _actual(cat), forecastable, reason, today, CFG,
                           season_over=season_over)
    render_play(env, tmp_path, play_context(season, today, "g/rules.html"), data)
    return (tmp_path / "play.html").read_text()


def test_skeleton_and_states(tmp_path, season):
    html = _render(tmp_path, season)
    for s in ('window.PLAY=', '"api_base_url":"https://smw-players.example.workers.dev"',
              'id="playLoading"', "Loading players…",
              'id="playError"', "Couldn't load players — try again in a minute.",
              'id="playNotFound"', "No player named", 'href="join.html"',
              'id="playExplainer"', 'id="playBoard"', 'id="playTable"', 'id="playDetail"',
              'id="playHeading"', 'id="playUnknown"', 'id="playMissingName"',
              'id="playDetailHeading"', 'id="playJoined"', 'id="playPicks"',
              "rankedPickPoints", "function composeView", 'fetch(D.api_base_url'):
        assert s in html, s
    assert html.count("fetch(") == 1
    assert '"state":"live"' in html
    assert "No projections yet" not in html


def test_own_nav_and_footer(tmp_path, season):
    html = _render(tmp_path, season)
    nav = html.split('<nav class="pills"', 1)[1].split("</nav>", 1)[0]
    assert 'href="play.html" aria-current="page"' in nav and 'href="join.html"' in nav
    for gone in ("index.html", "whatif.html", "scenarios.html", "history.html"):
        assert gone not in nav, gone
    assert 'href="g/rules.html"' in html
    assert "Films &amp; projections as of Aug 15, 2026 · players live." in html
    assert "<title>Play Along · Summer Movie Wager 2026</title>" in html
    assert "yearSelect" not in html and "groupSelect" not in html   # not a friends page


def test_early_state_has_no_projected_anywhere_outside_js(tmp_path, season):
    html = _render(tmp_path, season, forecastable=False, reason="only 3 films have projections")
    assert '"state":"early"' in html and '"projected_top":[]' in html
    assert "only 3 films have projections" in html
    markup = html.split("<script>window.PLAY=", 1)[0]
    assert "Projected" not in markup


def test_hostile_title_is_escaped_in_embed(tmp_path, season):
    evil = "</script><img src=x onerror=alert(1)>"
    projs = [_proj(evil, 5e8)] + [_proj(f"M{i:02d}", 400e6 / i, floor=100e6 / i) for i in range(1, 12)]
    cat = MovieCatalog([_film(p.title, gross=p.floor or 1.0) for p in projs], projs, [])
    html = _render(tmp_path, season, cat=cat)
    assert "\\u003c/script>\\u003cimg" in html
    assert evil not in html


def test_no_external_reference_but_the_api(tmp_path, season):
    html = _render(tmp_path, season).replace(CFG.api_base_url, "")
    for marker in ("http://", "https://", "//cdn", "@import", "url(http", "XMLHttpRequest"):
        assert marker not in html, marker


def test_play_snapshot(tmp_path, season):
    """Byte-exact snapshot. REGENERATION RITUAL: delete tests/fixtures/snapshot_play.html,
    run this test once (it rewrites the fixture and fails), OPEN THE FILE IN A BROWSER
    AND LOOK AT IT (it will show the 'Couldn't load players' state — that is correct
    offline), then re-run to lock."""
    html = _render(tmp_path, season)
    fixture = FIXTURES / "snapshot_play.html"
    if not fixture.exists():
        fixture.write_text(html)
        raise AssertionError("Snapshot fixture created; inspect it in a browser, then re-run.")
    assert html == fixture.read_text()
