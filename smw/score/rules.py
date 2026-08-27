"""The whole of the game's scoring rules (spec §2). Depends only on the roster type."""
from typing import Sequence

from smw.config.groups import PlayerPicks


def ranked_pick_points(predicted: int, actual: int | None) -> int:
    if actual is None:
        return 0
    distance = abs(predicted - actual)
    if distance == 0:
        return 13 if actual in (1, 10) else 10
    if distance == 1:
        return 7
    if distance == 2:
        return 5
    return 3


def score_breakdown(picks: PlayerPicks, top_titles: Sequence[str]) -> list[int]:
    if len(top_titles) > 10:
        raise ValueError(f"top ten cannot have {len(top_titles)} entries")
    position_of = {title: i + 1 for i, title in enumerate(top_titles)}
    breakdown = [0] * len(top_titles)
    for predicted, title in enumerate(picks.ranked, start=1):
        pos = position_of.get(title)
        if pos:
            breakdown[pos - 1] += ranked_pick_points(predicted, pos)
    for title in picks.dark_horses:
        pos = position_of.get(title)
        if pos:
            breakdown[pos - 1] += 1
    return breakdown


def score_player(picks: PlayerPicks, top_titles: Sequence[str]) -> int:
    return sum(score_breakdown(picks, top_titles))
