"""Monte Carlo season simulation (spec §9)."""
from dataclasses import dataclass

import numpy as np

from smw.config.groups import Group
from smw.config.season import Season
from smw.model.project import MovieCatalog, Projection
from smw.score.rules import score_breakdown, score_player

MIN_FILMS_FOR_TOP_TEN = 10  # structural: you cannot rank a top ten out of nine films
_MEDOID_CAP = 1500


class SimulationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Scenario:
    films: list[str]
    grid: dict[str, list[int]]
    totals: dict[str, int]
    win_pct: float
    margin: int


@dataclass(frozen=True)
class SimResult:
    win_prob: dict[str, float]
    tie_prob: dict[str, float]
    median_pts: dict[str, float]
    p10_pts: dict[str, float]
    p90_pts: dict[str, float]
    scenarios: dict[str, "Scenario | None"]


def _sample(season: Season, projections: list[Projection]) -> np.ndarray:
    """Vectorized (trials, films) sampling. Uncertainty applies only to money
    not yet banked, so a sample can never fall below the floor (§9.2)."""
    medians = np.array([p.median for p in projections])
    sigmas = np.array([p.sigma for p in projections])
    floors = np.array([p.floor for p in projections])
    rng = np.random.default_rng(season.seed)
    z = rng.standard_normal((season.monte_carlo_trials, len(projections)))
    return floors + np.maximum(0.0, medians - floors) * np.exp(sigmas * z)


def simulate(season: Season, group: Group, catalog: MovieCatalog) -> SimResult:
    projected = [p for p in catalog.projections if p.median > 0]
    if len(projected) < MIN_FILMS_FOR_TOP_TEN:
        raise SimulationError(
            f"only {len(projected)} films have projections; "
            f"{MIN_FILMS_FOR_TOP_TEN} are required to rank a top ten"
        )
    titles = [p.title for p in projected]
    samples = _sample(season, projected)
    top10 = np.argsort(-samples, axis=1)[:, :10]          # (trials, 10) film indices

    players = sorted(group.players)
    trials = season.monte_carlo_trials
    score_matrix = np.zeros((len(players), trials), dtype=np.int64)
    for t in range(trials):
        finish = [titles[i] for i in top10[t]]
        for pi, u in enumerate(players):
            score_matrix[pi, t] = score_player(group.players[u], finish)

    max_per_trial = score_matrix.max(axis=0)
    is_top = score_matrix == max_per_trial
    winners_per_trial = is_top.sum(axis=0)

    win_prob, tie_prob, med, p10, p90 = {}, {}, {}, {}, {}
    for pi, u in enumerate(players):
        strict = (is_top[pi] & (winners_per_trial == 1)).sum()
        ties = (is_top[pi] & (winners_per_trial > 1)).sum()
        win_prob[u] = strict / trials
        tie_prob[u] = ties / trials
        med[u], p10[u], p90[u] = (
            float(np.percentile(score_matrix[pi], q)) for q in (50, 10, 90)
        )

    scenarios = _scenarios(season, group, players, titles, top10,
                           score_matrix, is_top, winners_per_trial, win_prob)
    return SimResult(win_prob, tie_prob, med, p10, p90, scenarios)


def _scenarios(season, group, players, titles, top10,
               score_matrix, is_top, winners_per_trial, win_prob):
    out: dict[str, Scenario | None] = {}
    n_films = len(titles)
    for pi, u in enumerate(players):
        wins = np.flatnonzero(is_top[pi] & (winners_per_trial == 1))
        if wins.size == 0:
            out[u] = None
            continue
        # Per-player derived seed keeps scenarios reproducible (§9.6).
        prng = np.random.default_rng([season.seed, pi])
        if wins.size > _MEDOID_CAP:
            wins = np.sort(prng.choice(wins, _MEDOID_CAP, replace=False))
        # Spearman-footrule rank vectors: top-ten position 1–10, absentees 11,
        # so films missing from both trials contribute zero distance.
        R = np.full((wins.size, n_films), 11, dtype=np.int16)
        rows = np.arange(wins.size)[:, None]
        R[rows, top10[wins]] = np.arange(1, 11)[None, :]
        # ponytail: O(W) python loop over an O(W*F) numpy op instead of one giant
        # (W,W,F) broadcast — 1500² pairs would need ~9 GB broadcast at once.
        dist_sums = np.array([np.abs(R - R[j]).sum() for j in range(wins.size)])
        best_trial = int(wins[int(np.argmin(dist_sums))])

        finish = [titles[i] for i in top10[best_trial]]
        grid = {}
        for v in players:
            b = score_breakdown(group.players[v], finish)
            grid[v] = (b + [0] * 10)[:10]
        totals = {v: int(score_matrix[players.index(v), best_trial]) for v in players}
        margin = totals[u] - max(t for v, t in totals.items() if v != u)
        out[u] = Scenario(films=finish, grid=grid, totals=totals,
                          win_pct=round(win_prob[u] * 100, 1), margin=margin)
    return out
