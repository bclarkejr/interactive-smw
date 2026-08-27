from datetime import date
import pytest
from smw.catalog.normalize import Film
from smw.config.groups import Group, PlayerPicks
from smw.model.project import MovieCatalog, Projection, bands
from smw.model.simulate import simulate
from smw.score.rules import score_player

def _proj(title, median, sigma=0.2, floor=0.0):
    p10, p90 = bands(median, sigma, floor)
    return Projection(title, median, sigma, floor, "decay model", p10, p90)

def _film(title):
    return Film(title, date(2026, 5, 1), "in_theaters", "wide", 0.0, None)

def _catalog(n=18):
    projs = [_proj(f"M{i:02d}", 400_000_000.0 / i) for i in range(1, n + 1)]
    return MovieCatalog([_film(p.title) for p in projs], projs, [])

@pytest.fixture
def hopeless_group(group):
    # dave picks films that essentially never chart → no winning path
    players = dict(group.players)
    players["dave"] = PlayerPicks(
        "dave", tuple(f"Z{i}" for i in range(10)), ("Z10", "Z11", "Z12"))
    return Group(group.group_id, group.display_name, players)

def test_scenario_structure(season, group):
    r = simulate(season, group, _catalog())
    s = r.scenarios["alice"]
    assert s is not None
    assert len(s.films) == 10 and len(set(s.films)) == 10
    for u in group.players:
        assert len(s.grid[u]) == 10
        # grid rows are the score breakdown of a REAL trial: totals must agree
        assert sum(s.grid[u]) == s.totals[u]
        assert s.totals[u] == score_player(group.players[u], s.films)
    assert s.win_pct == pytest.approx(r.win_prob["alice"] * 100, abs=0.1)

def test_winner_actually_wins_with_margin(season, group):
    r = simulate(season, group, _catalog())
    s = r.scenarios["alice"]
    others = [v for u, v in s.totals.items() if u != "alice"]
    assert s.totals["alice"] - max(others) == s.margin
    assert s.margin >= 1

def test_player_with_no_path_gets_none(season, hopeless_group):
    r = simulate(season, hopeless_group, _catalog())
    assert r.scenarios["dave"] is None

def test_scenarios_reproducible(season, group):
    a = simulate(season, group, _catalog())
    b = simulate(season, group, _catalog())
    assert a.scenarios["alice"].films == b.scenarios["alice"].films
