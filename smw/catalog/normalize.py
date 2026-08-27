"""Catalog normalization: overrides, aliases, analyst estimates, film records (spec §5.3–5.4, §6.2, §6.5)."""
from dataclasses import dataclass, fields, replace
from datetime import date
from pathlib import Path

import yaml

from smw.config.groups import Group
from smw.config.season import Season
from smw.ingest.boxoffice import ChartRow

_OVERRIDE_KEYS = {"category", "alias_of", "release_date", "status"}
_CATEGORIES = {"wide", "animated_family"}
_STATUSES = {"pre_release", "in_theaters", "closed"}
_CONFIDENCES = {"high", "med", "low"}


@dataclass(frozen=True)
class Override:
    category: str | None = None
    alias_of: str | None = None
    release_date: date | None = None
    status: str | None = None


def load_overrides(path: Path) -> dict[str, Override]:
    path = Path(path)
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text()) or {}
    out: dict[str, Override] = {}
    for title, fields_ in raw.items():
        fields_ = fields_ or {}
        unknown = set(fields_) - _OVERRIDE_KEYS
        if unknown:
            raise ValueError(f"{path}: '{title}' has unknown key(s): {', '.join(sorted(unknown))}")
        cat, status = fields_.get("category"), fields_.get("status")
        if cat is not None and cat not in _CATEGORIES:
            raise ValueError(f"{path}: '{title}' category must be one of {sorted(_CATEGORIES)}")
        if status is not None and status not in _STATUSES:
            raise ValueError(f"{path}: '{title}' status must be one of {sorted(_STATUSES)}")
        out[title] = Override(**fields_)
    return out


def canonical(title: str, overrides: dict[str, Override]) -> str:
    ov = overrides.get(title)
    return ov.alias_of if ov and ov.alias_of else title


def apply_chart_aliases(rows: list[ChartRow], overrides: dict[str, Override]) -> list[ChartRow]:
    """Alias application point 1 (§6.5) plus release-date corrections, both keyed on the
    upstream title — applied BEFORE the window filter so a bad upstream date can be rescued."""
    out = []
    for r in rows:
        ov = overrides.get(r.title) or overrides.get(canonical(r.title, overrides))
        out.append(replace(
            r, title=canonical(r.title, overrides),
            release_date=ov.release_date if ov and ov.release_date else r.release_date))
    return out


@dataclass(frozen=True)
class PreopeningEstimate:
    release_date: date | None = None
    opening_weekend_estimate: float | None = None
    total_domestic_estimate: float | None = None
    confidence: str | None = None
    source: str = ""
    as_of: date | None = None
    notes: str = ""

    def is_complete(self) -> bool:
        return (
            self.opening_weekend_estimate is not None and self.opening_weekend_estimate > 0
            and self.total_domestic_estimate is not None and self.total_domestic_estimate > 0
            and self.confidence in _CONFIDENCES
        )


def load_preopening(path: Path) -> dict[str, PreopeningEstimate]:
    path = Path(path)
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text()) or {}
    out: dict[str, PreopeningEstimate] = {}
    known = {f.name for f in fields(PreopeningEstimate)}
    for title, fields_ in raw.items():
        fields_ = fields_ or {}
        conf = fields_.get("confidence")
        if conf is not None and conf not in _CONFIDENCES:
            raise ValueError(f"{path}: '{title}' confidence must be one of {sorted(_CONFIDENCES)}")
        unknown = set(fields_) - known
        if unknown:
            raise ValueError(f"{path}: '{title}' has unknown key(s): {', '.join(sorted(unknown))}")
        out[title] = PreopeningEstimate(**fields_)
    return out


@dataclass(frozen=True)
class Film:
    title: str
    release_date: date
    status: str          # pre_release | in_theaters | closed
    category: str        # wide | animated_family
    cumulative_gross: float
    estimate: "PreopeningEstimate | None"


def build_films(
    season: Season,
    groups: list[Group],
    chart_rows: list[ChartRow],
    grosses: dict[str, float],
    carried: set[str],
    overrides: dict[str, Override],
    preopening: dict[str, PreopeningEstimate],
    today: date,
) -> list[Film]:
    chart_by_title = {r.title: r for r in chart_rows}

    # §6.2 candidate set: rosters ∪ estimate keys ∪ top chart contenders ∪ carried.
    candidates: set[str] = set()
    for g in groups:
        for p in g.players.values():
            candidates.update(canonical(t, overrides) for t in p.ranked + p.dark_horses)
    candidates.update(canonical(t, overrides) for t in preopening)
    top_chart = sorted(chart_rows, key=lambda r: -r.gross)[: season.chart_contenders]
    candidates.update(r.title for r in top_chart)
    candidates.update(carried)

    pre_canon = {canonical(t, overrides): e for t, e in preopening.items()}

    films: list[Film] = []
    for title in sorted(candidates):
        ov = overrides.get(title)
        est = pre_canon.get(title)
        gross = grosses.get(title, 0.0)
        row = chart_by_title.get(title)

        # Release-date precedence: override → chart → estimates → today (if grossing) → window_end.
        if ov and ov.release_date:
            release = ov.release_date
        elif row:
            release = row.release_date
        elif est and est.release_date:
            release = est.release_date
        elif gross > 0:
            release = today
        else:
            release = season.window_end

        # Status inference, in spec order.
        if ov and ov.status:
            status = ov.status
        elif release > today:
            status = "pre_release"
        elif gross > 0 and title not in chart_by_title:
            status = "closed"
        elif gross > 0:
            status = "in_theaters"
        else:
            status = "pre_release"

        category = ov.category if ov and ov.category else "wide"
        films.append(Film(title=title, release_date=release, status=status,
                          category=category, cumulative_gross=gross, estimate=est))
    return films


def canonical_group(group: Group, overrides: dict[str, Override]) -> Group:
    """Alias application point 2 (§6.5) for rosters: every pick is resolved to its
    canonical title so scoring compares like with like."""
    from dataclasses import replace as _replace  # local: keeps the module header stable
    players = {}
    for u, p in group.players.items():
        ranked = tuple(canonical(t, overrides) for t in p.ranked)
        dark = tuple(canonical(t, overrides) for t in p.dark_horses)
        if len(set(ranked + dark)) != 13:
            dupes = sorted({t for t in ranked + dark if (ranked + dark).count(t) > 1})
            raise ValueError(
                f"{u}: alias_of collapses picks onto the same film: {', '.join(dupes)} "
                "— all 13 titles must stay distinct after alias resolution")
        players[u] = _replace(p, ranked=ranked, dark_horses=dark)
    return _replace(group, players=players)
