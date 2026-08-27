from dataclasses import dataclass, field, fields
from datetime import date
from pathlib import Path

import yaml

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


def load_season(path: Path) -> Season:
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a mapping")
    missing = [k for k in _REQUIRED if k not in raw]
    if missing:
        raise ValueError(f"{path}: missing required key(s): {', '.join(missing)}")
    if raw["window_start"] > raw["window_end"]:
        raise ValueError(f"{path}: window_start is after window_end")
    unknown = set(raw) - {f.name for f in fields(Season)}
    if unknown:
        raise ValueError(f"{path}: unknown key(s): {', '.join(sorted(unknown))}")
    return Season(**raw)
