from datetime import date
import pytest
from smw.catalog.normalize import Film
from smw.model.project import MovieCatalog, Projection, bands
from smw.model.simulate import simulate
from smw.render.views import build_leaderboard_view, projected_ranks
from smw.score.rules import score_player

TODAY = date(2026, 8, 15)

def _proj(title, median, floor=0.0, source="decay model"):
    p10, p90 = bands(median, 0.2, floor)
    return Projection(title, median, 0.2, floor, source, p10, p90)

def _film(title, gross=0.0, status="in_theaters"):
    return Film(title, date(2026, 5, 1), status, "wide", gross, None)

def _catalog(n=18):
    projs = [_proj(f"M{i:02d}", 400e6 / i, floor=100e6 / i) for i in range(1, n + 1)]
    films = [_film(p.title, gross=p.floor) for p in projs]
    return MovieCatalog(films, projs, [])

def _view(season, group, cat=None, with_sim=True, reason=None):
    cat = cat or _catalog()
    sim = simulate(season, group, cat) if with_sim else None
    actual = [f.title for f in sorted(cat.films, key=lambda f: -f.cumulative_gross)
              if f.cumulative_gross > 0][:10]
    current = {u: score_player(group.players[u], actual) for u in group.players}
    return build_leaderboard_view(season, group, cat, sim, current, actual,
                                  reason, TODAY)

def test_live_mode_shape(season, group):
    v = _view(season, group)
    assert v.mode == "live"
    assert v.heading == "🏆 Projected Standings"
    assert len(v.rows) == season.matrix_rows
    assert v.divider_after == 10
    assert [c.username for c in v.columns] == sorted(
        group.players, key=lambda u: (-_sim_median(season, group)[u], u))

def _sim_median(season, group):
    return simulate(season, group, _catalog()).median_pts

def test_footer_is_arithmetic_sum_of_cells(season, group):
    v = _view(season, group)
    for ci, col in enumerate(v.columns):
        assert col.footer_pts == sum(r.cells[ci].pts for r in v.rows)

def test_cell_states(season, group):
    v = _view(season, group)
    row1 = v.rows[0]           # M01, projected #1
    ci = [c.username for c in v.columns].index("alice")
    assert row1.cells[ci].kind == "pts"
    assert row1.cells[ci].pts == 13    # alice predicted M01 at #1
    row12 = v.rows[11]         # M12: on carol's roster (dark horse), outside top ten
    carol = [c.username for c in v.columns].index("carol")
    assert row12.cells[carol].kind == "zero"
    bob = [c.username for c in v.columns].index("bob")
    assert row12.cells[bob].kind == "none"  # bob never picked M12

def test_projected_ranks_whole_catalog(season):
    ranks = projected_ranks(_catalog())
    assert ranks["M01"] == 1
    assert ranks["M18"] == 18

def test_current_mode_no_forecast_artifacts(season, group):
    v = _view(season, group, with_sim=False, reason="only 3 films have non-zero projections")
    assert v.mode == "current"
    assert v.heading == "🏆 Current Standings"
    assert all(c.win_pct is None for c in v.columns)
    assert "only 3 films" in v.notice
    for d in v.details:
        assert "win" not in d.stats_line
        assert "projected" not in d.stats_line
    # cells are current points vs the actual top ten
    ci = [c.username for c in v.columns].index("alice")
    assert v.columns[ci].footer_pts == sum(r.cells[ci].pts for r in v.rows)

def test_divider_suppressed_with_ten_or_fewer_rows(season, group):
    v = _view(season, group, cat=_catalog(n=10))
    assert v.divider_after is None

def test_missing_picked_film_renders_placeholder(season, group):
    # M15..M18 exist; alice's dark horses M15-17 exist, but strip the catalog to 12
    v = _view(season, group, cat=_catalog(n=12))
    alice = next(d for d in v.details if d.username == "alice")
    assert any(r.missing for r in alice.dark_rows)  # M15+ absent → placeholder, no crash

def test_diff_arrows(season, group):
    v = _view(season, group)
    bob = next(d for d in v.details if d.username == "bob")
    # bob predicted M10 at #1; projection ranks it #10 → diff 1-10 = -9 → ▼
    row = next(r for r in bob.rows if r.title == "M10")
    assert row.diff == -9

def test_empty_roster_set_renders_empty_lists(season):
    from smw.config.groups import Group
    empty = Group("g", "G", {})
    cat = _catalog()
    v = build_leaderboard_view(season, empty, cat, None, {}, [], "r", TODAY)
    assert v.list_rows == [] or all(not d[1] for d in v.list_rows)
    assert v.columns == []
