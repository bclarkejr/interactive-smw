"""Leaderboard view models. All ordering and arithmetic happens HERE; templates
are pure functions of these dataclasses (spec §11.4)."""
from dataclasses import dataclass
from datetime import date

from smw.config.groups import Group, PlayerPicks
from smw.config.season import Season
from smw.model.project import MovieCatalog
from smw.model.simulate import SimResult
from smw.score.rules import ranked_pick_points

BADGES = {"pre_release": "pre-release", "in_theaters": "in theaters", "closed": "closed"}


@dataclass(frozen=True)
class Cell:
    kind: str  # pts | zero | none
    pts: int


@dataclass(frozen=True)
class MatrixRow:
    rank: int
    title: str
    gross: float
    cells: list[Cell]


@dataclass(frozen=True)
class PlayerColumn:
    username: str
    footer_pts: int
    win_pct: float | None


@dataclass(frozen=True)
class DetailRow:
    label: str
    title: str
    projected_rank: int | None
    diff: int | None
    gross: float | None
    pts: int
    missing: bool


@dataclass(frozen=True)
class PlayerDetail:
    username: str
    stats_line: str
    rows: list[DetailRow]
    dark_rows: list[DetailRow]


@dataclass(frozen=True)
class FilmRow:
    rank: int | None
    title: str
    released: str
    badge: str
    median: float
    p10: float
    p90: float
    cumulative: float
    source: str


@dataclass(frozen=True)
class LeaderboardView:
    mode: str
    heading: str
    columns: list[PlayerColumn]
    rows: list[MatrixRow]
    divider_after: int | None
    list_rows: list[tuple[str, dict[str, str]]]
    details: list[PlayerDetail]
    films: list[FilmRow]
    notice: str | None


def projected_ranks(catalog: MovieCatalog) -> dict[str, int]:
    """The system's single notion of 'projected rank' (§12.1): position across the
    whole catalog by median, positive medians only."""
    ordered = sorted((p for p in catalog.projections if p.median > 0),
                     key=lambda p: (-p.median, p.title))
    return {p.title: i + 1 for i, p in enumerate(ordered)}


def _pick_points(picks: PlayerPicks, title: str, top_titles: list[str]) -> Cell:
    """Cell for one film × one player against a finish order."""
    pos = top_titles.index(title) + 1 if title in top_titles else None
    if title in picks.ranked:
        if pos is None:
            return Cell("zero", 0)
        return Cell("pts", ranked_pick_points(picks.ranked.index(title) + 1, pos))
    if title in picks.dark_horses:
        return Cell("pts", 1) if pos is not None else Cell("zero", 0)
    return Cell("none", 0)


def _film_rows(catalog: MovieCatalog, ranks: dict[str, int]) -> list[FilmRow]:
    proj_by_title = {p.title: p for p in catalog.projections}
    ordered = sorted(catalog.films,
                     key=lambda f: (ranks.get(f.title, 10**6), f.title))
    rows = []
    for f in ordered:
        p = proj_by_title[f.title]
        if p.source in ("release after window", "release before window"):
            badge = "won't score"
        elif p.source == "no analyst entry":
            badge = "no projection"
        else:
            badge = BADGES[f.status]
        rows.append(FilmRow(ranks.get(f.title), f.title, f.release_date.strftime("%b %-d"),
                            badge, p.median, p.p10, p.p90, f.cumulative_gross, p.source))
    return rows


def _list_rows(group: Group, order: list[str]) -> list[tuple[str, dict[str, str]]]:
    if not group.players:
        return []
    rows = []
    for i in range(10):
        rows.append((f"Pick {i + 1}",
                     {u: group.players[u].ranked[i] for u in order}))
    for i in range(3):
        rows.append((f"🐴 {i + 1}",
                     {u: group.players[u].dark_horses[i] for u in order}))
    return rows


def _details(group, order, top_titles, catalog_titles, ranks, medians, mode,
             footer, current_points, sim):
    details = []
    for u in order:
        picks = group.players[u]
        rows, dark = [], []
        for kind, titles in (("ranked", picks.ranked), ("dark", picks.dark_horses)):
            for i, t in enumerate(titles):
                missing = t not in catalog_titles
                rank = ranks.get(t)
                predicted = i + 1 if kind == "ranked" else None
                diff = (predicted - rank) if (predicted and rank) else None
                pts = _pick_points(picks, t, top_titles).pts if not missing else 0
                row = DetailRow(
                    label=str(i + 1) if kind == "ranked" else "🐴",
                    title=t, projected_rank=rank, diff=diff,
                    gross=medians.get(t), pts=pts, missing=missing)
                (rows if kind == "ranked" else dark).append(row)
        if mode == "live":
            stats = (f"— {footer[u]} pts projected · {current_points.get(u, 0)} current"
                     f" · {sim.win_prob[u] * 100:.1f}% win")
        else:
            stats = f"— {current_points.get(u, 0)} pts current"
        details.append(PlayerDetail(u, stats, rows, dark))
    return details


def build_leaderboard_view(
    season: Season,
    group: Group,
    catalog: MovieCatalog,
    sim: SimResult | None,
    current_points: dict[str, int],
    actual_top: list[str],
    reason: str | None,
    today: date,
) -> LeaderboardView:
    ranks = projected_ranks(catalog)
    medians = {p.title: p.median for p in catalog.projections}
    grosses = {f.title: f.cumulative_gross for f in catalog.films}
    catalog_titles = {f.title for f in catalog.films}
    mode = "live" if sim is not None else "current"

    if mode == "live":
        row_titles = [t for t, r in sorted(ranks.items(), key=lambda kv: kv[1])
                      ][: season.matrix_rows]
        top_titles = row_titles[:10]
        order = sorted(group.players, key=lambda u: (-sim.median_pts[u], u))
        row_values = medians
    else:
        by_gross = sorted((f for f in catalog.films if f.cumulative_gross > 0),
                          key=lambda f: (-f.cumulative_gross, f.title))
        row_titles = [f.title for f in by_gross][: season.matrix_rows]
        top_titles = list(actual_top)
        order = sorted(group.players, key=lambda u: (-current_points.get(u, 0), u))
        row_values = grosses

    rows = [
        MatrixRow(i + 1, t, row_values.get(t, 0.0),
                  [_pick_points(group.players[u], t, top_titles) for u in order])
        for i, t in enumerate(row_titles)
    ]
    # §12.1 footer total rule — do not re-litigate: the footer is the arithmetic sum
    # of the cells above it, NOT sim.median_pts. A distribution's median is not the
    # median scenario's score; a column that doesn't add up reads as a bug.
    footer = {u: sum(r.cells[ci].pts for r in rows)
              for ci, u in enumerate(order)}
    columns = [
        PlayerColumn(u, footer[u],
                     round(sim.win_prob[u] * 100, 1) if sim else None)
        for u in order
    ]

    notice = None
    if mode == "current" and reason:
        notice = (f"The forecast is unavailable — {reason}. Every number below is a "
                  "real, current figure; projections return once enough films have them.")

    return LeaderboardView(
        mode=mode,
        heading="🏆 Projected Standings" if mode == "live" else "🏆 Current Standings",
        columns=columns,
        rows=rows,
        divider_after=10 if len(rows) > 10 else None,
        list_rows=_list_rows(group, order),
        details=_details(group, order, top_titles, catalog_titles, ranks, medians,
                         mode, footer, current_points, sim),
        films=_film_rows(catalog, ranks),
        notice=notice,
    )
