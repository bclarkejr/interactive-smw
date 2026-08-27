"""Mode B: pre-release projection from analyst estimates over a finite run (spec §7.4)."""
from datetime import date

from smw.config.season import Season
from smw.model.decay import DOW_WEIGHTS, day_weight

# Fri+Sat+Sun share of a week. Derived, not a literal: if DOW_WEIGHTS ever change,
# this MUST change with them (§7.4).
OPENING_WEEK_SHARE = sum(DOW_WEIGHTS[4:7])

CONFIDENCE_SIGMA = {"high": 0.20, "med": 0.30, "low": 0.45}


def derive_wow(opening: float, total: float, n_weeks: int, fallback: float) -> float:
    week_1 = opening / OPENING_WEEK_SHARE

    def run_total(w: float) -> float:
        return week_1 * (1 - w ** n_weeks) / (1 - w)

    lo, hi = 1e-9, 1 - 1e-9
    # run_total is strictly increasing on (0,1): week_1 at w→0, n_weeks*week_1 at w→1.
    if not (run_total(lo) < total < run_total(hi)):
        return fallback
    for _ in range(60):
        mid = (lo + hi) / 2
        if run_total(mid) < total:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def project_preopening(
    release_date: date,
    opening: float,
    total: float,
    confidence: str,
    category_wow: float,
    season: Season,
) -> tuple[float, float]:
    if release_date > season.window_end:
        return 0.0, 0.0
    w = derive_wow(opening, total, season.preopening_run_weeks, category_wow)
    week_1 = opening / OPENING_WEEK_SHARE
    in_window_days = (season.window_end - release_date).days + 1
    run_days = season.preopening_run_weeks * 7
    gross = sum(
        week_1 * w ** (d // 7) * day_weight(release_date, d)
        for d in range(min(in_window_days, run_days))
    )
    return min(gross, total), CONFIDENCE_SIGMA[confidence]
