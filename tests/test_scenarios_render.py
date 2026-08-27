from datetime import date
import pytest
from smw.config.groups import Group, PlayerPicks
from smw.model.simulate import simulate
from smw.render.page import base_context, build_scenarios_view, make_env, render_scenarios
from tests.test_views import _catalog

TODAY = date(2026, 8, 15)

@pytest.fixture
def sim(season, group):
    return simulate(season, group, _catalog())

def test_tabs_ordered_by_win_prob(group, sim):
    tabs = build_scenarios_view(group, sim)
    probs = [sim.win_prob[t["username"]] for t in tabs]
    assert probs == sorted(probs, reverse=True)

def test_winner_column_leftmost(group, sim):
    tabs = build_scenarios_view(group, sim)
    top = tabs[0]
    assert top["scenario"] is not None
    cols = top["scenario"]["columns"]
    totals = top["scenario"]["totals"]
    assert cols[0] == top["username"]          # winner sits leftmost
    assert totals == sorted(totals, reverse=True)

def test_grid_is_ten_rows_and_consistent(group, sim):
    s = build_scenarios_view(group, sim)[0]["scenario"]
    assert len(s["rows"]) == 10
    for ci in range(len(s["columns"])):
        assert sum(r["cells"][ci] for r in s["rows"]) == s["totals"][ci]

def test_no_path_player_disabled(season, group):
    players = dict(group.players)
    players["dave"] = PlayerPicks("dave", tuple(f"Z{i}" for i in range(10)),
                                  ("Z10", "Z11", "Z12"))
    hopeless = Group(group.group_id, group.display_name, players)
    sim = simulate(season, hopeless, _catalog())
    tabs = build_scenarios_view(hopeless, sim)
    dave = next(t for t in tabs if t["username"] == "dave")
    assert dave["scenario"] is None

def _render(tmp_path, season, group, tabs, reason=None):
    env = make_env()
    ctx = base_context(season, group, "scenarios", TODAY)
    render_scenarios(env, tmp_path, ctx, tabs, reason)
    return (tmp_path / "scenarios.html").read_text()

def test_rendered_page(tmp_path, season, group, sim):
    html = _render(tmp_path, season, group, build_scenarios_view(group, sim))
    assert "aria-pressed" in html
    assert "crowns them champion" in html
    assert "http://" not in html and "https://" not in html

def test_zero_cells_render_middle_dot_and_no_path_disabled(tmp_path, season, group):
    tabs = [
        {"username": "alice", "win_pct": 50.0, "scenario": {
            "caption": "cap", "columns": ["alice", "bob", "carol"],
            "rows": [{"title": f"T{i}", "cells": [10, 0, 3]} for i in range(10)],
            "totals": [100, 0, 30]}},
        {"username": "bob", "win_pct": 0.0, "scenario": None},
    ]
    html = _render(tmp_path, season, group, tabs)
    assert "·" in html          # zero cells as middle dot
    assert "disabled" in html   # genuinely disabled no-path button

def test_locked_state(tmp_path, season, group):
    html = _render(tmp_path, season, group, None, "only 3 films have projections")
    assert "unlocks once the forecast is live" in html
