"""Acceptance criteria 7, 8, 9, 12, 13 across every page of every group."""
import re
from datetime import date
import pytest
import smw.render.build as build
from tests.conftest import FIXTURES

PAGES = ("index.html", "whatif.html", "scenarios.html", "history.html", "rules.html")
GONE = (".num", ".table-scroll", "--card", "--dim", "--pos", "--gold", "cell-", "divider-row",
        "stats-line", '"standings"', "film-list", "two-col", "tab-row", 'class="tab"',
        "highlight-col", "chart-wrap", "odds-chart", "legend-swatch", "season-line",
        "theme-toggle", "reset-order", "points-grid", "crosshair-tip")
HEADINGS = {
    "index.html": ("<h2>🏆 Projected Standings</h2>", "<h2>📋 All Players' Lists</h2>",
                   "<h2>👤 Per-Player Detail</h2>", "<h2>🎞️ Films</h2>"),
    "whatif.html": ("<h2>🎬 What If? sandbox</h2>", "<h2>Points by film, for this order</h2>",
                    "↺ Reset to projected order"),
    "scenarios.html": ("<h2>🔮 Winning Scenarios</h2>", "crowns them champion"),
    "history.html": ("<h2>📈 Odds Over Time</h2>", "A break in a line"),
    "rules.html": ("<h2>📜 Scoring rules</h2>", "<strong>109</strong>"),
}

@pytest.fixture(scope="module")
def site(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("site")
    d = tmp / "data" / "seasons" / "2026"
    (d / "groups").mkdir(parents=True)
    # 3 chart films + 8 analyst entries = 11 non-zero projections ≥ the structural 10
    # and the policy 11 → a LIVE forecast, so What If? and Scenarios are unlocked.
    (d / "season.yaml").write_text(
        "year: 2026\nwindow_start: 2026-05-01\nwindow_end: 2026-09-07\n"
        "seed: 42\nmonte_carlo_trials: 500\nmin_projections_for_forecast: 11\n"
        "default_group: g\n")
    (d / "preopening_projections.yaml").write_text("".join(
        f'"Estimated Film {i}":\n'
        "  release_date: 2026-07-10\n"
        "  opening_weekend_estimate: 40_000_000\n"
        "  total_domestic_estimate: 110_000_000\n"
        "  confidence: med\n"
        for i in range(8)))
    for gid, name in (("g", "G League"), ("h", "H League")):
        (d / "groups" / f"{gid}.yaml").write_text(
            f"group_id: {gid}\ndisplay_name: {name}\nplayers:\n"
            "  alice:\n"
            "    ranked: [Big Summer Film, Mid June Comedy, Labor Day Opener, F4, F5, F6, F7, F8, F9, F10]\n"
            "    dark_horses: [D1, D2, Tiny Tail Film]\n"
            "  bob:\n"
            "    ranked: [Mid June Comedy, Big Summer Film, Labor Day Opener, F4, F5, F6, F7, F8, F9, F10]\n"
            "    dark_horses: [D1, D2, Tiny Tail Film]\n")
    (d / "forecast_history").mkdir()
    for gid in ("g", "h"):
        (d / "forecast_history" / f"{gid}.jsonl").write_text(
            '{"date": "2026-08-08", "player": "alice", "win_prob": 0.6, "median_final_pts": 50, "p10": 40, "p90": 60}\n'
            '{"date": "2026-08-08", "player": "bob", "win_prob": 0.4, "median_final_pts": 45, "p10": 35, "p90": 55}\n')
    out = tmp / "out"
    with pytest.MonkeyPatch.context() as mp:  # module-scoped, so no `monkeypatch` fixture
        mp.setattr(build, "fetch", lambda year: (FIXTURES / "synthetic_chart.html").read_text())
        build.run_build(tmp / "data", out, date(2026, 8, 15), local=True)
    return out

def _pages(site):
    for gid in ("g", "h"):
        for page in PAGES:
            yield gid, page, (site / "2026" / gid / page).read_text()

def test_h1_title_and_selectors_everywhere(site):
    for gid, page, html in _pages(site):
        assert "<h1>🍿 Summer Movie Wager</h1>" in html, (gid, page)
        name = "G League" if gid == "g" else "H League"
        assert re.search(rf"<title>[^<]+ · Summer Movie Wager 2026 · {name}</title>", html), (gid, page)
        assert 'value="../../2026/g/index.html" selected' in html, (gid, page)
        assert f'value="../{gid}/{page}" selected' in html, (gid, page)
        other = "h" if gid == "g" else "g"
        assert f'value="../{other}/{page}"' in html, (gid, page)

def test_every_table_is_in_a_scroller(site):
    for gid, page, html in _pages(site):
        body = html.split("</style>")[1]
        for m in re.finditer(r"<table\b[^>]*>", body):
            before = body[:m.start()].rstrip()
            if 'id="wiStandings"' in m.group(0):
                assert before.endswith('<div aria-live="polite">'), (gid, page)  # §3.5: the panel table
            else:
                assert re.search(r'<div class="scroller"(?: style="border:none")?>$', before), (gid, page, m.group(0))

def test_no_legacy_classes_or_tokens(site):
    for gid, page, html in _pages(site):
        for s in GONE:
            assert s not in html, (gid, page, s)

def test_verbatim_copy_per_page(site):
    for gid, page, html in _pages(site):
        for s in HEADINGS[page]:
            assert s in html, (gid, page, s)
        assert "Raw numbers: <a href=\"data.json\">data.json</a>" in html
        assert "Forecast: 500 seeded Monte Carlo seasons over 11 projected films." in html

def test_odds_chart_geometry(site):
    html = (site / "2026" / "g" / "history.html").read_text()
    assert 'viewBox="0 0 920 360"' in html and 'class="dl"' in html
    assert html.count('text-anchor="middle"') <= 8

def test_self_contained_including_vendored_library(site):
    for gid, page, html in _pages(site):
        for marker in ("http://", "https://", "//cdn", "@import", "url(http", "fetch(", "XMLHttpRequest"):
            assert marker not in html, (gid, page, marker)
    root = (site / "index.html").read_text()
    assert "http://" not in root and "https://" not in root

def test_whatif_page_minus_library_has_no_drag_code(site):
    for gid in ("g", "h"):
        html = (site / "2026" / gid / "whatif.html").read_text()
        start = html.index("/*! Sortable 1.15.6")
        end = html.index("</script>", start)
        rest = html[:start] + html[end:]
        assert "new Sortable(" in rest, gid
        for s in ("dragstart", "dragover", "touchstart", "elementFromPoint"):
            assert s not in rest, (gid, s)
