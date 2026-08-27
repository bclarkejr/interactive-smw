from dataclasses import dataclass, field, fields, replace
from datetime import date
from pathlib import Path

import yaml

from smw.config.groups import Group, load_group

_REQUIRED = ("year", "window_start", "window_end", "seed")


@dataclass(frozen=True)
class Season:
    year: int
    window_start: date
    window_end: date
    seed: int
    min_projections_for_forecast: int = 25
    chart_contenders: int = 25
    matrix_rows: int = 15
    monte_carlo_trials: int = 10000
    preopening_run_weeks: int = 10
    default_wow: dict[str, float] = field(
        default_factory=lambda: {"wide": 0.55, "animated_family": 0.65}
    )
    default_group: str | None = None


def load_season(path: Path) -> Season:
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a mapping")
    missing = [k for k in _REQUIRED if k not in raw]
    if missing:
        raise ValueError(f"{path}: missing required key(s): {', '.join(missing)}")
    unknown = set(raw) - {f.name for f in fields(Season)}
    if unknown:
        raise ValueError(f"{path}: unknown key(s): {', '.join(sorted(unknown))}")
    season = Season(**raw)
    _validate(season, str(path))
    return season


def _validate(s: Season, where: str) -> None:
    """Fail at the load boundary, not deep in simulation (zero trials → NumPy error,
    missing category → KeyError at projection time)."""
    for name in ("window_start", "window_end"):
        if not isinstance(getattr(s, name), date):
            raise ValueError(f"{where}: {name} must be a date")
    if s.window_start > s.window_end:
        raise ValueError(f"{where}: window_start is after window_end")
    for name in ("year", "seed"):
        if not isinstance(getattr(s, name), int) or isinstance(getattr(s, name), bool):
            raise ValueError(f"{where}: {name} must be an integer")
    for name in ("min_projections_for_forecast", "chart_contenders", "matrix_rows",
                 "monte_carlo_trials", "preopening_run_weeks"):
        v = getattr(s, name)
        if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
            raise ValueError(f"{where}: {name} must be a positive integer")
    if s.matrix_rows < 10:
        raise ValueError(f"{where}: matrix_rows must be at least 10 (the scored top ten)")
    if not isinstance(s.default_wow, dict) or set(s.default_wow) != {"wide", "animated_family"}:
        raise ValueError(f"{where}: default_wow must define exactly wide and animated_family")
    for cat, w in s.default_wow.items():
        if not isinstance(w, (int, float)) or isinstance(w, bool) or not 0 < w <= 1:
            raise ValueError(f"{where}: default_wow.{cat} must be a number in (0, 1]")
    if s.default_group is not None and not isinstance(s.default_group, str):
        raise ValueError(f"{where}: default_group must be a string")


def load_season_dir(season_dir: Path) -> tuple[Season, list[Group]]:
    """One season = one directory named after its year (spec §2.1)."""
    season_dir = Path(season_dir)
    season = load_season(season_dir / "season.yaml")
    if season_dir.name != str(season.year):
        raise ValueError(
            f"{season_dir}: directory name must equal season.yaml year ({season.year})")
    groups = [load_group(p) for p in sorted((season_dir / "groups").glob("*.yaml"))]
    if not groups:
        raise ValueError(f"{season_dir}: no group files under groups/")
    ids = sorted(g.group_id for g in groups)
    if season.default_group is None:
        season = replace(season, default_group=ids[0])
    elif season.default_group not in ids:
        raise ValueError(
            f"{season_dir / 'season.yaml'}: default_group {season.default_group!r} "
            "names no roster file")
    return season, groups
