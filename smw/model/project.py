"""Projection dispatch by status; display bands; operator warnings (spec §7.1, §7.5–7.6, §8)."""
import math
from dataclasses import dataclass
from datetime import date

from smw.catalog.normalize import Film, Override
from smw.config.season import Season
from smw.model.decay import blended_wow, project_decay
from smw.model.preopening import project_preopening

Z80 = 1.2816  # standard normal 90th percentile


@dataclass(frozen=True)
class Projection:
    title: str
    median: float
    sigma: float
    floor: float
    source: str
    p10: float
    p90: float


@dataclass(frozen=True)
class MovieCatalog:
    """Roster-independent pipeline product (§3.4). MUST NOT carry roster data."""
    films: list[Film]
    projections: list[Projection]
    warnings: list[str]


def bands(median: float, sigma: float, floor: float) -> tuple[float, float]:
    remaining = max(0.0, median - floor)
    return (floor + remaining * math.exp(-Z80 * sigma),
            floor + remaining * math.exp(Z80 * sigma))


def _project_one(film: Film, season: Season,
                 history: dict[str, list[tuple[date, float]]], today: date) -> Projection:
    if film.status == "closed":
        median, sigma, floor, source = (film.cumulative_gross, 0.0,
                                        film.cumulative_gross, "final gross")
    elif film.status == "in_theaters":
        wow = blended_wow(history.get(film.title, []), season.default_wow[film.category])
        median, sigma = project_decay(film.cumulative_gross, film.release_date,
                                      wow, season, today)
        floor, source = film.cumulative_gross, "decay model"
    elif film.estimate is not None and film.estimate.is_complete():
        if film.release_date > season.window_end:
            median, sigma, floor, source = 0.0, 0.0, 0.0, "release after window"
        else:
            median, sigma = project_preopening(
                film.release_date,
                film.estimate.opening_weekend_estimate,
                film.estimate.total_domestic_estimate,
                film.estimate.confidence,
                season.default_wow[film.category],
                season,
            )
            floor, source = 0.0, "analyst estimate"
    else:
        # §7.5: no fallback, by design. A visible zero beats a confident guess.
        median, sigma, floor, source = 0.0, 0.0, 0.0, "no analyst entry"
    p10, p90 = bands(median, sigma, floor)
    return Projection(film.title, median, sigma, floor, source, p10, p90)


def build_catalog(
    season: Season,
    films: list[Film],
    history: dict[str, list[tuple[date, float]]],
    picked_titles: set[str],
    overrides: dict[str, Override],
    today: date,
) -> MovieCatalog:
    projections = [_project_one(f, season, history, today) for f in films]

    warnings: list[str] = []
    unclassified = sorted(
        f.title for f in films
        if f.title in picked_titles
        and (f.title not in overrides or overrides[f.title].category is None)
    )
    if unclassified:
        warnings.append(
            "Picked films with no explicit category (defaulting to wide — §8): "
            + ", ".join(unclassified)
        )
    proj_by_title = {p.title: p for p in projections}
    no_projection = sorted(
        t for t in picked_titles
        if t in proj_by_title and proj_by_title[t].source == "no analyst entry"
    )
    if no_projection:
        warnings.append(
            "Picked films with no projection (add analyst estimates — §7.5): "
            + ", ".join(no_projection)
        )
    return MovieCatalog(films=films, projections=projections, warnings=warnings)
