import pytest
from smw.config.groups import PlayerPicks
from smw.score.rules import ranked_pick_points, score_breakdown, score_player

PICKS = PlayerPicks(
    username="alice",
    ranked=tuple(f"M{i:02d}" for i in range(1, 11)),  # M01 predicted #1 ... M10 predicted #10
    dark_horses=("D1", "D2", "D3"),
)

@pytest.mark.parametrize("predicted,actual,expected", [
    (1, None, 0),        # not in top ten
    (1, 1, 13),          # exact endpoint, top
    (10, 10, 13),        # exact endpoint, bottom
    (2, 2, 10),          # exact middle
    (9, 9, 10),          # exact middle, other edge
    (3, 4, 7),           # off by one
    (3, 2, 7),           # off by one, other direction
    (3, 5, 5),           # off by two
    (1, 4, 3),           # off by three
    (1, 10, 3),          # off by nine
])
def test_ranked_pick_points(predicted, actual, expected):
    assert ranked_pick_points(predicted, actual) == expected

def test_perfect_season_scores_109():
    finish = list(PICKS.ranked)
    # Dark horses can't also be ranked picks; use a roster whose dark horses miss.
    assert score_player(PICKS, finish) == 13 + 10 * 8 + 13

def test_dark_horse_scores_one_at_any_position():
    finish = ["D1"] + [f"X{i}" for i in range(8)] + ["D2"]  # D1 at #1, D2 at #10
    assert score_player(PICKS, finish) == 2

def test_over_length_finish_raises():
    with pytest.raises(ValueError):
        score_breakdown(PICKS, [f"X{i}" for i in range(11)])

def test_partial_finish_scores_only_present_positions():
    finish = ["M01", "M02", "M03"]  # only three films have grossed anything
    b = score_breakdown(PICKS, finish)
    assert len(b) == 3
    assert b == [13, 10, 10]

def test_empty_finish_scores_zero():
    assert score_player(PICKS, []) == 0
    assert score_breakdown(PICKS, []) == []

def test_breakdown_sums_to_total():
    finish = ["M05", "D1", "M01", "M02", "X1", "M10", "X2", "M03", "D2", "M09"]
    assert sum(score_breakdown(PICKS, finish)) == score_player(PICKS, finish)

def test_breakdown_is_indexed_by_actual_position():
    finish = ["M03", "M01"]  # M03 (predicted 3) finishes #1; M01 (predicted 1) finishes #2
    b = score_breakdown(PICKS, finish)
    assert b[0] == ranked_pick_points(3, 1)  # points the #1 finisher contributes
    assert b[1] == ranked_pick_points(1, 2)
