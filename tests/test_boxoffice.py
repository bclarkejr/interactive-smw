"""Parser tests run against the REAL committed Box Office Mojo 2026 chart
(tests/fixtures/year_chart.html, fetched 2026-08-26) — offline, §13.5."""
from datetime import date
import pytest
from smw.ingest.boxoffice import ChartRow, IngestError, chart_floor, parse_chart, windowed
from tests.conftest import FIXTURES

HTML = (FIXTURES / "year_chart.html").read_text()
ROWS = parse_chart(HTML, 2026)
BY_TITLE = {r.title: r for r in ROWS}

def test_parses_rows_and_skips_junk():
    assert len(ROWS) == 200  # the chart's 200 data rows; header/footer skipped
    assert BY_TITLE["Spider-Man: Brand New Day"].gross == 863_346_542.0

def test_reads_in_year_gross_not_budget_or_total():
    # A December-2025 holdover: in-year gross is the first money+estimatable cell;
    # the later money+estimatable cell is the larger lifetime "Total Gross".
    assert BY_TITLE["Avatar: Fire and Ash"].gross == 153_986_141.0

def test_title_from_anchor_excludes_note_markup():
    rr = BY_TITLE["Top Gun/Top Gun: Maverick"]
    assert "Re-release" not in rr.title  # note text lives in a nested span

def test_rerelease_flagged():
    assert BY_TITLE["Top Gun/Top Gun: Maverick"].is_rerelease
    assert not BY_TITLE["Spider-Man: Brand New Day"].is_rerelease

def test_dates_stamped_with_chart_year():
    assert BY_TITLE["The Devil Wears Prada 2"].release_date == date(2026, 5, 1)

def test_window_filter_boundaries_and_rerelease(season):
    kept = {r.title for r in windowed(ROWS, season)}
    assert len(kept) == 76
    assert "The Devil Wears Prada 2" in kept            # May 1: boundary start, in
    assert "Insidious: Out of the Further" in kept      # Aug 21, in
    assert "Michael" not in kept                        # Apr 24, out
    assert "Top Gun/Top Gun: Maverick" not in kept      # May 13 but a re-release, out
    assert "Avatar: Fire and Ash" not in kept           # Dec, out

def test_guard_a_empty_chart_raises(season):
    with pytest.raises(IngestError, match="Guard A"):
        windowed([], season)

def test_guard_b_everything_filtered_raises_naming_rule_3(season):
    rows = [ChartRow("X", 1.0, date(2026, 6, 1), True)]
    with pytest.raises(IngestError, match="Rule 3"):
        windowed(rows, season)

def test_chart_floor_is_min_of_all_parsed_rows():
    assert chart_floor(ROWS) == 700_349.0  # "Stand by Me" re-release, rank 200

def test_synthetic_fixture_still_parses(season):
    # The hand-written chart used by the pipeline tests must keep parsing too.
    rows = parse_chart((FIXTURES / "synthetic_chart.html").read_text(), 2026)
    assert len(rows) == 7
    assert {r.title for r in windowed(rows, season)} == {
        "Big Summer Film", "Mid June Comedy", "Labor Day Opener", "Tiny Tail Film"}
