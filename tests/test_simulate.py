from datetime import date
import numpy as np
import pytest
from smw.catalog.normalize import Film
from smw.model.project import MovieCatalog, Projection, bands
from smw.model.simulate import MIN_FILMS_FOR_TOP_TEN, SimulationError, simulate

def _proj(title, median, sigma=0.2, floor=0.0):
    p10, p90 = bands(median, sigma, floor)
    return Projection(title, median, sigma, floor, "decay model", p10, p90)

def _film(title):
    return Film(title, date(2026, 5, 1), "in_theaters", "wide", 0.0, None)

def _catalog(n=18):
    # M01 strongest ... M18 weakest, comfortable spacing
    projs = [_proj(f"M{i:02d}", 400_000_000.0 / i) for i in range(1, n + 1)]
    return MovieCatalog([_film(p.title) for p in projs], projs, [])

def test_fewer_than_ten_projected_films_raises(season, group):
    projs = [_proj(f"M{i:02d}", 100.0) for i in range(1, 9)] + [_proj("M09", 0.0)]
    cat = MovieCatalog([_film(p.title) for p in projs], projs, [])
    with pytest.raises(SimulationError):
        simulate(season, group, cat)

def test_deterministic_under_seed(season, group):
    a = simulate(season, group, _catalog())
    b = simulate(season, group, _catalog())
    assert a.win_prob == b.win_prob
    assert a.median_pts == b.median_pts

def test_percentile_ordering(season, group):
    r = simulate(season, group, _catalog())
    for u in group.players:
        assert r.p10_pts[u] <= r.median_pts[u] <= r.p90_pts[u]

def test_win_plus_tie_at_most_one_and_probs_sum(season, group):
    r = simulate(season, group, _catalog())
    for u in group.players:
        assert r.win_prob[u] + r.tie_prob[u] <= 1.0 + 1e-9
    # strict-win probs across players + fraction of tied trials == 1
    # (every trial has either exactly one strict winner or a tie for first)
    strict_total = sum(r.win_prob.values())
    any_tie = 1.0 - strict_total
    assert any_tie >= -1e-9
    tied_players_bound = sum(r.tie_prob.values())
    assert tied_players_bound >= any_tie * 2 - 1e-9  # a tie involves ≥ 2 players

def test_floor_is_never_breached(season, group, monkeypatch):
    # §9.2: assert min(samples) >= floor over a full trial run.
    import smw.model.simulate as sim
    captured = {}
    orig = sim._sample
    def spy(season_, projections):
        s = orig(season_, projections)
        captured["samples"] = s
        captured["floors"] = np.array([p.floor for p in projections])
        return s
    monkeypatch.setattr(sim, "_sample", spy)
    projs = [_proj(f"M{i:02d}", 400_000_000.0 / i, sigma=0.4,
                   floor=200_000_000.0 / i) for i in range(1, 15)]
    cat = MovieCatalog([_film(p.title) for p in projs], projs, [])
    simulate(season, group, cat)
    assert (captured["samples"] >= captured["floors"][None, :] - 1e-6).all()

def test_dominant_player_wins(season, group):
    # alice picked M01..M10 in order == projection order; she must dominate.
    r = simulate(season, group, _catalog())
    assert r.win_prob["alice"] > 0.9
