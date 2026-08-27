from datetime import date
from pathlib import Path
import pytest
from smw.config.season import Season, load_season

def test_load_season_from_yaml(tmp_path):
    p = tmp_path / "season.yaml"
    p.write_text(
        "year: 2026\nwindow_start: 2026-05-01\nwindow_end: 2026-09-07\n"
        "seed: 20260907\nmatrix_rows: 12\ndefault_wow:\n  wide: 0.5\n  animated_family: 0.6\n"
    )
    s = load_season(p)
    assert s.year == 2026
    assert s.window_start == date(2026, 5, 1)
    assert s.window_end == date(2026, 9, 7)
    assert s.seed == 20260907
    assert s.matrix_rows == 12                      # explicit value wins
    assert s.min_projections_for_forecast == 25     # default fills in
    assert s.default_wow == {"wide": 0.5, "animated_family": 0.6}

def test_missing_required_key_raises(tmp_path):
    p = tmp_path / "season.yaml"
    p.write_text("year: 2026\nwindow_start: 2026-05-01\nwindow_end: 2026-09-07\n")
    with pytest.raises(ValueError, match="seed"):
        load_season(p)

def test_inverted_window_raises(tmp_path):
    p = tmp_path / "season.yaml"
    p.write_text("year: 2026\nwindow_start: 2026-09-07\nwindow_end: 2026-05-01\nseed: 1\n")
    with pytest.raises(ValueError, match="window"):
        load_season(p)

BASE = "year: 2026\nwindow_start: 2026-05-01\nwindow_end: 2026-09-07\nseed: 1\n"

@pytest.mark.parametrize("extra,needle", [
    ("monte_carlo_trials: 0\n", "monte_carlo_trials"),
    ("matrix_rows: -3\n", "matrix_rows"),
    ("chart_contenders: many\n", "chart_contenders"),
    ("default_wow:\n  wide: 0.5\n", "animated_family"),
    ("default_wow:\n  wide: 1.5\n  animated_family: 0.6\n", "default_wow.wide"),
])
def test_invalid_values_fail_at_load(tmp_path, extra, needle):
    p = tmp_path / "season.yaml"
    p.write_text(BASE + extra)
    with pytest.raises(ValueError, match=needle):
        load_season(p)

def test_string_dates_rejected(tmp_path):
    p = tmp_path / "season.yaml"
    p.write_text('year: 2026\nwindow_start: "May 1"\nwindow_end: 2026-09-07\nseed: 1\n')
    with pytest.raises(ValueError):
        load_season(p)
