from datetime import date
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

def test_locked_state_notice(tmp_path, season, group):
    html = _render(tmp_path, season, group, locked=True)
    assert "unlocks once the forecast is live" in html
    assert "only 3 films" in html
    assert 'id="film-list"' not in html  # no sandbox markup (the CSS still mentions it)

def test_embedded_data_and_scripts(tmp_path, season, group):
    html = _render(tmp_path, season, group)
    assert "window.WHATIF" in html
    assert "rankedPickPoints" in html   # scoring.js inlined
    assert "aria-live" in html          # polite live region
    assert "If it ends this way" in html
    assert "can't be dragged in and score 0" in html

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
