import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
MARKER = "/* ---------- site additions ---------- */"
LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#a16207", "#be185d"]
DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#facc15", "#f472b6"]

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def _mockup_style() -> str:
    html = (ROOT / "brainstorming" / "mockup.html").read_text()
    style = html.split("<style>", 1)[1].split("</style>", 1)[0]
    style = re.sub(r"\.mocknote\{[^}]*\}", "", style)           # the mockup's own banner
    style = style.replace(".page{display:none}.page.active{display:block}", "")
    style = re.sub(r"--s-[a-z0-9_-]+:#[0-9a-fA-F]{3,6};", "", style)  # per-user tokens
    return style

def _site_css():
    css = (ROOT / "smw" / "render" / "static" / "site.css").read_text()
    assert css.count(MARKER) == 1
    verbatim, additions = css.split(MARKER)
    return verbatim, additions

def test_verbatim_block_equals_mockup_style():
    verbatim, _ = _site_css()
    assert _norm(verbatim) == _norm(_mockup_style())

def test_additions_hold_only_series_and_selector_rules():
    _, additions = _site_css()
    additions = re.sub(r"/\*.*?\*/", "", additions, flags=re.S)  # comments are not rules
    selectors = [s.strip() for s in re.findall(r"([^{}]+)\{", additions)]
    assert selectors
    for sel in selectors:
        assert (".series-" in sel or sel.startswith("@media")
                or sel in (".sel", ".vh")), sel

def test_series_colours_in_all_three_token_blocks():
    _, additions = _site_css()
    flat = _norm(additions)
    for i, (light, dark) in enumerate(zip(LIGHT, DARK)):
        assert f".series-{i}{{--series:{light}}}" in flat
        assert f':root[data-theme="dark"] .series-{i}{{--series:{dark}}}' in flat
        assert f':root:not([data-theme="light"]) .series-{i}{{--series:{dark}}}' in flat

def test_no_legacy_tokens_anywhere():
    css = (ROOT / "smw" / "render" / "static" / "site.css").read_text()
    for tok in ("--card", "--dim", "--pos", "--gold", ".num", ".table-scroll"):
        assert tok not in css, tok
