from datetime import date
import json
import pytest
from smw.catalog.resolve import ResolutionError, load_history, resolve_grosses
from smw.ingest.boxoffice import ChartRow

def _hist(tmp_path, rows):
    p = tmp_path / "box_office_history.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return load_history(p)

def _row(title, gross, rel=date(2026, 5, 1)):
    return ChartRow(title, gross, rel, False)

def test_missing_history_file_is_empty(tmp_path):
    assert load_history(tmp_path / "nope.jsonl") == {}

def test_same_date_rows_dedupe_to_max(tmp_path):
    h = _hist(tmp_path, [
        {"movie": "A", "date": "2026-06-01", "cumulative_gross": 100.0},
        {"movie": "A", "date": "2026-06-01", "cumulative_gross": 120.0},
        {"movie": "A", "date": "2026-06-08", "cumulative_gross": 130.0},
    ])
    assert h["A"] == [(date(2026, 6, 1), 120.0), (date(2026, 6, 8), 130.0)]

def test_history_sorted_by_date_even_if_file_is_not(tmp_path):
    h = _hist(tmp_path, [
        {"movie": "A", "date": "2026-06-08", "cumulative_gross": 130.0},
        {"movie": "A", "date": "2026-06-01", "cumulative_gross": 100.0},
    ])
    assert [d for d, _ in h["A"]] == [date(2026, 6, 1), date(2026, 6, 8)]

def test_chart_merges_by_max_never_overwrites(season):
    history = {"A": [(date(2026, 6, 1), 150.0)]}
    grosses, carried, usable = resolve_grosses(
        season, history, [_row("A", 120.0)], floor=1.0, today=date(2026, 6, 8))
    assert grosses["A"] == 150.0  # highest, not latest
    assert usable
    assert carried == set()

def test_carry_forward_off_chart_title(season):
    history = {"Gone": [(date(2026, 6, 1), 500.0)]}
    grosses, carried, _ = resolve_grosses(
        season, history, [_row("A", 120.0)], floor=1000.0, today=date(2026, 6, 8))
    assert grosses["Gone"] == 500.0
    assert carried == {"Gone"}

def test_guard_c_carried_above_floor_raises_with_alias_hint(season):
    history = {"Renamed Upstream": [(date(2026, 6, 1), 5_000_000.0)]}
    with pytest.raises(ResolutionError, match="alias_of.*Renamed Upstream"):
        resolve_grosses(season, history, [_row("A", 120.0)],
                        floor=468_000.0, today=date(2026, 6, 8))

def test_observations_after_cutoff_ignored(season):
    # Run on window_end + 1 sees the full window; later-dated rows include
    # post-window money and must not count.
    history = {"A": [(date(2026, 9, 8), 200.0), (date(2026, 9, 20), 999.0)]}
    grosses, _, usable = resolve_grosses(
        season, history, [], floor=1.0, today=date(2026, 9, 8))
    assert grosses["A"] == 200.0

def test_chart_frozen_after_window_end_plus_one(season):
    # today = window_end + 2 → chart_usable false: chart values ignored, Guard C skipped.
    history = {"A": [(date(2026, 9, 8), 200.0)]}
    grosses, carried, usable = resolve_grosses(
        season, history, [_row("A", 5_000_000.0)], floor=1.0, today=date(2026, 9, 9))
    assert not usable
    assert grosses["A"] == 200.0
    assert carried == {"A"}

def test_chart_usable_on_window_end_plus_one(season):
    _, _, usable = resolve_grosses(season, {}, [_row("A", 1.0)],
                                   floor=1.0, today=date(2026, 9, 8))
    assert usable

def test_with_snapshot_merges_today_by_max():
    from smw.catalog.resolve import with_snapshot
    h = {"A": [(date(2026, 6, 1), 100.0), (date(2026, 6, 8), 150.0)],
         "Old": [(date(2026, 6, 1), 5.0)]}
    out = with_snapshot(h, {"A": 140.0, "New": 20.0, "Zero": 0.0}, date(2026, 6, 8))
    assert out["A"] == [(date(2026, 6, 1), 100.0), (date(2026, 6, 8), 150.0)]  # max wins
    assert out["New"] == [(date(2026, 6, 8), 20.0)]
    assert out["Old"] == h["Old"]
    assert "Zero" not in out

def test_with_snapshot_drops_observations_after_today():
    from smw.catalog.resolve import with_snapshot
    h = {"A": [(date(2026, 6, 1), 100.0), (date(2026, 6, 15), 900.0)],
         "Future": [(date(2026, 7, 1), 5.0)]}
    out = with_snapshot(h, {"A": 150.0}, date(2026, 6, 8))
    assert out["A"] == [(date(2026, 6, 1), 100.0), (date(2026, 6, 8), 150.0)]
    assert "Future" not in out
