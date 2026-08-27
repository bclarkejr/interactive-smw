from datetime import date
from pathlib import Path
from smw.model.simulate import simulate
from smw.render.page import base_context, build_whatif_data, make_env, render_whatif
from tests.test_views import _catalog

TODAY = date(2026, 8, 15)

def _render(tmp_path, season, group, locked=False):
    env = make_env()
    ctx = base_context(season, group, "whatif", TODAY)
    if locked:
        render_whatif(env, tmp_path, ctx, None, "only 3 films have non-zero projections")
    else:
        cat = _catalog()
        data = build_whatif_data(season, group, cat, simulate(season, group, cat))
        render_whatif(env, tmp_path, ctx, data, None)
    return (tmp_path / "whatif.html").read_text()

STATIC = Path(__file__).parent.parent / "smw" / "render" / "static"

def test_locked_state_notice(tmp_path, season, group):
    html = _render(tmp_path, season, group, locked=True)
    assert "unlocks once the forecast is live" in html
    assert "only 3 films" in html
    assert 'id="wiList"' not in html and "new Sortable(" not in html

def test_embedded_data_and_scripts(tmp_path, season, group):
    html = _render(tmp_path, season, group)
    assert "window.WHATIF" in html
    assert "rankedPickPoints" in html   # scoring.js inlined
    assert "new Sortable(" in html and "Sortable 1.15.6 - MIT" in html
    assert 'aria-live="polite"' in html
    for s in ("<h2>🎬 What If? sandbox</h2>", "player's score recompute",
              "If it ends this way…", "↺ Reset to projected order",
              "Films outside the projected top 15 can't be dragged in and score 0.",
              "<h2>Points by film, for this order</h2>", 'id="wiStandings"', 'id="wiGrid"',
              '<th>Place</th><th class="t">Player</th><th>Pts</th><th>vs proj.</th>'):
        assert s in html, s

def test_site_drag_code_is_gone():
    js = (STATIC / "whatif.js").read_text()
    for s in ("dragstart", "dragover", "touchstart", "elementFromPoint", "draggable"):
        assert s not in js, s
    assert "new Sortable(" in js and "ghostClass" in js and "delayOnTouchOnly" in js

def test_grid_columns_follow_player_order_not_standings():
    js = (STATIC / "whatif.js").read_text()
    grid = js[js.index("#wiGrid thead"):]
    assert "D.players.forEach" in grid          # header + cells iterate pipeline order
    assert "rows.forEach(function (r) { th(" not in js  # never the score-sorted array

def test_page_minus_library_has_no_site_drag_code(tmp_path, season, group):
    html = _render(tmp_path, season, group)
    start = html.index("/*! Sortable 1.15.6")
    end = html.index("</script>", start)
    rest = html[:start] + html[end:]
    assert "new Sortable(" in rest
    for s in ("dragstart", "dragover", "touchstart", "elementFromPoint"):
        assert s not in rest, s

def test_vendored_library_is_minified_1_15_6_without_urls():
    lib = (STATIC / "sortable.min.js").read_text()
    assert lib.startswith("/*! Sortable 1.15.6 - MIT | (c) 2019 Lebedev Konstantin */")
    assert "://" not in lib and "</script" not in lib
    assert lib.count("\n") < 5   # minified

def test_data_shape(season, group):
    cat = _catalog()
    data = build_whatif_data(season, group, cat, simulate(season, group, cat))
    assert len(data["films"]) == season.matrix_rows
    assert data["films"][0] == "M01"
    names = [p["name"] for p in data["players"]]
    assert set(names) == set(group.players)
    assert all(len(p["ranked"]) == 10 and len(p["dark"]) == 3 for p in data["players"])
    assert set(data["baseline"]) == set(group.players)

def test_no_external_references(tmp_path, season, group):
    html = _render(tmp_path, season, group)
    assert "http://" not in html and "https://" not in html
