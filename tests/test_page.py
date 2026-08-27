from datetime import date
import re
from smw.render.page import base_context, fmt_money, json_embed, make_env, write_page

TODAY = date(2026, 8, 15)

def _render_rules(tmp_path, season, group):
    env = make_env()
    ctx = base_context(season, group, active="rules", today=TODAY)
    write_page(env, "rules.html.j2", tmp_path, "rules.html", ctx)
    return (tmp_path / "rules.html").read_text()

def test_autoescape_is_forced_on():
    env = make_env()
    assert env.autoescape is True  # not extension-guessed

def test_json_embed_escapes_script_breakout():
    out = str(json_embed({"t": "</script><b>"}))
    assert "</script" not in out
    assert "\\u003c/script" in out

def test_fmt_money_matches_mockup():
    assert fmt_money(1_020_000_000) == "$1.02B"
    assert fmt_money(498_000_000) == "$498.0M"
    assert fmt_money(310_491_022) == "$310.5M"
    assert fmt_money(468_000) == "$0.5M"

def test_theme_script_in_head_before_body(tmp_path, season, group):
    html = _render_rules(tmp_path, season, group)
    head = html.split("</head>")[0]
    assert "prefers-color-scheme" in head or "data-theme" in head
    assert html.index("data-theme") < html.index("<body")

def test_nav_pills_all_live_links_with_aria_current(tmp_path, season, group):
    html = _render_rules(tmp_path, season, group)
    for href in ("index.html", "whatif.html", "scenarios.html", "history.html"):
        assert re.search(rf'<a[^>]+href="{href}"', html)
    # rules page is footer-linked, not a nav pill: no pill is current on it.
    # Scoped to the <nav> markup: the mockup's own CSS legitimately contains the
    # literal string 'aria-current="page"' in a selector (nav.pills a[aria-current="page"]).
    nav = html[html.index("<nav"):html.index("</nav>")]
    assert 'aria-current="page"' not in nav

def test_scoring_rules_reproduced_on_site(tmp_path, season, group):
    html = _render_rules(tmp_path, season, group)
    for needle in ("13", "10", "7", "5", "3", "dark horse", "no tiebreaker"):
        assert needle.lower() in html.lower()

def test_no_external_references(tmp_path, season, group):
    html = _render_rules(tmp_path, season, group)
    assert "http://" not in html and "https://" not in html

from smw.render.page import Site

def test_title_h1_selectors_and_footer(tmp_path, season, group):
    site = Site(years=((2027, "x"), (2026, "testers")),
                groups=(("testers", "Test League"), ("aaa", "Zed League")),
                forecast_note="Forecast: 2,000 seeded Monte Carlo seasons over 18 projected films.")
    env = make_env()
    ctx = base_context(season, group, "rules", TODAY, site)
    write_page(env, "rules.html.j2", tmp_path, "rules.html", {**ctx, "title": "Scoring rules"})
    html = (tmp_path / "rules.html").read_text()
    assert "<title>Scoring rules · Summer Movie Wager 2026 · Test League</title>" in html
    assert "<h1>🍿 Summer Movie Wager</h1>" in html
    assert "Wager window: May 1 – Sep 7, 2026" in html
    assert "Refreshed Aug 15, 2026" in html
    # year selector: newest first, current selected, target = that year's default group leaderboard
    assert html.index('value="../../2027/x/index.html"') < html.index('value="../../2026/testers/index.html" selected')
    # group selector: by display name, current selected, same page filename
    assert html.index('value="../testers/rules.html" selected') < html.index('value="../aaa/rules.html"')
    assert 'onchange="location.href=this.value"' in html
    assert "2,000 seeded Monte Carlo seasons over 18 projected films." in html
    assert 'id="themeToggle"' in html and "◐ Theme" in html
    assert 'class="pills"' in html and 'footer class="site"' in html

def test_single_option_selectors_still_render(tmp_path, season, group):
    html = _render_rules(tmp_path, season, group)   # site=None → one year, one group
    assert html.count("<select") == 2
    assert 'value="../../2026/testers/index.html" selected' in html
    assert 'value="../testers/rules.html" selected' in html
