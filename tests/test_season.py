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

def test_matrix_rows_below_ten_rejected(tmp_path):
    p = tmp_path / "season.yaml"
    p.write_text(BASE + "matrix_rows: 9\n")
    with pytest.raises(ValueError, match="matrix_rows"):
        load_season(p)

from smw.config.season import load_season_dir

def _season_dir(tmp_path, name="2026", extra="", groups=("b", "a")):
    d = tmp_path / name
    (d / "groups").mkdir(parents=True)
    (d / "season.yaml").write_text(BASE + extra)
    for g in groups:
        (d / "groups" / f"{g}.yaml").write_text(f"group_id: {g}\ndisplay_name: {g.upper()}\n")
    return d

def test_default_group_key_loads(tmp_path):
    p = tmp_path / "season.yaml"
    p.write_text(BASE + "default_group: smw-friends\n")
    assert load_season(p).default_group == "smw-friends"
    p.write_text(BASE)
    assert load_season(p).default_group is None

def test_default_group_must_be_string(tmp_path):
    p = tmp_path / "season.yaml"
    p.write_text(BASE + "default_group: 3\n")
    with pytest.raises(ValueError, match="default_group"):
        load_season(p)

def test_load_season_dir_fills_default_group_lexically(tmp_path):
    season, groups = load_season_dir(_season_dir(tmp_path))
    assert season.default_group == "a"
    assert [g.group_id for g in groups] == ["a", "b"]

def test_load_season_dir_keeps_explicit_default_group(tmp_path):
    season, _ = load_season_dir(_season_dir(tmp_path, extra="default_group: b\n"))
    assert season.default_group == "b"

def test_load_season_dir_unknown_default_group_raises(tmp_path):
    with pytest.raises(ValueError, match="default_group"):
        load_season_dir(_season_dir(tmp_path, extra="default_group: zzz\n"))

def test_load_season_dir_name_must_equal_year(tmp_path):
    with pytest.raises(ValueError, match="2026"):
        load_season_dir(_season_dir(tmp_path, name="2025"))

def test_load_season_dir_requires_a_group(tmp_path):
    with pytest.raises(ValueError, match="group"):
        load_season_dir(_season_dir(tmp_path, groups=()))
