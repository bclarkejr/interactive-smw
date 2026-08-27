from datetime import date
import pytest
from smw.ingest.boxoffice import ChartRow, IngestError, chart_floor, parse_chart, windowed
from tests.conftest import FIXTURES

HTML = (FIXTURES / "year_chart.html").read_text()

def test_parses_rows_and_skips_junk():
    rows = parse_chart(HTML, 2026)
    assert len(rows) == 7  # footer/header rows skipped, re-release still parsed (flagged)
    by_title = {r.title: r for r in rows}
    assert by_title["Big Summer Film"].gross == 310_491_022.0

def test_reads_in_year_gross_not_budget_or_total():
    rows = parse_chart(HTML, 2026)
    holdover = next(r for r in rows if r.title == "Spring Holdover")
    assert holdover.gross == 150_000_000.0  # first money+estimatable cell, not budget, not Total Gross

def test_title_from_anchor_excludes_note_markup():
    rows = parse_chart(HTML, 2026)
    rr = next(r for r in rows if r.title == "Anniversary Classic")
    assert rr.title == "Anniversary Classic"  # no "2026 Re-release" text picked up

def test_rerelease_flagged():
    rows = parse_chart(HTML, 2026)
    assert next(r for r in rows if r.title == "Anniversary Classic").is_rerelease
    assert not next(r for r in rows if r.title == "Big Summer Film").is_rerelease

def test_dates_stamped_with_chart_year():
    rows = parse_chart(HTML, 2026)
    assert next(r for r in rows if r.title == "Big Summer Film").release_date == date(2026, 5, 1)

def test_window_filter_boundaries_and_rerelease(season):
    kept = {r.title for r in windowed(parse_chart(HTML, 2026), season)}
    assert kept == {"Big Summer Film", "Mid June Comedy", "Labor Day Opener", "Tiny Tail Film"}

def test_guard_a_empty_chart_raises(season):
    with pytest.raises(IngestError, match="Guard A"):
        windowed([], season)

def test_guard_b_everything_filtered_raises_naming_rule_3(season):
    rows = [ChartRow("X", 1.0, date(2026, 6, 1), True)]
    with pytest.raises(IngestError, match="Rule 3"):
        windowed(rows, season)

def test_chart_floor_is_min_of_all_parsed_rows():
    assert chart_floor(parse_chart(HTML, 2026)) == 468_000.0
