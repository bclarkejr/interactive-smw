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

def test_fmt_money():
    assert fmt_money(1_234_000_000) == "$1.2B"
    assert fmt_money(310_491_022) == "$310.5M"
    assert fmt_money(468_000) == "$468K"
    assert fmt_money(0) == "$0"

def test_theme_script_in_head_before_body(tmp_path, season, group):
    html = _render_rules(tmp_path, season, group)
    head = html.split("</head>")[0]
    assert "prefers-color-scheme" in head or "data-theme" in head
    assert html.index("data-theme") < html.index("<body")

def test_nav_pills_all_live_links_with_aria_current(tmp_path, season, group):
    html = _render_rules(tmp_path, season, group)
    for href in ("index.html", "whatif.html", "scenarios.html", "history.html"):
        assert re.search(rf'<a[^>]+href="{href}"', html)
    # rules page is footer-linked, not a nav pill: no pill is current on it
    assert 'aria-current="page"' not in html

def test_scoring_rules_reproduced_on_site(tmp_path, season, group):
    html = _render_rules(tmp_path, season, group)
    for needle in ("13", "10", "7", "5", "3", "dark horse", "no tiebreaker"):
        assert needle.lower() in html.lower()

def test_no_external_references(tmp_path, season, group):
    html = _render_rules(tmp_path, season, group)
    assert "http://" not in html and "https://" not in html
