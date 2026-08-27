from datetime import date
from smw.model.simulate import simulate
from smw.render.page import base_context, make_env, render_leaderboard
from smw.render.views import build_leaderboard_view
from smw.score.rules import score_player
from tests.test_views import _catalog  # reuse the deterministic catalog factory

TODAY = date(2026, 8, 15)

def _render(tmp_path, season, group, with_sim=True):
    cat = _catalog()
    sim = simulate(season, group, cat) if with_sim else None
    actual = [f.title for f in sorted(cat.films, key=lambda f: -f.cumulative_gross)
              if f.cumulative_gross > 0][:10]
    current = {u: score_player(group.players[u], actual) for u in group.players}
    view = build_leaderboard_view(season, group, cat, sim, current, actual,
                                  None if with_sim else "only 3 films have projections",
                                  TODAY)
    env = make_env()
    ctx = base_context(season, group, "leaderboard", TODAY)
    render_leaderboard(env, tmp_path, ctx, view)
    return (tmp_path / "index.html").read_text()

def test_hostile_title_escaped(tmp_path, season, group):
    # Titles come from an external HTML document and are untrusted (§11.4).
    from smw.catalog.normalize import Film
    from smw.model.project import MovieCatalog, Projection
    hostile = "</script><script>alert(1)</script> The Movie"
    f = Film(hostile, date(2026, 5, 1), "in_theaters", "wide", 5.0, None)
    p = Projection(hostile, 10.0, 0.2, 5.0, "decay model", 8.0, 12.0)
    cat = MovieCatalog([f], [p], [])
    view = build_leaderboard_view(season, group, cat, None,
                                  {u: 0 for u in group.players}, [hostile],
                                  "reason", TODAY)
    env = make_env()
    ctx = base_context(season, group, "leaderboard", TODAY)
    render_leaderboard(env, tmp_path, ctx, view)
    html = (tmp_path / "index.html").read_text()
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html

def test_current_points_mode_has_no_forecast_numbers(tmp_path, season, group):
    # §13.5 named gap: below the threshold the page contains no win percentage
    # and no projected total.
    html = _render(tmp_path, season, group, with_sim=False)
    assert "Win odds" not in html
    assert "% win" not in html
    assert "Projected pts" not in html
    assert "Current pts" in html
    assert "🏆 Current Standings" in html

def test_live_mode_has_forecast_rows(tmp_path, season, group):
    html = _render(tmp_path, season, group)
    assert "Win odds" in html
    assert "🏆 Projected Standings" in html
    assert "Outside the top 10" in html

def test_no_external_references(tmp_path, season, group):
    html = _render(tmp_path, season, group)
    assert "http://" not in html and "https://" not in html

def test_leaderboard_structure_matches_mockup(tmp_path, season, group):
    html = _render(tmp_path, season, group)
    for s in ("<h2>🏆 Projected Standings</h2>", "<h2>📋 All Players' Lists</h2>",
              "<h2>👤 Per-Player Detail</h2>", "<h2>🎞️ Films</h2>",
              'id="matrix"', 'id="lists"', "Rows: top 15 films by projected median",
              "Show all tracked films", "projections, ranges, provenance",
              '<tr class="odds">', '<tr class="divider">', 'class="scroller" style="border:none"',
              '<th class="t">Slot</th>', "Dark horses", '<th class="t">Movie</th>'):
        assert s in html, s
    for gone in (".num", "table-scroll", "cell-pos", "divider-row", "stats-line"):
        assert gone not in html.split("</style>")[1], gone

def test_leaderboard_snapshot(tmp_path, season, group):
    """Byte-exact snapshot (§13.5). REGENERATION RITUAL: delete
    tests/fixtures/snapshot_index.html, run this test once (it rewrites the fixture
    and fails), OPEN THE FILE IN A BROWSER AND LOOK AT IT, then re-run to lock.
    A snapshot regenerated without human inspection tests nothing."""
    from tests.conftest import FIXTURES
    html = _render(tmp_path, season, group)
    fixture = FIXTURES / "snapshot_index.html"
    if not fixture.exists():
        fixture.write_text(html)
        raise AssertionError(
            "Snapshot fixture created. Open tests/fixtures/snapshot_index.html in a "
            "browser, inspect it, then re-run to lock.")
    assert html == fixture.read_text()
