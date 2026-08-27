"""Mode A: geometric weekly decay anchored to observed cumulative gross (spec §7.2–7.3)."""
import math
from datetime import date

from smw.config.season import Season

DOW_WEIGHTS = (0.07, 0.10, 0.07, 0.06, 0.22, 0.26, 0.22)  # Mon..Sun, sums to 1.00


def day_weight(release_date: date, d: int) -> float:
    if d // 7 == 0:
        return DOW_WEIGHTS[(release_date.weekday() + d) % 7]
    return 1 / 7


def decay_sigma(weeks_observed: int) -> float:
    if weeks_observed >= 6:
        return 0.10
    if weeks_observed <= 0:
        return 0.30
    return 0.30 - 0.20 * weeks_observed / 6


def blended_wow(observations: list[tuple[date, float]], default: float) -> float:
    if len(observations) < 2:
        return default
    grosses = [g for _, g in observations]
    deltas = [b - a for a, b in zip(grosses, grosses[1:])]
    ratios = [
        deltas[i + 1] / deltas[i]
        for i in range(len(deltas) - 1)
        if deltas[i] > 0 and deltas[i + 1] > 0
    ]
    if not ratios:
        return default
    observed = math.prod(ratios) ** (1 / len(ratios))
    weight = min(1.0, (len(observations) - 1) / 5.0)
    blended = weight * observed + (1 - weight) * default
    # §7.3 [Changed]: unclamped, one anomalous growing pair compounds upward to
    # window_end and distorts the whole top ten. A sustained WoW > 1.0 is not real.
    return min(max(blended, 0.01), 1.00)


def project_decay(
    cumulative: float, release_date: date, wow: float, season: Season, today: date
) -> tuple[float, float]:
    if today < release_date:
        raise ValueError("decay model requires a released film")
    elapsed = (today - release_date).days
    sigma = decay_sigma(elapsed // 7)
    if today >= season.window_end:
        return cumulative, sigma

    end_days = (season.window_end - release_date).days + 1  # window_end inclusive
    if elapsed == 0:
        # Degenerate same-day case: cumulative IS week one; project from week two.
        week_1 = cumulative
        start = 7
    else:
        denom = sum(wow ** (d // 7) * day_weight(release_date, d) for d in range(elapsed))
        week_1 = cumulative / denom
        start = elapsed
    remaining = sum(
        week_1 * wow ** (d // 7) * day_weight(release_date, d)
        for d in range(start, end_days)
    )
    return cumulative + remaining, sigma
