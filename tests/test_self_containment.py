import json
from datetime import date
import pytest
import smw.render.build as build
from tests.conftest import FIXTURES

PAGES = ("index.html", "whatif.html", "scenarios.html", "history.html", "rules.html")

@pytest.fixture
def built_site(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "fetch",
                        lambda year: (FIXTURES / "year_chart.html").read_text())
    d = tmp_path / "data"
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
    out = tmp_path / "out"
    build.run_build(d, out, date(2026, 8, 15), local=True)
    return out

def test_no_external_origin_references(built_site):
    for page in PAGES:
        html = (built_site / page).read_text()
        for marker in ("http://", "https://", "//cdn", "@import", "url(http"):
            assert marker not in html, f"{page} contains {marker}"

def test_no_page_fetches_data_json(built_site):
    # data.json is published for humans and tools; no page fetches it (§13.1).
    for page in PAGES:
        html = (built_site / page).read_text()
        assert "fetch(" not in html
        assert "XMLHttpRequest" not in html

def test_reproducible_build(built_site, tmp_path, monkeypatch):
    # Byte-identical output for identical inputs (§1.3): rebuild into a second
    # directory from the same inputs and diff every page.
    monkeypatch.setattr(build, "fetch",
                        lambda year: (FIXTURES / "year_chart.html").read_text())
    out2 = tmp_path / "out2"
    # rebuild with the same data dir the fixture created
    build.run_build(tmp_path / "data", out2, date(2026, 8, 15), local=True)
    for page in PAGES + ("data.json",):
        assert (built_site / page).read_bytes() == (out2 / page).read_bytes(), page
