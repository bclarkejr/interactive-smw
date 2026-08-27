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
    return [replace(r, title=canonical(r.title, overrides)) for r in rows]


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
