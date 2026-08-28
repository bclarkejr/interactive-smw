from datetime import date
import pytest
import smw.render.build as build
from tests.conftest import FIXTURES

PAGES = ("index.html", "whatif.html", "scenarios.html", "history.html", "rules.html")
PLAY_PAGES = ("play.html", "join.html")
API = "https://smw-players.example.workers.dev"
MARKERS = ("http://", "https://", "//cdn", "@import", "url(http")

def _write_data(tmp_path):
    d = tmp_path / "data" / "seasons" / "2026"
    (d / "groups").mkdir(parents=True)
    (d / "season.yaml").write_text(
        "year: 2026\nwindow_start: 2026-05-01\nwindow_end: 2026-09-07\n"
        "seed: 42\nmonte_carlo_trials: 500\nmin_projections_for_forecast: 3\n")
    (d / "groups" / "g.yaml").write_text(
        "group_id: g\ndisplay_name: G\nplayers:\n"
        "  alice:\n"
        "    ranked: [Big Summer Film, Mid June Comedy, Labor Day Opener,"
        " F4, F5, F6, F7, F8, F9, F10]\n"
        "    dark_horses: [D1, D2, Tiny Tail Film]\n")
    (d / "play.yaml").write_text(f"api_base_url: {API}\ndefault_group: [alice]\n")

@pytest.fixture
def built_site(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "fetch",
                        lambda year: (FIXTURES / "synthetic_chart.html").read_text())
    monkeypatch.setattr(build, "fetch_players", lambda url: [])
    _write_data(tmp_path)
    out = tmp_path / "out"
    build.run_build(tmp_path / "data", out, date(2026, 8, 15), local=True)
    return out / "2026" / "g"

def test_no_external_origin_references(built_site):
    for page in PAGES:
        html = (built_site / page).read_text()
        for marker in MARKERS:
            assert marker not in html, f"{page} contains {marker}"

def test_no_page_fetches_data_json(built_site):
    # data.json is published for humans and tools; no friends page fetches anything (§13.1).
    for page in PAGES:
        html = (built_site / page).read_text()
        assert "fetch(" not in html
        assert "XMLHttpRequest" not in html

def test_friends_pages_do_not_link_to_play_along(built_site):
    # Play-along spec §4.1: separate audience, fixed friends nav.
    for page in PAGES:
        html = (built_site / page).read_text()
        assert 'href="play.html"' not in html and 'href="join.html"' not in html
        assert "../play.html" not in html and "../join.html" not in html

def test_play_pages_reference_exactly_the_api_origin(built_site):
    # Play-along spec §5.1 departure: one fetch each to the configured origin, nothing else.
    for page in PLAY_PAGES:
        html = (built_site.parent / page).read_text()
        assert API in html, page
        stripped = html.replace(API, "")
        for marker in MARKERS:
            assert marker not in stripped, f"{page} contains {marker} beyond the API origin"
        assert html.count("fetch(") == 1, page
        assert "XMLHttpRequest" not in html

def test_play_pages_fail_on_any_other_origin(tmp_path, monkeypatch):
    # The allowance is for the configured origin only; a build against a different
    # origin must not smuggle the old one through a template or script.
    monkeypatch.setattr(build, "fetch",
                        lambda year: (FIXTURES / "synthetic_chart.html").read_text())
    monkeypatch.setattr(build, "fetch_players", lambda url: [])
    _write_data(tmp_path)
    other = "https://other.example"
    (tmp_path / "data" / "seasons" / "2026" / "play.yaml").write_text(
        f"api_base_url: {other}\n")
    out = tmp_path / "out"
    build.run_build(tmp_path / "data", out, date(2026, 8, 15), local=True)
    for page in PLAY_PAGES:
        html = (out / "2026" / page).read_text()
        assert API not in html
        assert "https://" not in html.replace(other, "")

def test_reproducible_build(built_site, tmp_path, monkeypatch):
    # Byte-identical output for identical inputs (§1.3): rebuild into a second
    # directory from the same inputs and diff every page, play pages included.
    monkeypatch.setattr(build, "fetch",
                        lambda year: (FIXTURES / "synthetic_chart.html").read_text())
    monkeypatch.setattr(build, "fetch_players", lambda url: [])
    out2 = tmp_path / "out2"
    build.run_build(tmp_path / "data", out2, date(2026, 8, 15), local=True)
    for page in PAGES + ("data.json",):
        assert (built_site / page).read_bytes() == (out2 / "2026" / "g" / page).read_bytes(), page
    for page in PLAY_PAGES:
        assert (built_site.parent / page).read_bytes() == (out2 / "2026" / page).read_bytes(), page
    assert (built_site.parent.parent / "index.html").read_bytes() == \
        (out2 / "index.html").read_bytes()
