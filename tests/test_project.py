import math
from datetime import date, timedelta
import pytest
from smw.catalog.normalize import Film, Override, PreopeningEstimate
from smw.model.project import Z80, MovieCatalog, bands, build_catalog

TODAY = date(2026, 7, 1)

def _film(title="F", status="in_theaters", gross=0.0, release=date(2026, 5, 1),
          category="wide", estimate=None):
    return Film(title, release, status, category, gross, estimate)

def _catalog(season, films, history=None, picked=None, overrides=None, today=TODAY):
    return build_catalog(season, films, history or {}, picked or set(),
                         overrides or {}, today)

def test_closed_film_is_final_gross(season):
    cat = _catalog(season, [_film(status="closed", gross=500.0)])
    p = cat.projections[0]
    assert (p.median, p.sigma, p.floor, p.source) == (500.0, 0.0, 500.0, "final gross")
    assert p.p10 == p.p90 == 500.0

def test_in_theaters_uses_decay_with_floor(season):
    cat = _catalog(season, [_film(gross=100_000_000.0)])
    p = cat.projections[0]
    assert p.source == "decay model"
    assert p.floor == 100_000_000.0
    assert p.median > p.floor

def test_pre_release_with_complete_estimate(season):
    est = PreopeningEstimate(release_date=date(2026, 8, 1),
                             opening_weekend_estimate=70_000_000,
                             total_domestic_estimate=200_000_000, confidence="high")
    cat = _catalog(season, [_film(status="pre_release", release=date(2026, 8, 1),
                                  estimate=est)])
    p = cat.projections[0]
    assert p.source == "analyst estimate"
    assert p.floor == 0.0
    assert p.median > 0

def test_pre_release_after_window(season):
    est = PreopeningEstimate(release_date=date(2026, 9, 20),
                             opening_weekend_estimate=70_000_000,
                             total_domestic_estimate=200_000_000, confidence="high")
    cat = _catalog(season, [_film(status="pre_release", release=date(2026, 9, 20),
                                  estimate=est)])
    p = cat.projections[0]
    assert (p.median, p.source) == (0.0, "release after window")

def test_pre_release_without_estimate_is_zero_no_fallback(season):
    cat = _catalog(season, [_film(status="pre_release", release=date(2026, 8, 1))])
    p = cat.projections[0]
    assert (p.median, p.sigma, p.floor, p.source) == (0.0, 0.0, 0.0, "no analyst entry")

def test_bands_closed_form():
    p10, p90 = bands(200.0, 0.3, 120.0)
    assert p10 == pytest.approx(120.0 + 80.0 * math.exp(-Z80 * 0.3))
    assert p90 == pytest.approx(120.0 + 80.0 * math.exp(Z80 * 0.3))

def test_warning_for_unclassified_picked_film(season):
    films = [_film(title="Toon", gross=10.0), _film(title="Classified", gross=10.0)]
    cat = _catalog(season, films, picked={"Toon", "Classified"},
                   overrides={"Classified": Override(category="wide")})
    assert any("Toon" in w and "category" in w.lower() for w in cat.warnings)
    assert not any("Classified" in w for w in cat.warnings)

def test_warning_for_picked_film_without_projection(season):
    films = [_film(title="Mystery", status="pre_release", release=date(2026, 8, 1))]
    cat = _catalog(season, films, picked={"Mystery"})
    assert any("Mystery" in w and "no projection" in w.lower() for w in cat.warnings)

def test_observed_history_feeds_blend(season):
    d0 = date(2026, 5, 4)
    history = {"F": [(d0 + timedelta(days=7 * i), [100.0, 180.0, 220.0][i])
                     for i in range(3)]}
    with_hist = _catalog(season, [_film(gross=220.0)], history=history)
    without = _catalog(season, [_film(gross=220.0)])
    assert with_hist.projections[0].median != without.projections[0].median
