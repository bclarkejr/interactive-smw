import math
from datetime import date, timedelta
import pytest
from smw.model.decay import DOW_WEIGHTS, day_weight
from smw.model.preopening import (
    CONFIDENCE_SIGMA, OPENING_WEEK_SHARE, derive_wow, project_preopening,
)

def test_opening_week_share_tied_to_dow_weights():
    assert OPENING_WEEK_SHARE == pytest.approx(sum(DOW_WEIGHTS[4:7]))
    assert OPENING_WEEK_SHARE == pytest.approx(0.70)

def test_derive_wow_solves_finite_series():
    # week_1 = 70/0.7 = 100; with w=0.5, N=10: total = 100*(1-0.5^10)/0.5 ≈ 199.8047
    w = derive_wow(70.0, 100.0 * (1 - 0.5 ** 10) / 0.5, 10, fallback=0.99)
    assert w == pytest.approx(0.5, abs=1e-6)

def test_derive_wow_no_root_falls_back():
    # total below week_1: impossible run shape → category default
    assert derive_wow(70.0, 50.0, 10, fallback=0.55) == 0.55
    # total above N*week_1 (limit as w→1): also no root in (0,1)
    assert derive_wow(70.0, 100.0 * 11, 10, fallback=0.55) == 0.55

def test_after_window_scores_zero(season):
    median, sigma = project_preopening(
        date(2026, 9, 8), 70_000_000, 200_000_000, "high", 0.55, season)
    assert (median, sigma) == (0.0, 0.0)

def test_sigma_by_confidence(season):
    rel = date(2026, 6, 19)
    for conf, expect in (("high", 0.20), ("med", 0.30), ("low", 0.45)):
        _, sigma = project_preopening(rel, 70_000_000, 200_000_000, conf, 0.55, season)
        assert sigma == expect

def test_long_run_caps_at_analyst_total(season):
    # Early release, whole run inside the window → in-window sum equals the run
    # total but must never exceed the analyst estimate.
    median, _ = project_preopening(
        date(2026, 5, 1), 70_000_000, 150_000_000, "med", 0.55, season)
    assert median <= 150_000_000
    assert median == pytest.approx(150_000_000, rel=0.01)

def test_late_window_release_projects_partial(season):
    # Opens 3 weeks before window_end: in-window gross is legitimately far below total.
    rel = season.window_end - timedelta(days=21)
    median, _ = project_preopening(rel, 140_000_000, 400_000_000, "med", 0.55, season)
    assert 140_000_000 < median < 400_000_000

def test_release_before_window_scores_zero(season):
    before = project_preopening(date(2026, 4, 30), 70e6, 200e6, "high", 0.55, season)
    on_open = project_preopening(date(2026, 5, 1), 70e6, 200e6, "high", 0.55, season)
    assert before == (0.0, 0.0)
    assert on_open[0] > 0
