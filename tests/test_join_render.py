from datetime import date

from smw.config.play import PlayConfig
from smw.render.page import make_env
from smw.render.play import build_play_data, play_context, render_join
from tests.conftest import FIXTURES
from tests.test_views import _catalog

TODAY = date(2026, 8, 15)
CFG = PlayConfig("https://smw-players.example.workers.dev", ())


def _render(tmp_path, season, season_over=False, today=TODAY):
    cat = _catalog()
    actual = [f.title for f in sorted(cat.films, key=lambda f: -f.cumulative_gross)][:10]
    env = make_env()
    data = build_play_data(season, cat, actual, True, None, today, CFG,
                           season_over=season_over)
    render_join(env, tmp_path, play_context(season, today, "g/rules.html"), data, season_over)
    return (tmp_path / "join.html").read_text()


def test_form_shape(tmp_path, season):
    html = _render(tmp_path, season)
    assert 'id="joinForm"' in html and 'id="username"' in html
    assert 'pattern="[a-z0-9][a-z0-9-]{1,22}[a-z0-9]"' in html
    assert "3–24 characters: lowercase letters, digits, and hyphens (not at the ends)" in html
    assert html.count('name="ranked"') == 10 and html.count('name="dark"') == 3
    assert html.count('list="films"') == 13
    assert '<datalist id="films">' in html
    assert '<option value="M01">May 1</option>' in html     # title + release date (§5.2)
    assert html.count("<option value=") == 18
    for s in ('id="joinError"', 'id="joinDone"', 'id="joinName"', 'id="joinLink"', 'id="joinCopy"',
              "Picks are final", "update weekly", "function validateSubmission",
              'href="join.html" aria-current="page"'):
        assert s in html, s
    assert html.count("fetch(") == 1


def test_season_over_replaces_form(tmp_path, season):
    html = _render(tmp_path, season, season_over=True)
    assert "Season's over" in html and 'href="play.html"' in html
    assert 'id="joinForm"' not in html
    assert "window.PLAY=" in html          # join.js still inlined; main() no-ops without the form


def test_hostile_title_in_datalist_is_escaped(tmp_path, season):
    from smw.model.project import MovieCatalog
    from tests.test_views import _film, _proj
    evil = '"><script>alert(1)</script>'
    projs = [_proj(evil, 5e8)] + [_proj(f"M{i:02d}", 400e6 / i, floor=100e6 / i) for i in range(1, 12)]
    cat = MovieCatalog([_film(p.title, gross=p.floor or 1.0) for p in projs], projs, [])
    actual = [f.title for f in sorted(cat.films, key=lambda f: -f.cumulative_gross)][:10]
    env = make_env()
    data = build_play_data(season, cat, actual, True, None, TODAY, CFG, season_over=False)
    render_join(env, tmp_path, play_context(season, TODAY, "g/rules.html"), data, False)
    html = (tmp_path / "join.html").read_text()
    assert "<script>alert(1)</script>" not in html
    assert "&#34;&gt;&lt;script&gt;" in html or "&quot;&gt;&lt;script&gt;" in html


def test_no_external_reference_but_the_api(tmp_path, season):
    html = _render(tmp_path, season).replace(CFG.api_base_url, "")
    for marker in ("http://", "https://", "//cdn", "@import", "url(http", "XMLHttpRequest"):
        assert marker not in html, marker


def test_join_snapshot(tmp_path, season):
    """Byte-exact snapshot. REGENERATION RITUAL: delete tests/fixtures/snapshot_join.html,
    run once (writes the fixture and fails), OPEN IT IN A BROWSER AND LOOK AT IT, re-run to lock."""
    html = _render(tmp_path, season)
    fixture = FIXTURES / "snapshot_join.html"
    if not fixture.exists():
        fixture.write_text(html)
        raise AssertionError("Snapshot fixture created; inspect it in a browser, then re-run.")
    assert html == fixture.read_text()
