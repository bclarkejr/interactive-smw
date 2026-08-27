# Summer Movie Wager — Standalone Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a from-scratch, self-contained static-site generator that tracks and forecasts a summer box-office prediction game: ingest Box Office Mojo's yearly chart, project every film's final in-window gross, Monte-Carlo-simulate the season, and render four interactive HTML pages plus `data.json`.

**Architecture:** A batch Python pipeline (`Season → ingest → normalize → project → MovieCatalog`, then per-group `score/simulate/render`) that writes static HTML with all CSS/JS inlined. No server, no database, no build toolchain, no client-side dependencies. All persisted data is YAML/JSONL in a version-controlled `data/` directory.

**Tech Stack:** Python ≥3.11, PyYAML, Jinja2, numpy, requests, beautifulsoup4, pytest. Zero client-side libraries (hand-rolled drag-and-drop with mandatory keyboard fallback).

**Spec:** `superpowers/specs/2026-08-15-standalone-rebuild-spec.md` — the plan argues from the spec; executors read both. Section references (§) below point into that file.

## Global Constraints

Copied from the spec; every task's requirements implicitly include these.

- **Reproducible output:** given identical inputs, two builds produce byte-identical HTML. Simulation seeded from `season.seed`; nothing reads wall-clock time except the explicitly passed `--date` (§1.3).
- **Self-contained pages:** zero network requests from published pages. All CSS/JS inlined, no remote fonts (system font stack), no runtime fetch, no external links anywhere in output (§13.1).
- **No module-level date or threshold constants** in projection, simulation, or render layers — everything comes from `Season` (§3.2). Game/model constants (point values, day-of-week weights, sigma tables) are allowed as module constants; dates and tunables are not.
- **No type may carry film data and roster data together** (§3.5). `score`, `simulate`, `render` take `(Season, Group, MovieCatalog)` and never read global state. `render()` takes an output directory parameter.
- **`smw/score/rules.py` depends on nothing but the roster type** (Appendix B).
- **No network in tests.** The chart HTML is a committed fixture (§13.5).
- **Autoescaping forced on unconditionally** in Jinja2; embedded JSON escapes `<` as `\u003c` (§11.4).
- **2026 season values:** `year=2026`, `window_start=2026-05-01`, `window_end=2026-09-07`, `seed=20260907` (§3.2, §5.1).
- Scoring constants (§2.3–2.5): exact at #1/#10 = 13; exact #2–#9 = 10; off-by-1/2/3+ = 7/5/3; dark horse in top ten = 1; max score 109.
- Model constants (Appendix A): default WoW wide 0.55 / animated_family 0.65; DOW weights Mon–Sun `[0.07, 0.10, 0.07, 0.06, 0.22, 0.26, 0.22]`; decay sigma 0.30→0.10 linear over 6 weeks; observed-decay clamp [0.01, 1.00]; pre-release run 10 weeks; opening-weekend share of week one 0.70 (= Fri+Sat+Sun weights, must stay derived); confidence sigma high/med/low = 0.20/0.30/0.45; 80% band z = 1.2816; 10 films to rank (raises), 25 projections to forecast (degrades); 10 000 trials; medoid cap 1500; top 25 chart contenders; 15 matrix rows; palette of 8; breakpoint ~700px.
- **Working directory is not yet a git repository** — Task 1 runs `git init`. Generated site output is committed (§13.4); never hand-edit it.

## File Structure

```
pyproject.toml
README.md                          # operator doc incl. end-of-season protocol (T21)
smw/
  __init__.py
  __main__.py                      # CLI entry (T19)
  config/
    __init__.py
    season.py                      # Season, load_season (T2)
    groups.py                      # PlayerPicks, Group, load_group (T3)
  score/
    __init__.py
    rules.py                       # the whole of §2 (T4)
  ingest/
    __init__.py
    boxoffice.py                   # fetch, parse, window filter, Guards A/B (T5)
  catalog/
    __init__.py
    normalize.py                   # overrides, aliases, preopening loader, Film, build_films (T6, T8)
    resolve.py                     # history load/dedup, gross resolution, Guard C (T7)
  model/
    __init__.py
    decay.py                       # Mode A + observed blend + clamp (T9)
    preopening.py                  # Mode B, finite-run bisection (T10)
    project.py                     # dispatch, bands, warnings, MovieCatalog (T11)
    simulate.py                    # sampling with floor, aggregation, medoid scenarios (T12, T13)
  render/
    __init__.py
    build.py                       # pipeline glue, data.json, history writers (T19)
    page.py                        # jinja env, view models, per-page renderers (T14–T18)
    templates/                     # base, index, whatif, scenarios, history, rules
    static/                        # site.css, theme.js, scoring.js, whatif.js, scenarios.js, history.js
data/
  season.yaml
  groups/filmcast-friends.yaml
  preopening_projections.yaml
  movies_overrides.yaml
  # box_office_history.jsonl / forecast_history.jsonl appear after first production run
tests/
  conftest.py
  fixtures/
    year_chart.html                # synthetic BOM chart fixture (T5)
    scoring_vectors.json           # shared server/client test vector (T20)
    snapshot_index.html            # byte-exact leaderboard snapshot (T15)
  test_*.py                        # one file per module, named in tasks
out/                               # generated site, committed
```

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `smw/__init__.py`, `smw/config/__init__.py`, `smw/score/__init__.py`, `smw/ingest/__init__.py`, `smw/catalog/__init__.py`, `smw/model/__init__.py`, `smw/render/__init__.py`, `tests/test_smoke.py`

**Interfaces:**
- Produces: an installable `smw` package importable from tests; `pytest` runs from repo root.

- [ ] **Step 1: Initialize git and package layout**

```bash
cd /Users/bclarke/Desktop/dev/interactive-smw
git init
mkdir -p smw/config smw/score smw/ingest smw/catalog smw/model smw/render/templates smw/render/static tests/fixtures data/groups out
touch smw/__init__.py smw/config/__init__.py smw/score/__init__.py smw/ingest/__init__.py smw/catalog/__init__.py smw/model/__init__.py smw/render/__init__.py
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "smw"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pyyaml>=6.0",
    "jinja2>=3.1",
    "numpy>=1.26",
    "requests>=2.31",
    "beautifulsoup4>=4.12",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["smw*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Write `.gitignore`**

```gitignore
__pycache__/
*.pyc
.venv/
.pytest_cache/
.DS_Store
*.egg-info/
```

Note: `out/` is NOT ignored — generated output is committed (§13.4).

- [ ] **Step 4: Create venv, install, write smoke test**

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
```

`tests/test_smoke.py`:

```python
def test_imports():
    import smw.config, smw.score, smw.ingest, smw.catalog, smw.model, smw.render  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore: scaffold smw package

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

All later tasks use `.venv/bin/pytest`; abbreviated below as `pytest`.

---

### Task 2: Season configuration

**Files:**
- Create: `smw/config/season.py`, `data/season.yaml`, `tests/test_season.py`, `tests/conftest.py`

**Interfaces:**
- Produces: `Season` frozen dataclass with fields `year: int`, `window_start: date`, `window_end: date`, `seed: int`, `min_projections_for_forecast: int = 25`, `chart_contenders: int = 25`, `matrix_rows: int = 15`, `monte_carlo_trials: int = 10000`, `preopening_run_weeks: int = 10`, `default_wow: dict[str, float]` (defaults `{"wide": 0.55, "animated_family": 0.65}`); `load_season(path: Path) -> Season` raising `ValueError` on missing required keys or inverted window. Also a shared test fixture `season` in `conftest.py` used by every later test file.

- [ ] **Step 1: Write the failing tests** — `tests/test_season.py`:

```python
from datetime import date
from pathlib import Path
import pytest
from smw.config.season import Season, load_season

def test_load_season_from_yaml(tmp_path):
    p = tmp_path / "season.yaml"
    p.write_text(
        "year: 2026\nwindow_start: 2026-05-01\nwindow_end: 2026-09-07\n"
        "seed: 20260907\nmatrix_rows: 12\ndefault_wow:\n  wide: 0.5\n  animated_family: 0.6\n"
    )
    s = load_season(p)
    assert s.year == 2026
    assert s.window_start == date(2026, 5, 1)
    assert s.window_end == date(2026, 9, 7)
    assert s.seed == 20260907
    assert s.matrix_rows == 12                      # explicit value wins
    assert s.min_projections_for_forecast == 25     # default fills in
    assert s.default_wow == {"wide": 0.5, "animated_family": 0.6}

def test_missing_required_key_raises(tmp_path):
    p = tmp_path / "season.yaml"
    p.write_text("year: 2026\nwindow_start: 2026-05-01\nwindow_end: 2026-09-07\n")
    with pytest.raises(ValueError, match="seed"):
        load_season(p)

def test_inverted_window_raises(tmp_path):
    p = tmp_path / "season.yaml"
    p.write_text("year: 2026\nwindow_start: 2026-09-07\nwindow_end: 2026-05-01\nseed: 1\n")
    with pytest.raises(ValueError, match="window"):
        load_season(p)
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_season.py -v` — Expected: FAIL, `ModuleNotFoundError` / `ImportError`.

- [ ] **Step 3: Implement `smw/config/season.py`**

```python
from dataclasses import dataclass, field
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
    unknown = set(raw) - {f.name for f in Season.__dataclass_fields__.values()}
    if unknown:
        raise ValueError(f"{path}: unknown key(s): {', '.join(sorted(unknown))}")
    return Season(**raw)
```

(`Season.__dataclass_fields__.values()` — use `dataclasses.fields(Season)`; either works, pick `fields()` for clarity: `from dataclasses import fields` and `{f.name for f in fields(Season)}`.)

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_season.py -v` — Expected: 3 PASS.

- [ ] **Step 5: Write `data/season.yaml`** (the 2026 season, §5.1)

```yaml
year: 2026
window_start: 2026-05-01
window_end: 2026-09-07
min_projections_for_forecast: 25
chart_contenders: 25
matrix_rows: 15
monte_carlo_trials: 10000
seed: 20260907
preopening_run_weeks: 10
default_wow:
  wide: 0.55
  animated_family: 0.65
```

- [ ] **Step 6: Write the shared conftest fixture** — `tests/conftest.py`:

```python
from datetime import date
from pathlib import Path

import pytest

from smw.config.season import Season

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def season() -> Season:
    # Small trial count keeps simulation tests fast; deterministic seed throughout.
    return Season(
        year=2026,
        window_start=date(2026, 5, 1),
        window_end=date(2026, 9, 7),
        seed=42,
        monte_carlo_trials=2000,
    )
```

- [ ] **Step 7: Run full suite, commit**

Run: `pytest -v` — Expected: all PASS.

```bash
git add -A && git commit -m "feat: Season config and loader

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Rosters — `Group` and `PlayerPicks`

**Files:**
- Create: `smw/config/groups.py`, `data/groups/filmcast-friends.yaml`, `tests/test_groups.py`

**Interfaces:**
- Produces: `PlayerPicks` frozen dataclass (`username: str`, `ranked: tuple[str, ...]` exactly 10, `dark_horses: tuple[str, ...]` exactly 3); `Group` frozen dataclass (`group_id: str`, `display_name: str`, `players: dict[str, PlayerPicks]`); `load_group(path: Path) -> Group` raising `ValueError` naming the player and the violation (§2.1). Later tasks consume `group.players[u].ranked` / `.dark_horses` and `sorted(group.players)` for stable ordering.

- [ ] **Step 1: Write the failing tests** — `tests/test_groups.py`:

```python
import pytest
from smw.config.groups import load_group

VALID = """\
group_id: testers
display_name: "Test League"
players:
  alice:
    ranked: [F1, F2, F3, F4, F5, F6, F7, F8, F9, F10]
    dark_horses: [D1, D2, D3]
"""

def _write(tmp_path, text):
    p = tmp_path / "g.yaml"
    p.write_text(text)
    return p

def test_valid_group_loads(tmp_path):
    g = load_group(_write(tmp_path, VALID))
    assert g.group_id == "testers"
    assert g.display_name == "Test League"
    assert g.players["alice"].ranked == tuple(f"F{i}" for i in range(1, 11))
    assert g.players["alice"].dark_horses == ("D1", "D2", "D3")
    assert g.players["alice"].username == "alice"

def test_wrong_ranked_count_names_player(tmp_path):
    bad = VALID.replace(", F10]", "]")
    with pytest.raises(ValueError, match="alice.*10 ranked"):
        load_group(_write(tmp_path, bad))

def test_wrong_dark_horse_count_names_player(tmp_path):
    bad = VALID.replace(", D3]", "]")
    with pytest.raises(ValueError, match="alice.*3 dark horse"):
        load_group(_write(tmp_path, bad))

def test_duplicate_title_rejected(tmp_path):
    bad = VALID.replace("dark_horses: [D1, D2, D3]", "dark_horses: [D1, D2, F1]")
    with pytest.raises(ValueError, match="alice.*distinct"):
        load_group(_write(tmp_path, bad))

def test_empty_players_is_legal(tmp_path):
    g = load_group(_write(tmp_path, "group_id: t\ndisplay_name: T\nplayers: {}\n"))
    assert g.players == {}
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_groups.py -v` — Expected: FAIL with import error.

- [ ] **Step 3: Implement `smw/config/groups.py`**

```python
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class PlayerPicks:
    username: str
    ranked: tuple[str, ...]
    dark_horses: tuple[str, ...]


@dataclass(frozen=True)
class Group:
    group_id: str
    display_name: str
    players: dict[str, PlayerPicks]


def load_group(path: Path) -> Group:
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict) or "group_id" not in raw or "display_name" not in raw:
        raise ValueError(f"{path}: group file needs group_id and display_name")
    players: dict[str, PlayerPicks] = {}
    for username, picks in (raw.get("players") or {}).items():
        ranked = tuple(picks.get("ranked") or [])
        dark = tuple(picks.get("dark_horses") or [])
        if len(ranked) != 10:
            raise ValueError(f"{username}: expected exactly 10 ranked picks, got {len(ranked)}")
        if len(dark) != 3:
            raise ValueError(f"{username}: expected exactly 3 dark horses, got {len(dark)}")
        if len(set(ranked + dark)) != 13:
            raise ValueError(f"{username}: all 13 titles must be distinct")
        players[username] = PlayerPicks(username=username, ranked=ranked, dark_horses=dark)
    return Group(group_id=raw["group_id"], display_name=raw["display_name"], players=players)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_groups.py -v` — Expected: 5 PASS.

- [ ] **Step 5: Write `data/groups/filmcast-friends.yaml`** (the spec's §5.2 example roster; the operator replaces/extends players before the first production run)

```yaml
group_id: filmcast-friends
display_name: "The Friends League"
players:
  bclarke:
    ranked:
      - Toy Story 5
      - "Spider-Man: Brand New Day"
      - Minions & Monsters
      - The Devil Wears Prada 2
      - The Odyssey
      - Moana
      - "Star Wars: The Mandalorian and Grogu"
      - Supergirl
      - Disclosure Day
      - Mortal Kombat II
    dark_horses:
      - Backrooms
      - Scary Movie
      - Evil Dead Burn
```

- [ ] **Step 6: Add a group fixture to `tests/conftest.py`** (append)

```python
from smw.config.groups import Group, PlayerPicks


def _picks(username: str, ranked: list[str], dark: list[str]) -> PlayerPicks:
    return PlayerPicks(username=username, ranked=tuple(ranked), dark_horses=tuple(dark))


@pytest.fixture
def group() -> Group:
    # Films are generic titles M01..M18 so tests control the finish order exactly.
    return Group(
        group_id="testers",
        display_name="Test League",
        players={
            "alice": _picks("alice",
                            [f"M{i:02d}" for i in range(1, 11)], ["M15", "M16", "M17"]),
            "bob": _picks("bob",
                          [f"M{i:02d}" for i in range(10, 0, -1)], ["M15", "M18", "M14"]),
            "carol": _picks("carol",
                            ["M02", "M01", "M03", "M05", "M04", "M06", "M08", "M07", "M10", "M09"],
                            ["M11", "M12", "M13"]),
        },
    )
```

- [ ] **Step 7: Run full suite, commit**

Run: `pytest -v` — Expected: all PASS.

```bash
git add -A && git commit -m "feat: Group/PlayerPicks with roster validation

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Scoring rules (§2)

**Files:**
- Create: `smw/score/rules.py`, `tests/test_rules.py`

**Interfaces:**
- Consumes: `PlayerPicks` from `smw.config.groups` (the only permitted import — Appendix B rule).
- Produces: `ranked_pick_points(predicted: int, actual: int | None) -> int`; `score_breakdown(picks: PlayerPicks, top_titles: Sequence[str]) -> list[int]` (indexed by actual finish position, raises `ValueError` if `len(top_titles) > 10`); `score_player(picks: PlayerPicks, top_titles: Sequence[str]) -> int`. Every later scoring consumer (simulation, leaderboard, scenarios, current points) calls exactly these.

- [ ] **Step 1: Write the failing tests** — `tests/test_rules.py`. Coverage required by §13.5: every rung, both endpoints, dark horse hit/miss, over-length raises, partial/empty finish lists, breakdown sums to total.

```python
import pytest
from smw.config.groups import PlayerPicks
from smw.score.rules import ranked_pick_points, score_breakdown, score_player

PICKS = PlayerPicks(
    username="alice",
    ranked=tuple(f"M{i:02d}" for i in range(1, 11)),  # M01 predicted #1 ... M10 predicted #10
    dark_horses=("D1", "D2", "D3"),
)

@pytest.mark.parametrize("predicted,actual,expected", [
    (1, None, 0),        # not in top ten
    (1, 1, 13),          # exact endpoint, top
    (10, 10, 13),        # exact endpoint, bottom
    (2, 2, 10),          # exact middle
    (9, 9, 10),          # exact middle, other edge
    (3, 4, 7),           # off by one
    (3, 2, 7),           # off by one, other direction
    (3, 5, 5),           # off by two
    (1, 4, 3),           # off by three
    (1, 10, 3),          # off by nine
])
def test_ranked_pick_points(predicted, actual, expected):
    assert ranked_pick_points(predicted, actual) == expected

def test_perfect_season_scores_109():
    finish = list(PICKS.ranked)
    # Dark horses can't also be ranked picks; use a roster whose dark horses miss.
    assert score_player(PICKS, finish) == 13 + 10 * 8 + 13

def test_dark_horse_scores_one_at_any_position():
    finish = ["D1"] + [f"X{i}" for i in range(8)] + ["D2"]  # D1 at #1, D2 at #10
    assert score_player(PICKS, finish) == 2

def test_over_length_finish_raises():
    with pytest.raises(ValueError):
        score_breakdown(PICKS, [f"X{i}" for i in range(11)])

def test_partial_finish_scores_only_present_positions():
    finish = ["M01", "M02", "M03"]  # only three films have grossed anything
    b = score_breakdown(PICKS, finish)
    assert len(b) == 3
    assert b == [13, 10, 10]

def test_empty_finish_scores_zero():
    assert score_player(PICKS, []) == 0
    assert score_breakdown(PICKS, []) == []

def test_breakdown_sums_to_total():
    finish = ["M05", "D1", "M01", "M02", "X1", "M10", "X2", "M03", "D2", "M09"]
    assert sum(score_breakdown(PICKS, finish)) == score_player(PICKS, finish)

def test_breakdown_is_indexed_by_actual_position():
    finish = ["M03", "M01"]  # M03 (predicted 3) finishes #1; M01 (predicted 1) finishes #2
    b = score_breakdown(PICKS, finish)
    assert b[0] == ranked_pick_points(3, 1)  # points the #1 finisher contributes
    assert b[1] == ranked_pick_points(1, 2)
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_rules.py -v` — Expected: FAIL with import error.

- [ ] **Step 3: Implement `smw/score/rules.py`** (§2.3–2.5 reference implementation, verbatim semantics)

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_rules.py -v` — Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: scoring rules (spec §2)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Chart ingest (§4)

**Files:**
- Create: `smw/ingest/boxoffice.py`, `tests/fixtures/year_chart.html`, `tests/test_boxoffice.py`

**Interfaces:**
- Consumes: `Season` from Task 2.
- Produces: `ChartRow` frozen dataclass (`title: str`, `gross: float`, `release_date: date`, `is_rerelease: bool`); `parse_chart(html: str, year: int) -> list[ChartRow]`; `windowed(rows: list[ChartRow], season: Season) -> list[ChartRow]` (Guards A and B, raising `IngestError`); `fetch_chart(year: int) -> str` (requests, 30 s timeout); `chart_floor(rows: list[ChartRow]) -> float` (minimum gross across ALL parsed rows — Task 7's Guard C consumes this). `IngestError(RuntimeError)` exception class.

- [ ] **Step 1: Write the chart fixture** — `tests/fixtures/year_chart.html`. Synthetic, modeled on Box Office Mojo's real yearly-chart markup (`mojo-field-type-*` cell classes, in-year gross carrying both `mojo-field-type-money` and `mojo-estimatable`, a budget column carrying money-without-estimatable, titles inside an `<a>`, a re-release marked by a `<span>` note nested in the title cell, abbreviated dates without a year). When the first production run happens, save the real fetched page over this fixture and re-run the parser tests (§13.5 wants the committed fixture to be the real chart).

```html
<html><body>
<table>
<tr><th>Rank</th><th>Release</th><th>Gross</th><th>Budget</th><th>Total Gross</th><th>Release Date</th></tr>
<tr>
  <td class="mojo-field-type-rank">1</td>
  <td class="mojo-field-type-release"><a href="/release/rl1/">Big Summer Film</a></td>
  <td class="mojo-field-type-money mojo-estimatable">$310,491,022</td>
  <td class="mojo-field-type-money">$200,000,000</td>
  <td class="mojo-field-type-money mojo-estimatable">$310,491,022</td>
  <td class="mojo-field-type-date a-nowrap">May 1</td>
</tr>
<tr>
  <td class="mojo-field-type-rank">2</td>
  <td class="mojo-field-type-release"><a href="/release/rl2/">Spring Holdover</a></td>
  <td class="mojo-field-type-money mojo-estimatable">$150,000,000</td>
  <td class="mojo-field-type-money">$90,000,000</td>
  <td class="mojo-field-type-money mojo-estimatable">$155,000,000</td>
  <td class="mojo-field-type-date a-nowrap">Apr 10</td>
</tr>
<tr>
  <td class="mojo-field-type-rank">3</td>
  <td class="mojo-field-type-release"><a href="/release/rl3/">Anniversary Classic</a><span class="a-size-small">2026 Re-release</span></td>
  <td class="mojo-field-type-money mojo-estimatable">$12,000,000</td>
  <td class="mojo-field-type-money">$5,000,000</td>
  <td class="mojo-field-type-money mojo-estimatable">$412,000,000</td>
  <td class="mojo-field-type-date a-nowrap">Jun 12</td>
</tr>
<tr>
  <td class="mojo-field-type-rank">4</td>
  <td class="mojo-field-type-release"><a href="/release/rl4/">Mid June Comedy</a></td>
  <td class="mojo-field-type-money mojo-estimatable">$88,300,500</td>
  <td class="mojo-field-type-money">$40,000,000</td>
  <td class="mojo-field-type-money mojo-estimatable">$88,300,500</td>
  <td class="mojo-field-type-date a-nowrap">Jun 19</td>
</tr>
<tr>
  <td class="mojo-field-type-rank">5</td>
  <td class="mojo-field-type-release"><a href="/release/rl5/">Labor Day Opener</a></td>
  <td class="mojo-field-type-money mojo-estimatable">$5,100,000</td>
  <td class="mojo-field-type-money">$15,000,000</td>
  <td class="mojo-field-type-money mojo-estimatable">$5,100,000</td>
  <td class="mojo-field-type-date a-nowrap">Sep 7</td>
</tr>
<tr>
  <td class="mojo-field-type-rank">6</td>
  <td class="mojo-field-type-release"><a href="/release/rl6/">Autumn Release</a></td>
  <td class="mojo-field-type-money mojo-estimatable">$2,000,000</td>
  <td class="mojo-field-type-money">$10,000,000</td>
  <td class="mojo-field-type-money mojo-estimatable">$2,000,000</td>
  <td class="mojo-field-type-date a-nowrap">Sep 8</td>
</tr>
<tr>
  <td class="mojo-field-type-rank">7</td>
  <td class="mojo-field-type-release"><a href="/release/rl7/">Tiny Tail Film</a></td>
  <td class="mojo-field-type-money mojo-estimatable">$468,000</td>
  <td class="mojo-field-type-money">$1,000,000</td>
  <td class="mojo-field-type-money mojo-estimatable">$468,000</td>
  <td class="mojo-field-type-date a-nowrap">Jul 4</td>
</tr>
<tr><td class="mojo-footer">Footer junk row with no money or date</td></tr>
</table>
</body></html>
```

Window facts this fixture encodes for a 2026-05-01..2026-09-07 season: `Big Summer Film` (May 1, boundary start, in), `Spring Holdover` (Apr 10, out), `Anniversary Classic` (re-release, out), `Mid June Comedy` (in), `Labor Day Opener` (Sep 7, boundary end, in), `Autumn Release` (Sep 8, out), `Tiny Tail Film` (in, and it is the chart floor row).

- [ ] **Step 2: Write the failing tests** — `tests/test_boxoffice.py`:

```python
from datetime import date
import pytest
from smw.ingest.boxoffice import ChartRow, IngestError, chart_floor, parse_chart, windowed
from tests.conftest import FIXTURES

HTML = (FIXTURES / "year_chart.html").read_text()

def test_parses_rows_and_skips_junk():
    rows = parse_chart(HTML, 2026)
    assert len(rows) == 7  # footer/header rows skipped, re-release still parsed (flagged)
    by_title = {r.title: r for r in rows}
    assert by_title["Big Summer Film"].gross == 310_491_022.0

def test_reads_in_year_gross_not_budget_or_total():
    rows = parse_chart(HTML, 2026)
    holdover = next(r for r in rows if r.title == "Spring Holdover")
    assert holdover.gross == 150_000_000.0  # first money+estimatable cell, not budget, not Total Gross

def test_title_from_anchor_excludes_note_markup():
    rows = parse_chart(HTML, 2026)
    rr = next(r for r in rows if r.title == "Anniversary Classic")
    assert rr.title == "Anniversary Classic"  # no "2026 Re-release" text picked up

def test_rerelease_flagged():
    rows = parse_chart(HTML, 2026)
    assert next(r for r in rows if r.title == "Anniversary Classic").is_rerelease
    assert not next(r for r in rows if r.title == "Big Summer Film").is_rerelease

def test_dates_stamped_with_chart_year():
    rows = parse_chart(HTML, 2026)
    assert next(r for r in rows if r.title == "Big Summer Film").release_date == date(2026, 5, 1)

def test_window_filter_boundaries_and_rerelease(season):
    kept = {r.title for r in windowed(parse_chart(HTML, 2026), season)}
    assert kept == {"Big Summer Film", "Mid June Comedy", "Labor Day Opener", "Tiny Tail Film"}

def test_guard_a_empty_chart_raises(season):
    with pytest.raises(IngestError, match="Guard A"):
        windowed([], season)

def test_guard_b_everything_filtered_raises_naming_rule_3(season):
    rows = [ChartRow("X", 1.0, date(2026, 6, 1), True)]
    with pytest.raises(IngestError, match="Rule 3"):
        windowed(rows, season)

def test_chart_floor_is_min_of_all_parsed_rows():
    assert chart_floor(parse_chart(HTML, 2026)) == 468_000.0
```

- [ ] **Step 3: Run to verify failure**

Run: `pytest tests/test_boxoffice.py -v` — Expected: FAIL with import error.

- [ ] **Step 4: Implement `smw/ingest/boxoffice.py`**

```python
"""Box Office Mojo yearly-chart ingest (spec §4). The system's only network dependency."""
from dataclasses import dataclass
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from smw.config.season import Season


class IngestError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChartRow:
    title: str
    gross: float
    release_date: date
    is_rerelease: bool


def fetch_chart(year: int) -> str:
    resp = requests.get(
        f"https://www.boxofficemojo.com/year/{year}/",
        timeout=30,
        headers={"User-Agent": "smw-tracker (personal box-office pool)"},
    )
    resp.raise_for_status()
    return resp.text


def parse_chart(html: str, year: int) -> list[ChartRow]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[ChartRow] = []
    for tr in soup.find_all("tr"):
        title_cell = tr.select_one("td.mojo-field-type-release")
        # Rule 1: in-year gross is the FIRST cell carrying BOTH the money class and the
        # estimatable marker. Money-without-estimatable is the budget column; a later
        # money+estimatable cell is the stale "Total Gross".
        money_cell = tr.select_one("td.mojo-field-type-money.mojo-estimatable")
        date_cell = tr.select_one("td.mojo-field-type-date")
        if title_cell is None or money_cell is None or date_cell is None:
            continue  # Rule 4: header/footer rows partially match; skip, don't raise
        link = title_cell.find("a")
        if link is None:
            continue
        title = link.get_text(strip=True)  # Rule 2: anchor text only
        try:
            gross = float(money_cell.get_text(strip=True).replace("$", "").replace(",", ""))
            release = datetime.strptime(
                f"{date_cell.get_text(strip=True)} {year}", "%b %d %Y"
            ).date()
        except ValueError:
            continue
        # Rule 3: a note element nested in the title cell marks a re-release.
        is_rerelease = title_cell.find("span") is not None
        rows.append(ChartRow(title=title, gross=gross, release_date=release,
                             is_rerelease=is_rerelease))
    return rows


def chart_floor(rows: list[ChartRow]) -> float:
    return min(r.gross for r in rows)


def windowed(rows: list[ChartRow], season: Season) -> list[ChartRow]:
    if not rows:
        raise IngestError(
            "Guard A: chart parse yielded zero rows — the fetch failed or the markup changed."
        )
    kept = [
        r for r in rows
        if season.window_start <= r.release_date <= season.window_end and not r.is_rerelease
    ]
    if not kept:
        raise IngestError(
            "Guard B: the chart parsed but the window filter kept zero rows. "
            "First check Rule 3 (re-release detection): a markup change that nests a new "
            "element inside every title cell flags every film as a re-release and filters "
            "everything away."
        )
    return kept
```

- [ ] **Step 5: Run to verify pass**

Run: `pytest tests/test_boxoffice.py -v` — Expected: 9 PASS.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: chart ingest with parsing rules and Guards A/B

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Overrides, aliases, and pre-release estimate loaders (§5.3, §5.4, §6.5)

**Files:**
- Create: `smw/catalog/normalize.py` (loaders and alias half; Task 8 adds `build_films`), `data/movies_overrides.yaml`, `data/preopening_projections.yaml`, `tests/test_normalize.py`

**Interfaces:**
- Produces (all in `smw.catalog.normalize`):
  - `Override` frozen dataclass: `category: str | None = None`, `alias_of: str | None = None`, `release_date: date | None = None`, `status: str | None = None`.
  - `load_overrides(path: Path) -> dict[str, Override]` — missing file → `{}`; unknown keys or bad category/status values raise `ValueError`.
  - `canonical(title: str, overrides: dict[str, Override]) -> str` — resolves `alias_of`, else identity.
  - `apply_chart_aliases(rows: list[ChartRow], overrides: dict[str, Override]) -> list[ChartRow]` — alias application point 1 of §6.5 (at chart ingest, keyed on the variant).
  - `PreopeningEstimate` frozen dataclass: `release_date: date | None = None`, `opening_weekend_estimate: float | None = None`, `total_domestic_estimate: float | None = None`, `confidence: str | None = None`, `source: str = ""`, `as_of: date | None = None`, `notes: str = ""`; method `is_complete() -> bool` (§5.3: opening, total, confidence all present, both figures positive).
  - `load_preopening(path: Path) -> dict[str, PreopeningEstimate]` — missing file → `{}`; a `confidence` outside `{high, med, low}` raises `ValueError`; underscore digit separators (YAML 1.1 / PyYAML) must load as ints.

- [ ] **Step 1: Write the failing tests** — `tests/test_normalize.py`:

```python
from datetime import date
import pytest
from smw.catalog.normalize import (
    Override, PreopeningEstimate, apply_chart_aliases, canonical,
    load_overrides, load_preopening,
)
from smw.ingest.boxoffice import ChartRow

def test_load_overrides_all_fields(tmp_path):
    p = tmp_path / "movies_overrides.yaml"
    p.write_text(
        '"Toy Story 5":\n  category: animated_family\n'
        '"Variant Title":\n  alias_of: "Canonical Title"\n'
        '"Bad Date Film":\n  release_date: 2026-07-10\n  status: pre_release\n'
    )
    ov = load_overrides(p)
    assert ov["Toy Story 5"].category == "animated_family"
    assert ov["Variant Title"].alias_of == "Canonical Title"
    assert ov["Bad Date Film"].release_date == date(2026, 7, 10)
    assert ov["Bad Date Film"].status == "pre_release"

def test_missing_overrides_file_is_empty(tmp_path):
    assert load_overrides(tmp_path / "nope.yaml") == {}

def test_unknown_override_key_raises(tmp_path):
    p = tmp_path / "o.yaml"
    p.write_text('"X":\n  categry: wide\n')
    with pytest.raises(ValueError, match="categry"):
        load_overrides(p)

def test_canonical_resolves_alias():
    ov = {"Variant": Override(alias_of="Canonical")}
    assert canonical("Variant", ov) == "Canonical"
    assert canonical("Other", ov) == "Other"

def test_apply_chart_aliases_renames_rows():
    ov = {"Variant": Override(alias_of="Canonical")}
    rows = [ChartRow("Variant", 5.0, date(2026, 6, 1), False),
            ChartRow("Untouched", 1.0, date(2026, 6, 1), False)]
    out = apply_chart_aliases(rows, ov)
    assert [r.title for r in out] == ["Canonical", "Untouched"]
    assert out[0].gross == 5.0

def test_load_preopening_with_underscore_separators(tmp_path):
    p = tmp_path / "pre.yaml"
    p.write_text(
        '"Toy Story 5":\n'
        "  release_date: 2026-06-19\n"
        "  opening_weekend_estimate: 168_000_000\n"
        "  total_domestic_estimate: 559_000_000\n"
        "  confidence: med\n"
        '  source: "Box Office Theory"\n'
        "  as_of: 2026-04-23\n"
    )
    pre = load_preopening(p)
    est = pre["Toy Story 5"]
    assert est.opening_weekend_estimate == 168_000_000
    assert est.total_domestic_estimate == 559_000_000
    assert est.confidence == "med"
    assert est.is_complete()

def test_partial_entry_is_not_complete(tmp_path):
    p = tmp_path / "pre.yaml"
    p.write_text('"X":\n  opening_weekend_estimate: 10_000_000\n')
    assert not load_preopening(p)["X"].is_complete()

def test_nonpositive_figure_is_not_complete():
    est = PreopeningEstimate(opening_weekend_estimate=0,
                             total_domestic_estimate=100.0, confidence="med")
    assert not est.is_complete()

def test_bad_confidence_raises(tmp_path):
    p = tmp_path / "pre.yaml"
    p.write_text('"X":\n  confidence: certain\n')
    with pytest.raises(ValueError, match="confidence"):
        load_preopening(p)
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_normalize.py -v` — Expected: FAIL with import error.

- [ ] **Step 3: Implement the loader half of `smw/catalog/normalize.py`**

```python
"""Catalog normalization: overrides, aliases, analyst estimates, film records (spec §5.3–5.4, §6.2, §6.5)."""
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

import yaml

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
    for title, fields in raw.items():
        unknown = set(fields) - _OVERRIDE_KEYS
        if unknown:
            raise ValueError(f"{path}: '{title}' has unknown key(s): {', '.join(sorted(unknown))}")
        cat, status = fields.get("category"), fields.get("status")
        if cat is not None and cat not in _CATEGORIES:
            raise ValueError(f"{path}: '{title}' category must be one of {sorted(_CATEGORIES)}")
        if status is not None and status not in _STATUSES:
            raise ValueError(f"{path}: '{title}' status must be one of {sorted(_STATUSES)}")
        out[title] = Override(**fields)
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
    for title, fields in raw.items():
        conf = fields.get("confidence")
        if conf is not None and conf not in _CONFIDENCES:
            raise ValueError(f"{path}: '{title}' confidence must be one of {sorted(_CONFIDENCES)}")
        known = {f for f in PreopeningEstimate.__dataclass_fields__}
        unknown = set(fields) - known
        if unknown:
            raise ValueError(f"{path}: '{title}' has unknown key(s): {', '.join(sorted(unknown))}")
        out[title] = PreopeningEstimate(**fields)
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_normalize.py -v` — Expected: 9 PASS.

- [ ] **Step 5: Write the two data files** (starting content for the 2026 deployment; the operator maintains these through the season)

`data/movies_overrides.yaml`:

```yaml
# Film corrections (spec §5.4). Keys per entry: category, alias_of, release_date, status.
# Classify EVERY picked film explicitly, including genuinely `wide` ones (§8).
"Toy Story 5":
  category: animated_family
"Minions & Monsters":
  category: animated_family
"Moana":
  category: animated_family
```

`data/preopening_projections.yaml`:

```yaml
# Pre-release analyst estimates (spec §5.3). An entry is used only when
# opening_weekend_estimate, total_domestic_estimate, and confidence are all present.
"Toy Story 5":
  release_date: 2026-06-19
  opening_weekend_estimate: 168_000_000
  total_domestic_estimate: 559_000_000
  confidence: med
  source: "Box Office Theory"
  as_of: 2026-04-23
  notes: ""
```

- [ ] **Step 6: Run full suite, commit**

Run: `pytest -v` — Expected: all PASS.

```bash
git add -A && git commit -m "feat: overrides, aliases, and pre-release estimate loaders

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Gross resolution and Guard C (§5.5, §6.1, §6.3)

**Files:**
- Create: `smw/catalog/resolve.py`, `tests/test_resolve.py`

**Interfaces:**
- Consumes: `Season`, `ChartRow`.
- Produces (in `smw.catalog.resolve`):
  - `load_history(path: Path) -> dict[str, list[tuple[date, float]]]` — missing file → `{}` (caller warns, §10.2); same-date rows for a film deduplicate to the max at load (§5.5); each film's list is sorted by date ascending (Task 9's `blended_wow` relies on this ordering).
  - `resolve_grosses(season: Season, history: dict[str, list[tuple[date, float]]], chart_rows: list[ChartRow], floor: float, today: date) -> tuple[dict[str, float], set[str], bool]` — returns `(grosses, carried, chart_usable)`; raises `ResolutionError` for Guard C.
  - `ResolutionError(RuntimeError)`.

- [ ] **Step 1: Write the failing tests** — `tests/test_resolve.py`:

```python
from datetime import date
import json
import pytest
from smw.catalog.resolve import ResolutionError, load_history, resolve_grosses
from smw.ingest.boxoffice import ChartRow

def _hist(tmp_path, rows):
    p = tmp_path / "box_office_history.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return load_history(p)

def _row(title, gross, rel=date(2026, 5, 1)):
    return ChartRow(title, gross, rel, False)

def test_missing_history_file_is_empty(tmp_path):
    assert load_history(tmp_path / "nope.jsonl") == {}

def test_same_date_rows_dedupe_to_max(tmp_path):
    h = _hist(tmp_path, [
        {"movie": "A", "date": "2026-06-01", "cumulative_gross": 100.0},
        {"movie": "A", "date": "2026-06-01", "cumulative_gross": 120.0},
        {"movie": "A", "date": "2026-06-08", "cumulative_gross": 130.0},
    ])
    assert h["A"] == [(date(2026, 6, 1), 120.0), (date(2026, 6, 8), 130.0)]

def test_history_sorted_by_date_even_if_file_is_not(tmp_path):
    h = _hist(tmp_path, [
        {"movie": "A", "date": "2026-06-08", "cumulative_gross": 130.0},
        {"movie": "A", "date": "2026-06-01", "cumulative_gross": 100.0},
    ])
    assert [d for d, _ in h["A"]] == [date(2026, 6, 1), date(2026, 6, 8)]

def test_chart_merges_by_max_never_overwrites(season):
    history = {"A": [(date(2026, 6, 1), 150.0)]}
    grosses, carried, usable = resolve_grosses(
        season, history, [_row("A", 120.0)], floor=1.0, today=date(2026, 6, 8))
    assert grosses["A"] == 150.0  # highest, not latest
    assert usable
    assert carried == set()

def test_carry_forward_off_chart_title(season):
    history = {"Gone": [(date(2026, 6, 1), 500.0)]}
    grosses, carried, _ = resolve_grosses(
        season, history, [_row("A", 120.0)], floor=1000.0, today=date(2026, 6, 8))
    assert grosses["Gone"] == 500.0
    assert carried == {"Gone"}

def test_guard_c_carried_above_floor_raises_with_alias_hint(season):
    history = {"Renamed Upstream": [(date(2026, 6, 1), 5_000_000.0)]}
    with pytest.raises(ResolutionError, match="alias_of.*Renamed Upstream"):
        resolve_grosses(season, history, [_row("A", 120.0)],
                        floor=468_000.0, today=date(2026, 6, 8))

def test_observations_after_cutoff_ignored(season):
    # Run on window_end + 1 sees the full window; later-dated rows include
    # post-window money and must not count.
    history = {"A": [(date(2026, 9, 8), 200.0), (date(2026, 9, 20), 999.0)]}
    grosses, _, usable = resolve_grosses(
        season, history, [], floor=1.0, today=date(2026, 9, 8))
    assert grosses["A"] == 200.0

def test_chart_frozen_after_window_end_plus_one(season):
    # today = window_end + 2 → chart_usable false: chart values ignored, Guard C skipped.
    history = {"A": [(date(2026, 9, 8), 200.0)]}
    grosses, carried, usable = resolve_grosses(
        season, history, [_row("A", 5_000_000.0)], floor=1.0, today=date(2026, 9, 9))
    assert not usable
    assert grosses["A"] == 200.0
    assert carried == {"A"}

def test_chart_usable_on_window_end_plus_one(season):
    _, _, usable = resolve_grosses(season, {}, [_row("A", 1.0)],
                                   floor=1.0, today=date(2026, 9, 8))
    assert usable
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_resolve.py -v` — Expected: FAIL with import error.

- [ ] **Step 3: Implement `smw/catalog/resolve.py`**

```python
"""Gross resolution: history + live chart merged by max, carry-forward, Guard C (spec §6.1–6.3)."""
import json
from datetime import date, timedelta
from pathlib import Path

from smw.config.season import Season
from smw.ingest.boxoffice import ChartRow


class ResolutionError(RuntimeError):
    pass


def load_history(path: Path) -> dict[str, list[tuple[date, float]]]:
    path = Path(path)
    if not path.exists():
        return {}
    per_date: dict[str, dict[date, float]] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        d = date.fromisoformat(row["date"])
        gross = float(row["cumulative_gross"])
        by_date = per_date.setdefault(row["movie"], {})
        # §5.5: same-date rows collapse to the max, so a same-day re-run can never
        # inflate a film's snapshot count or skew the observed-decay weight.
        by_date[d] = max(gross, by_date.get(d, 0.0))
    return {
        title: sorted(by_date.items())
        for title, by_date in per_date.items()
    }


def resolve_grosses(
    season: Season,
    history: dict[str, list[tuple[date, float]]],
    chart_rows: list[ChartRow],
    floor: float,
    today: date,
) -> tuple[dict[str, float], set[str], bool]:
    cutoff = min(today, season.window_end + timedelta(days=1))
    chart_usable = (today - timedelta(days=1)) <= season.window_end

    grosses: dict[str, float] = {}
    for title, observations in history.items():
        in_range = [g for (d, g) in observations if d <= cutoff]
        if in_range:
            grosses[title] = max(in_range)  # highest, not latest

    chart_titles: set[str] = set()
    if chart_usable:
        for row in chart_rows:
            chart_titles.add(row.title)
            grosses[row.title] = max(row.gross, grosses.get(row.title, 0.0))

    carried = {t for t in grosses if t not in chart_titles}

    if chart_usable:
        impossible = sorted(t for t in carried if grosses[t] >= floor)
        if impossible:
            blocks = "\n\n".join(
                f'"<current upstream title for {t!r}>":\n  alias_of: "{t}"'
                for t in impossible
            )
            raise ResolutionError(
                "Guard C: carried-forward film(s) with a gross at or above the chart floor "
                f"(${floor:,.0f}) — a film that large must still be on the chart, so its "
                "absence means the source renamed it. Find the new title on the chart and "
                "add to movies_overrides.yaml:\n\n" + blocks
            )
    return grosses, carried, chart_usable
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_resolve.py -v` — Expected: 9 PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: gross resolution with carry-forward and Guard C

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Film catalog — candidate set, release dates, status (§6.2)

**Files:**
- Modify: `smw/catalog/normalize.py` (append `Film` and `build_films`)
- Test: `tests/test_build_films.py`

**Interfaces:**
- Consumes: `Override`, `PreopeningEstimate`, `canonical` (Task 6); `ChartRow` (Task 5); `Group` (Task 3); `Season` (Task 2).
- Produces: `Film` frozen dataclass (`title: str`, `release_date: date`, `status: str` in `{pre_release, in_theaters, closed}`, `category: str`, `cumulative_gross: float`, `estimate: PreopeningEstimate | None`); `build_films(season: Season, groups: list[Group], chart_rows: list[ChartRow], grosses: dict[str, float], carried: set[str], overrides: dict[str, Override], preopening: dict[str, PreopeningEstimate], today: date) -> list[Film]` returning films sorted by title (deterministic; ranking happens later in projection).

- [ ] **Step 1: Write the failing tests** — `tests/test_build_films.py`:

```python
from datetime import date
import pytest
from smw.catalog.normalize import Film, Override, PreopeningEstimate, build_films
from smw.config.groups import Group, PlayerPicks
from smw.ingest.boxoffice import ChartRow

TODAY = date(2026, 7, 1)

def _group(*titles):
    ranked = list(titles) + [f"Pad{i}" for i in range(10 - len(titles))]
    return Group("g", "G", {"u": PlayerPicks("u", tuple(ranked), ("DH1", "DH2", "DH3"))})

def _films(season, **kw):
    args = dict(groups=[], chart_rows=[], grosses={}, carried=set(),
                overrides={}, preopening={}, today=TODAY)
    args.update(kw)
    return {f.title: f for f in build_films(season, **args)}

def test_candidate_set_union(season):
    films = _films(
        season,
        groups=[_group("Picked Film")],
        chart_rows=[ChartRow("Chart Film", 100.0, date(2026, 5, 8), False)],
        grosses={"Chart Film": 100.0, "Carried Film": 50.0},
        carried={"Carried Film"},
        preopening={"Analyst Film": PreopeningEstimate(release_date=date(2026, 8, 1))},
    )
    for t in ("Picked Film", "Chart Film", "Carried Film", "Analyst Film",
              "DH1", "Pad0"):
        assert t in films

def test_chart_contenders_cap(season):
    rows = [ChartRow(f"C{i:03d}", 1000.0 - i, date(2026, 5, 8), False) for i in range(40)]
    films = _films(season, chart_rows=rows,
                   grosses={r.title: r.gross for r in rows})
    # top `chart_contenders` (25) by gross admitted; the rest only if carried/picked
    assert "C000" in films and "C024" in films and "C025" not in films

def test_release_date_precedence(season):
    est = PreopeningEstimate(release_date=date(2026, 8, 20))
    films = _films(
        season,
        chart_rows=[ChartRow("OnChart", 10.0, date(2026, 6, 5), False)],
        grosses={"OnChart": 10.0, "GrossOnly": 5.0},
        carried={"GrossOnly"},
        overrides={"OnChart": Override(release_date=date(2026, 6, 12))},
        preopening={"AnalystOnly": est},
    )
    assert films["OnChart"].release_date == date(2026, 6, 12)   # override beats chart
    assert films["AnalystOnly"].release_date == date(2026, 8, 20)  # estimate file
    assert films["GrossOnly"].release_date == TODAY             # positive gross, no date info
    films2 = _films(season, groups=[_group("NoData")])
    assert films2["NoData"].release_date == season.window_end   # nothing at all

def test_status_inference(season):
    films = _films(
        season,
        chart_rows=[ChartRow("Playing", 10.0, date(2026, 6, 5), False)],
        grosses={"Playing": 10.0, "Faded": 5.0},
        carried={"Faded"},
        overrides={"Forced": Override(status="closed"), "Playing2": Override()},
        groups=[_group("Future", "Forced")],
        preopening={"Future": PreopeningEstimate(release_date=date(2026, 8, 1))},
    )
    assert films["Playing"].status == "in_theaters"   # gross > 0, on chart
    assert films["Faded"].status == "closed"          # gross > 0, absent from chart
    assert films["Future"].status == "pre_release"    # release date after today
    assert films["Forced"].status == "closed"         # explicit override wins

def test_category_from_override_default_wide(season):
    films = _films(season, groups=[_group("Toon")],
                   overrides={"Toon": Override(category="animated_family")})
    assert films["Toon"].category == "animated_family"
    assert films["Pad0"].category == "wide"

def test_roster_variant_resolves_to_canonical_gross(season):
    # Alias application point 2 (§6.5): the roster's spelling finds the canonical record.
    films = _films(
        season,
        groups=[_group("Variant Spelling")],
        grosses={"Canonical": 42.0},
        carried={"Canonical"},
        overrides={"Variant Spelling": Override(alias_of="Canonical")},
    )
    assert "Variant Spelling" not in films
    assert films["Canonical"].cumulative_gross == 42.0
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_build_films.py -v` — Expected: FAIL with import error.

- [ ] **Step 3: Append to `smw/catalog/normalize.py`**

```python
# --- appended below the Task 6 content; add these imports at the top of the file:
# from smw.config.groups import Group
# from smw.config.season import Season


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
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_build_films.py -v` — Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: film catalog with candidate set and status inference

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Mode A — decay model with observed blend and clamp (§7.2, §7.3)

**Files:**
- Create: `smw/model/decay.py`, `tests/test_decay.py`

**Interfaces:**
- Consumes: `Season`.
- Produces (in `smw.model.decay`):
  - `DOW_WEIGHTS: tuple[float, ...]` — Mon–Sun `(0.07, 0.10, 0.07, 0.06, 0.22, 0.26, 0.22)`.
  - `day_weight(release_date: date, d: int) -> float` — day `d`'s share of its week: DOW weights (offset from the release weekday) inside week 0, uniform `1/7` afterwards.
  - `decay_sigma(weeks_observed: int) -> float` — 0.30 at ≤0, 0.10 at ≥6, linear between.
  - `blended_wow(observations: list[tuple[date, float]], default: float) -> float` — observed geometric-mean decay blended with the category default, clamped to `[0.01, 1.00]`. Observations must be date-sorted (Task 7 guarantees it).
  - `project_decay(cumulative: float, release_date: date, wow: float, season: Season, today: date) -> tuple[float, float]` — returns `(median_in_window_gross, sigma)`; raises `ValueError` if `today < release_date`.
- Tasks 10 and 11 import `DOW_WEIGHTS` and `day_weight` from here — one source of truth for the week shape (§7.4's 0.70 must stay derived from it).

**Implementation note (the arithmetic, unified):** back-calibration and forward projection both walk days. Day `d` (0-based from release) earns `week_1 × wow^(d//7) × day_weight(d)`. Summing that over the observed days and dividing the actual cumulative by it recovers `week_1` (§7.2 step 4 exactly — a full week's weights sum to 1.0); summing it over the remaining in-window days is the forward projection (§7.2 step 5). One loop over ≤130 days per film; no closed forms to get wrong.

- [ ] **Step 1: Write the failing tests** — `tests/test_decay.py`:

```python
import math
from datetime import date, timedelta
import pytest
from smw.model.decay import (
    DOW_WEIGHTS, blended_wow, day_weight, decay_sigma, project_decay,
)

FRI_MAY_1 = date(2026, 5, 1)  # 2026-05-01 is a Friday

def test_dow_weights_sum_to_one():
    assert math.isclose(sum(DOW_WEIGHTS), 1.0)

def test_day_weight_week_one_uses_dow_week_two_uniform():
    assert day_weight(FRI_MAY_1, 0) == DOW_WEIGHTS[4]   # release Friday
    assert day_weight(FRI_MAY_1, 1) == DOW_WEIGHTS[5]   # Saturday
    assert day_weight(FRI_MAY_1, 9) == pytest.approx(1 / 7)

def test_sigma_taper():
    assert decay_sigma(0) == 0.30
    assert decay_sigma(6) == 0.10
    assert decay_sigma(3) == pytest.approx(0.30 - 0.20 * 3 / 6)
    assert decay_sigma(10) == 0.10

def _synthetic_cumulative(week_1, wow, release, upto):
    days = (upto - release).days
    return sum(week_1 * wow ** (d // 7) * day_weight(release, d) for d in range(days))

def test_back_calibration_round_trips(season):
    # A film generated by pure geometric decay must project to its own full-window total.
    week_1, wow = 100_000_000.0, 0.55
    today = FRI_MAY_1 + timedelta(days=24)  # mid-week, partial week 4
    cumulative = _synthetic_cumulative(week_1, wow, FRI_MAY_1, today)
    full = _synthetic_cumulative(week_1, wow, FRI_MAY_1,
                                 season.window_end + timedelta(days=1))
    median, _ = project_decay(cumulative, FRI_MAY_1, wow, season, today)
    assert median == pytest.approx(full, rel=1e-9)

def test_pre_release_date_raises(season):
    with pytest.raises(ValueError):
        project_decay(1.0, date(2026, 7, 1), 0.55, season, date(2026, 6, 30))

def test_frozen_past_window_end(season):
    median, _ = project_decay(500.0, FRI_MAY_1, 0.55, season, season.window_end)
    assert median == 500.0

def test_degenerate_day_zero_projects_from_week_two(season):
    median, sigma = project_decay(50_000_000.0, FRI_MAY_1, 0.5, season, FRI_MAY_1)
    assert median > 50_000_000.0
    assert sigma == 0.30
    # cumulative treated as week one; remaining tail is week_1 * (w + w^2 + ...)
    expected_tail = sum(
        50_000_000.0 * 0.5 ** (d // 7) * day_weight(FRI_MAY_1, d)
        for d in range(7, (season.window_end - FRI_MAY_1).days + 1)
    )
    assert median == pytest.approx(50_000_000.0 + expected_tail)

def test_blend_defaults_below_three_snapshots():
    d = date(2026, 6, 1)
    assert blended_wow([], 0.55) == 0.55
    assert blended_wow([(d, 100.0)], 0.55) == 0.55
    assert blended_wow([(d, 100.0), (d + timedelta(days=7), 150.0)], 0.55) == 0.55

def test_blend_pulls_toward_observed():
    d = date(2026, 6, 1)
    obs = [(d, 100.0), (d + timedelta(days=7), 180.0), (d + timedelta(days=14), 220.0)]
    # deltas 80, 40 → ratio 0.5; weight 2/5 → 0.4*0.5 + 0.6*0.55 = 0.53
    assert blended_wow(obs, 0.55) == pytest.approx(0.53)

def test_blend_full_weight_at_six_snapshots():
    d = date(2026, 6, 1)
    obs = [(d + timedelta(days=7 * i), 100.0 * (2 - 0.5 ** i)) for i in range(6)]
    ratios_only = blended_wow(obs, 0.99)
    assert ratios_only == pytest.approx(0.5, rel=1e-6)  # default contributes nothing

def test_clamp_growth_cannot_exceed_one():
    # §13.5 named gap: grosses that grew between observations must clamp to ≤ 1.0.
    d = date(2026, 6, 1)
    obs = [(d, 100.0), (d + timedelta(days=7), 150.0),
           (d + timedelta(days=14), 260.0), (d + timedelta(days=21), 500.0),
           (d + timedelta(days=28), 1000.0), (d + timedelta(days=35), 3000.0)]
    assert blended_wow(obs, 0.55) <= 1.0

def test_zero_delta_pairs_skipped():
    d = date(2026, 6, 1)
    obs = [(d, 100.0), (d + timedelta(days=7), 100.0), (d + timedelta(days=14), 100.0)]
    assert blended_wow(obs, 0.55) == 0.55  # no positive-delta pairs → default
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_decay.py -v` — Expected: FAIL with import error.

- [ ] **Step 3: Implement `smw/model/decay.py`**

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_decay.py -v` — Expected: 11 PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: decay model with observed-WoW blend and clamp

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: Mode B — analyst model with finite-run derivation (§7.4)

**Files:**
- Create: `smw/model/preopening.py`, `tests/test_preopening.py`

**Interfaces:**
- Consumes: `DOW_WEIGHTS`, `day_weight` from `smw.model.decay`; `Season`.
- Produces (in `smw.model.preopening`):
  - `OPENING_WEEK_SHARE: float` — computed as `sum(DOW_WEIGHTS[4:7])` (= 0.70, Fri+Sat+Sun), never a literal, so it changes with the weights (§7.4 requirement).
  - `CONFIDENCE_SIGMA: dict[str, float]` — `{"high": 0.20, "med": 0.30, "low": 0.45}`.
  - `derive_wow(opening: float, total: float, n_weeks: int, fallback: float) -> float` — bisection on `(0, 1)` for `total = week_1 × (1 − w^N)/(1 − w)` with `week_1 = opening / OPENING_WEEK_SHARE`; returns `fallback` when no root exists in `(0, 1)`.
  - `project_preopening(release_date: date, opening: float, total: float, confidence: str, category_wow: float, season: Season) -> tuple[float, float]` — `(median_in_window_gross, sigma)`; `(0.0, 0.0)` when `release_date > season.window_end`.

- [ ] **Step 1: Write the failing tests** — `tests/test_preopening.py`:

```python
import math
from datetime import date, timedelta
import pytest
from smw.model.decay import DOW_WEIGHTS, day_weight
from smw.model.preopening import (
    CONFIDENCE_SIGMA, OPENING_WEEK_SHARE, derive_wow, project_preopening,
)

def test_opening_week_share_tied_to_dow_weights():
    assert OPENING_WEEK_SHARE == pytest.approx(sum(DOW_WEIGHTS[4:7]))
    assert OPENING_WEEK_SHARE == pytest.approx(0.70)

def test_derive_wow_solves_finite_series():
    # week_1 = 70/0.7 = 100; with w=0.5, N=10: total = 100*(1-0.5^10)/0.5 ≈ 199.8047
    w = derive_wow(70.0, 100.0 * (1 - 0.5 ** 10) / 0.5, 10, fallback=0.99)
    assert w == pytest.approx(0.5, abs=1e-6)

def test_derive_wow_no_root_falls_back():
    # total below week_1: impossible run shape → category default
    assert derive_wow(70.0, 50.0, 10, fallback=0.55) == 0.55
    # total above N*week_1 (limit as w→1): also no root in (0,1)
    assert derive_wow(70.0, 100.0 * 11, 10, fallback=0.55) == 0.55

def test_after_window_scores_zero(season):
    median, sigma = project_preopening(
        date(2026, 9, 8), 70_000_000, 200_000_000, "high", 0.55, season)
    assert (median, sigma) == (0.0, 0.0)

def test_sigma_by_confidence(season):
    rel = date(2026, 6, 19)
    for conf, expect in (("high", 0.20), ("med", 0.30), ("low", 0.45)):
        _, sigma = project_preopening(rel, 70_000_000, 200_000_000, conf, 0.55, season)
        assert sigma == expect

def test_long_run_caps_at_analyst_total(season):
    # Early release, whole run inside the window → in-window sum equals the run
    # total but must never exceed the analyst estimate.
    median, _ = project_preopening(
        date(2026, 5, 1), 70_000_000, 150_000_000, "med", 0.55, season)
    assert median <= 150_000_000
    assert median == pytest.approx(150_000_000, rel=0.01)

def test_late_window_release_projects_partial(season):
    # Opens 3 weeks before window_end: in-window gross is legitimately far below total.
    rel = season.window_end - timedelta(days=21)
    median, _ = project_preopening(rel, 140_000_000, 400_000_000, "med", 0.55, season)
    assert 140_000_000 < median < 400_000_000
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_preopening.py -v` — Expected: FAIL with import error.

- [ ] **Step 3: Implement `smw/model/preopening.py`**

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_preopening.py -v` — Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: pre-release analyst model with finite-run WoW derivation

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: Projection dispatch, display bands, warnings, `MovieCatalog` (§7.1, §7.5, §7.6, §8, §3.4)

**Files:**
- Create: `smw/model/project.py`, `tests/test_project.py`

**Interfaces:**
- Consumes: `Film` (Task 8), `blended_wow`/`project_decay` (Task 9), `project_preopening` (Task 10), `Season`.
- Produces (in `smw.model.project`):
  - `Z80 = 1.2816` (standard normal 90th percentile).
  - `Projection` frozen dataclass: `title: str`, `median: float`, `sigma: float`, `floor: float`, `source: str` (one of `"final gross"`, `"decay model"`, `"analyst estimate"`, `"release after window"`, `"no analyst entry"`), `p10: float`, `p90: float`.
  - `MovieCatalog` frozen dataclass (§3.4 — roster-independent, NO roster data): `films: list[Film]`, `projections: list[Projection]` (same order as `films`), `warnings: list[str]`.
  - `bands(median: float, sigma: float, floor: float) -> tuple[float, float]` — §7.6 closed form.
  - `build_catalog(season: Season, films: list[Film], history: dict[str, list[tuple[date, float]]], picked_titles: set[str], overrides: dict[str, Override], today: date) -> MovieCatalog`. `picked_titles` is a plain set of canonical titles — passing the set, not `Group`, keeps roster data out of the catalog type. Warnings: one listing picked films with no explicit category (§8), one listing picked films with no projection (§7.5).
- Simulation (T12) consumes `catalog.projections`; render (T14+) consumes both lists and `warnings`.

- [ ] **Step 1: Write the failing tests** — `tests/test_project.py`:

```python
import math
from datetime import date, timedelta
import pytest
from smw.catalog.normalize import Film, Override, PreopeningEstimate
from smw.model.project import Z80, MovieCatalog, bands, build_catalog

TODAY = date(2026, 7, 1)

def _film(title="F", status="in_theaters", gross=0.0, release=date(2026, 5, 1),
          category="wide", estimate=None):
    return Film(title, release, status, category, gross, estimate)

def _catalog(season, films, history=None, picked=None, overrides=None, today=TODAY):
    return build_catalog(season, films, history or {}, picked or set(),
                         overrides or {}, today)

def test_closed_film_is_final_gross(season):
    cat = _catalog(season, [_film(status="closed", gross=500.0)])
    p = cat.projections[0]
    assert (p.median, p.sigma, p.floor, p.source) == (500.0, 0.0, 500.0, "final gross")
    assert p.p10 == p.p90 == 500.0

def test_in_theaters_uses_decay_with_floor(season):
    cat = _catalog(season, [_film(gross=100_000_000.0)])
    p = cat.projections[0]
    assert p.source == "decay model"
    assert p.floor == 100_000_000.0
    assert p.median > p.floor

def test_pre_release_with_complete_estimate(season):
    est = PreopeningEstimate(release_date=date(2026, 8, 1),
                             opening_weekend_estimate=70_000_000,
                             total_domestic_estimate=200_000_000, confidence="high")
    cat = _catalog(season, [_film(status="pre_release", release=date(2026, 8, 1),
                                  estimate=est)])
    p = cat.projections[0]
    assert p.source == "analyst estimate"
    assert p.floor == 0.0
    assert p.median > 0

def test_pre_release_after_window(season):
    est = PreopeningEstimate(release_date=date(2026, 9, 20),
                             opening_weekend_estimate=70_000_000,
                             total_domestic_estimate=200_000_000, confidence="high")
    cat = _catalog(season, [_film(status="pre_release", release=date(2026, 9, 20),
                                  estimate=est)])
    p = cat.projections[0]
    assert (p.median, p.source) == (0.0, "release after window")

def test_pre_release_without_estimate_is_zero_no_fallback(season):
    cat = _catalog(season, [_film(status="pre_release", release=date(2026, 8, 1))])
    p = cat.projections[0]
    assert (p.median, p.sigma, p.floor, p.source) == (0.0, 0.0, 0.0, "no analyst entry")

def test_bands_closed_form():
    p10, p90 = bands(200.0, 0.3, 120.0)
    assert p10 == pytest.approx(120.0 + 80.0 * math.exp(-Z80 * 0.3))
    assert p90 == pytest.approx(120.0 + 80.0 * math.exp(Z80 * 0.3))

def test_warning_for_unclassified_picked_film(season):
    films = [_film(title="Toon", gross=10.0), _film(title="Classified", gross=10.0)]
    cat = _catalog(season, films, picked={"Toon", "Classified"},
                   overrides={"Classified": Override(category="wide")})
    assert any("Toon" in w and "category" in w.lower() for w in cat.warnings)
    assert not any("Classified" in w for w in cat.warnings)

def test_warning_for_picked_film_without_projection(season):
    films = [_film(title="Mystery", status="pre_release", release=date(2026, 8, 1))]
    cat = _catalog(season, films, picked={"Mystery"})
    assert any("Mystery" in w and "no projection" in w.lower() for w in cat.warnings)

def test_observed_history_feeds_blend(season):
    d0 = date(2026, 5, 4)
    history = {"F": [(d0 + timedelta(days=7 * i), [100.0, 180.0, 220.0][i])
                     for i in range(3)]}
    with_hist = _catalog(season, [_film(gross=220.0)], history=history)
    without = _catalog(season, [_film(gross=220.0)])
    assert with_hist.projections[0].median != without.projections[0].median
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_project.py -v` — Expected: FAIL with import error.

- [ ] **Step 3: Implement `smw/model/project.py`**

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_project.py -v` — Expected: 9 PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: projection dispatch, display bands, operator warnings

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 12: Simulation — sampling, trials, aggregation (§9.1–9.5)

**Files:**
- Create: `smw/model/simulate.py`, `tests/test_simulate.py`

**Interfaces:**
- Consumes: `Season`, `Group`, `MovieCatalog`, `score_player`/`score_breakdown` from `smw.score.rules`.
- Produces (in `smw.model.simulate`):
  - `MIN_FILMS_FOR_TOP_TEN = 10` — structural constant (§9.5); `SimulationError(RuntimeError)` raised when fewer than 10 films have a positive-median projection.
  - `Scenario` frozen dataclass: `films: list[str]` (exactly 10), `grid: dict[str, list[int]]` (10 ints per player), `totals: dict[str, int]`, `win_pct: float` (0–100), `margin: int`.
  - `SimResult` frozen dataclass: `win_prob`, `tie_prob`, `median_pts`, `p10_pts`, `p90_pts` — each `dict[str, float]` keyed by username — and `scenarios: dict[str, Scenario | None]` (filled by Task 13; Task 12 sets every value to `None`).
  - `simulate(season: Season, group: Group, catalog: MovieCatalog) -> SimResult`, seeded from `season.seed`.
- Internal seams Task 13 builds on: `_sample(season, projections) -> np.ndarray` of shape `(trials, films)` and the per-trial `top10` index array — structure `simulate()` so the scenario step receives `(samples' argsort top-10 indices, titles, score_matrix, is_top, winners_per_trial)`.

- [ ] **Step 1: Write the failing tests** — `tests/test_simulate.py`:

```python
from datetime import date
import numpy as np
import pytest
from smw.catalog.normalize import Film
from smw.model.project import MovieCatalog, Projection, bands
from smw.model.simulate import MIN_FILMS_FOR_TOP_TEN, SimulationError, simulate

def _proj(title, median, sigma=0.2, floor=0.0):
    p10, p90 = bands(median, sigma, floor)
    return Projection(title, median, sigma, floor, "decay model", p10, p90)

def _film(title):
    return Film(title, date(2026, 5, 1), "in_theaters", "wide", 0.0, None)

def _catalog(n=18):
    # M01 strongest ... M18 weakest, comfortable spacing
    projs = [_proj(f"M{i:02d}", 400_000_000.0 / i) for i in range(1, n + 1)]
    return MovieCatalog([_film(p.title) for p in projs], projs, [])

def test_fewer_than_ten_projected_films_raises(season, group):
    projs = [_proj(f"M{i:02d}", 100.0) for i in range(1, 9)] + [_proj("M09", 0.0)]
    cat = MovieCatalog([_film(p.title) for p in projs], projs, [])
    with pytest.raises(SimulationError):
        simulate(season, group, cat)

def test_deterministic_under_seed(season, group):
    a = simulate(season, group, _catalog())
    b = simulate(season, group, _catalog())
    assert a.win_prob == b.win_prob
    assert a.median_pts == b.median_pts

def test_percentile_ordering(season, group):
    r = simulate(season, group, _catalog())
    for u in group.players:
        assert r.p10_pts[u] <= r.median_pts[u] <= r.p90_pts[u]

def test_win_plus_tie_at_most_one_and_probs_sum(season, group):
    r = simulate(season, group, _catalog())
    for u in group.players:
        assert r.win_prob[u] + r.tie_prob[u] <= 1.0 + 1e-9
    # strict-win probs across players + fraction of tied trials == 1
    # (every trial has either exactly one strict winner or a tie for first)
    strict_total = sum(r.win_prob.values())
    any_tie = 1.0 - strict_total
    assert any_tie >= -1e-9
    tied_players_bound = sum(r.tie_prob.values())
    assert tied_players_bound >= any_tie * 2 - 1e-9  # a tie involves ≥ 2 players

def test_floor_is_never_breached(season, group, monkeypatch):
    # §9.2: assert min(samples) >= floor over a full trial run.
    import smw.model.simulate as sim
    captured = {}
    orig = sim._sample
    def spy(season_, projections):
        s = orig(season_, projections)
        captured["samples"] = s
        captured["floors"] = np.array([p.floor for p in projections])
        return s
    monkeypatch.setattr(sim, "_sample", spy)
    projs = [_proj(f"M{i:02d}", 400_000_000.0 / i, sigma=0.4,
                   floor=200_000_000.0 / i) for i in range(1, 15)]
    cat = MovieCatalog([_film(p.title) for p in projs], projs, [])
    simulate(season, group, cat)
    assert (captured["samples"] >= captured["floors"][None, :] - 1e-6).all()

def test_dominant_player_wins(season, group):
    # alice picked M01..M10 in order == projection order; she must dominate.
    r = simulate(season, group, _catalog())
    assert r.win_prob["alice"] > 0.9
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_simulate.py -v` — Expected: FAIL with import error.

- [ ] **Step 3: Implement `smw/model/simulate.py`** (aggregation exactly per §9.4; scenarios stubbed as `None` until Task 13)

```python
"""Monte Carlo season simulation (spec §9)."""
from dataclasses import dataclass

import numpy as np

from smw.config.groups import Group
from smw.config.season import Season
from smw.model.project import MovieCatalog, Projection
from smw.score.rules import score_player

MIN_FILMS_FOR_TOP_TEN = 10  # structural: you cannot rank a top ten out of nine films


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
    # Task 13 replaces this stub with medoid selection (§9.6).
    return {u: None for u in players}
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_simulate.py -v` — Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: seeded Monte Carlo simulation with floored sampling

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 13: Representative winning scenarios — medoid selection (§9.6)

**Files:**
- Modify: `smw/model/simulate.py` (replace the `_scenarios` stub)
- Test: `tests/test_scenarios.py`

**Interfaces:**
- Consumes: everything Task 12 produced.
- Produces: `_scenarios(...)` returning `dict[str, Scenario | None]` — for each player the medoid of their strict-win trials under Spearman-footrule distance over rank vectors (top-ten position, 11 for absentees), capped at 1500 sampled trials with a per-player derived seed; `None` for a player who never strictly wins. `Scenario.grid` values come from `score_breakdown` against the medoid trial's finish order, padded/truncated to exactly 10 ints; `margin` = winner total − best runner-up total (≥ 1).

- [ ] **Step 1: Write the failing tests** — `tests/test_scenarios.py`:

```python
from datetime import date
import pytest
from smw.catalog.normalize import Film
from smw.config.groups import Group, PlayerPicks
from smw.model.project import MovieCatalog, Projection, bands
from smw.model.simulate import simulate
from smw.score.rules import score_player

def _proj(title, median, sigma=0.2, floor=0.0):
    p10, p90 = bands(median, sigma, floor)
    return Projection(title, median, sigma, floor, "decay model", p10, p90)

def _film(title):
    return Film(title, date(2026, 5, 1), "in_theaters", "wide", 0.0, None)

def _catalog(n=18):
    projs = [_proj(f"M{i:02d}", 400_000_000.0 / i) for i in range(1, n + 1)]
    return MovieCatalog([_film(p.title) for p in projs], projs, [])

@pytest.fixture
def hopeless_group(group):
    # dave picks films that essentially never chart → no winning path
    players = dict(group.players)
    players["dave"] = PlayerPicks(
        "dave", tuple(f"Z{i}" for i in range(10)), ("Z10", "Z11", "Z12"))
    return Group(group.group_id, group.display_name, players)

def test_scenario_structure(season, group):
    r = simulate(season, group, _catalog())
    s = r.scenarios["alice"]
    assert s is not None
    assert len(s.films) == 10 and len(set(s.films)) == 10
    for u in group.players:
        assert len(s.grid[u]) == 10
        # grid rows are the score breakdown of a REAL trial: totals must agree
        assert sum(s.grid[u]) == s.totals[u]
        assert s.totals[u] == score_player(group.players[u], s.films)
    assert s.win_pct == pytest.approx(r.win_prob["alice"] * 100, abs=0.1)

def test_winner_actually_wins_with_margin(season, group):
    r = simulate(season, group, _catalog())
    s = r.scenarios["alice"]
    others = [v for u, v in s.totals.items() if u != "alice"]
    assert s.totals["alice"] - max(others) == s.margin
    assert s.margin >= 1

def test_player_with_no_path_gets_none(season, hopeless_group):
    r = simulate(season, hopeless_group, _catalog())
    assert r.scenarios["dave"] is None

def test_scenarios_reproducible(season, group):
    a = simulate(season, group, _catalog())
    b = simulate(season, group, _catalog())
    assert a.scenarios["alice"].films == b.scenarios["alice"].films
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_scenarios.py -v` — Expected: FAIL (`scenarios["alice"] is None` from the stub).

- [ ] **Step 3: Replace `_scenarios` in `smw/model/simulate.py`**

```python
import numpy as _np  # (np already imported at module top; shown for completeness)

from smw.score.rules import score_breakdown

_MEDOID_CAP = 1500


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
```

Also remove the Task 12 stub and add `from smw.score.rules import score_breakdown` to the module's imports (drop the illustrative `import numpy as _np` line — `np` is already imported).

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_scenarios.py tests/test_simulate.py -v` — Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: medoid winning scenarios via Spearman footrule

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 14: Render foundation — Jinja env, theme, nav, base template, rules page (§11.2, §11.4, §13.1–13.2)

**Files:**
- Create: `smw/render/page.py`, `smw/render/templates/base.html.j2`, `smw/render/templates/rules.html.j2`, `smw/render/static/site.css`, `smw/render/static/theme.js`, `tests/test_page.py`

**Interfaces:**
- Consumes: `Season`, `Group`.
- Produces (in `smw.render.page`):
  - `make_env() -> jinja2.Environment` — `autoescape=True` unconditionally (never `select_autoescape`), filters `money` and `json_embed` registered.
  - `json_embed(obj) -> Markup` — compact, `sort_keys=True`, `<` escaped as `\u003c` (§11.4).
  - `fmt_money(x: float) -> str` — `$1.2B` / `$310.5M` / `$468K` / `$0`; deterministic.
  - `base_context(season: Season, group: Group, active: str, today: date) -> dict` — css text, theme js text, nav model, season header strings; every page renderer merges its own context over this.
  - `write_page(env, template_name: str, out_dir: Path, filename: str, context: dict) -> None`.
  - `render_rules(env, out_dir, ctx) -> None` — writes `rules.html`.
- Templates: `base.html.j2` exposes blocks `content` and `head_extra`; nav pills in fixed order Leaderboard/What If?/Winning Scenarios/Odds Over Time, `aria-current="page"` on the active one, all four always real links (§11.2); theme-resolution script inline in `<head>` before any body content (§13.2); footer links only `data.json` and `rules.html` (both relative); theme toggle button with `aria-label`.

- [ ] **Step 1: Write the failing tests** — `tests/test_page.py`:

```python
from datetime import date
import re
from smw.render.page import base_context, fmt_money, json_embed, make_env, write_page

TODAY = date(2026, 8, 15)

def _render_rules(tmp_path, season, group):
    env = make_env()
    ctx = base_context(season, group, active="rules", today=TODAY)
    write_page(env, "rules.html.j2", tmp_path, "rules.html", ctx)
    return (tmp_path / "rules.html").read_text()

def test_autoescape_is_forced_on():
    env = make_env()
    assert env.autoescape is True  # not extension-guessed

def test_json_embed_escapes_script_breakout():
    out = str(json_embed({"t": "</script><b>"}))
    assert "</script" not in out
    assert "\\u003c/script" in out

def test_fmt_money():
    assert fmt_money(1_234_000_000) == "$1.2B"
    assert fmt_money(310_491_022) == "$310.5M"
    assert fmt_money(468_000) == "$468K"
    assert fmt_money(0) == "$0"

def test_theme_script_in_head_before_body(tmp_path, season, group):
    html = _render_rules(tmp_path, season, group)
    head = html.split("</head>")[0]
    assert "prefers-color-scheme" in head or "data-theme" in head
    assert html.index("data-theme") < html.index("<body")

def test_nav_pills_all_live_links_with_aria_current(tmp_path, season, group):
    html = _render_rules(tmp_path, season, group)
    for href in ("index.html", "whatif.html", "scenarios.html", "history.html"):
        assert re.search(rf'<a[^>]+href="{href}"', html)
    # rules page is footer-linked, not a nav pill: no pill is current on it
    assert 'aria-current="page"' not in html

def test_scoring_rules_reproduced_on_site(tmp_path, season, group):
    html = _render_rules(tmp_path, season, group)
    for needle in ("13", "10", "7", "5", "3", "dark horse", "no tiebreaker"):
        assert needle.lower() in html.lower()

def test_no_external_references(tmp_path, season, group):
    html = _render_rules(tmp_path, season, group)
    assert "http://" not in html and "https://" not in html
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_page.py -v` — Expected: FAIL with import error.

- [ ] **Step 3: Implement `smw/render/page.py`**

```python
"""Jinja environment, shared context, page writer (spec §11.4, §13.1–13.2).
The render layer MUST NOT sort, rank, or compute — view models arrive finished."""
import json
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from smw.config.groups import Group
from smw.config.season import Season

TEMPLATES = Path(__file__).parent / "templates"
STATIC = Path(__file__).parent / "static"

NAV = [
    ("index.html", "🏆 Leaderboard", "leaderboard"),
    ("whatif.html", "🎬 What If?", "whatif"),
    ("scenarios.html", "🔮 Winning Scenarios", "scenarios"),
    ("history.html", "📈 Odds Over Time", "history"),
]


def json_embed(obj) -> Markup:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return Markup(text.replace("<", "\\u003c"))


def fmt_money(x: float) -> str:
    x = float(x)
    if x >= 1e9:
        return f"${x / 1e9:.1f}B"
    if x >= 1e6:
        return f"${x / 1e6:.1f}M"
    if x >= 1e3:
        return f"${x / 1e3:.0f}K"
    return f"${x:.0f}"


def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=True,  # forced unconditionally; titles come from an external site
        keep_trailing_newline=True,
    )
    env.filters["money"] = fmt_money
    env.filters["json_embed"] = json_embed
    return env


def base_context(season: Season, group: Group, active: str, today: date) -> dict:
    return {
        # Repo-controlled build assets, inlined verbatim; everything external
        # still flows through autoescape.
        "css": Markup((STATIC / "site.css").read_text()),
        "theme_js": Markup((STATIC / "theme.js").read_text()),
        "nav": NAV,
        "active": active,
        "display_name": group.display_name,
        "season_label": f"Summer {season.year}",
        "window_label": (
            f"{season.window_start.strftime('%b %-d')} – "
            f"{season.window_end.strftime('%b %-d, %Y')}"
        ),
        "refreshed": today.isoformat(),
        "wide_shell": False,
    }


def write_page(env: Environment, template_name: str, out_dir: Path,
               filename: str, context: dict) -> None:
    html = env.get_template(template_name).render(**context)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / filename).write_text(html)


def render_rules(env: Environment, out_dir: Path, ctx: dict) -> None:
    write_page(env, "rules.html.j2", out_dir, "rules.html",
               {**ctx, "title": "Scoring rules"})
```

- [ ] **Step 4: Write `smw/render/static/theme.js`** (two halves; the resolver is inlined in `<head>`, the toggle handler at the end of `<body>`)

```javascript
// -- resolver: runs in <head>, before any body content paints (§13.2 [Changed])
(function () {
  var t = null;
  try { t = localStorage.getItem("theme"); } catch (e) {}
  if (t === "dark" || t === "light") {
    document.documentElement.setAttribute("data-theme", t);
  }
  // no stored choice: leave attribute off; the prefers-color-scheme CSS block applies
})();
```

and append the toggle handler (the base template places this whole file in head; the
handler waits for DOM):

```javascript
document.addEventListener("DOMContentLoaded", function () {
  var btn = document.getElementById("theme-toggle");
  if (!btn) return;
  btn.addEventListener("click", function () {
    var root = document.documentElement;
    var dark = root.getAttribute("data-theme") === "dark" ||
      (!root.getAttribute("data-theme") &&
       matchMedia("(prefers-color-scheme: dark)").matches);
    var next = dark ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) {}
  });
});
```

- [ ] **Step 5: Write `smw/render/templates/base.html.j2`**

```jinja
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} · {{ display_name }}</title>
<script>{{ theme_js }}</script>
<style>{{ css }}</style>
{% block head_extra %}{% endblock %}
</head>
<body>
<div class="shell{% if wide_shell %} wide{% endif %}">
<header>
  <div class="masthead">
    <h1>{{ display_name }}</h1>
    <p class="season-line">{{ season_label }} · {{ window_label }} · refreshed {{ refreshed }}</p>
    <button id="theme-toggle" type="button" aria-label="Toggle light/dark theme">◐</button>
  </div>
  <nav aria-label="Site">
    {% for href, label, key in nav -%}
    <a class="pill{% if key == active %} current{% endif %}" href="{{ href }}"
       {% if key == active %}aria-current="page"{% endif %}>{{ label }}</a>
    {% endfor -%}
  </nav>
</header>
<main>
{% block content %}{% endblock %}
</main>
<footer>
  <a href="data.json">data.json</a> · <a href="rules.html">Scoring rules</a>
</footer>
</div>
</body>
</html>
```

Note the theme script tag: `theme_js` and `css` are inlined as `Markup` (see `base_context`) because Jinja autoescaping would mangle `&&` inside `<script>`. Both are repo-controlled build assets, not external data; every external string still goes through autoescape.

- [ ] **Step 6: Write `smw/render/templates/rules.html.j2`** (§13.1: rules reproduced on-site; content restates §2)

```jinja
{% extends "base.html.j2" %}
{% block content %}
<h2>Scoring rules</h2>
<p>Before the season, each player submits <strong>10 ranked picks</strong> — the films they
believe will gross the most at the domestic box office during the wager window, in
predicted finish order — plus <strong>3 dark horses</strong>, unordered. All 13 titles must
be distinct. Rosters lock when the window opens.</p>
<p>The actual top ten is the ten films with the highest domestic gross earned
<em>inside the window</em>, ranked descending. Money earned before or after the window
does not count.</p>
<h3>Ranked picks</h3>
<table>
<thead><tr><th>Condition</th><th>Points</th></tr></thead>
<tbody>
<tr><td>Not in the top ten</td><td>0</td></tr>
<tr><td>Exact match at position 1 or position 10</td><td>13</td></tr>
<tr><td>Exact match at positions 2–9</td><td>10</td></tr>
<tr><td>In the top ten, off by exactly 1 position</td><td>7</td></tr>
<tr><td>In the top ten, off by exactly 2 positions</td><td>5</td></tr>
<tr><td>In the top ten, off by 3 or more positions</td><td>3</td></tr>
</tbody>
</table>
<h3>Dark horses</h3>
<p>Each dark horse that finishes anywhere in the top ten scores <strong>1 point</strong>.</p>
<h3>Winning</h3>
<p>Highest total wins. The maximum possible score is 109. There is
<strong>no tiebreaker</strong> — tied players share the placement.</p>
{% endblock %}
```

- [ ] **Step 7: Write `smw/render/static/site.css`**

```css
/* Tokens: light on :root; explicit dark attribute; OS preference scoped so an
   explicit light choice wins (§13.2). */
:root {
  --bg: #faf9f6; --card: #ffffff; --ink: #1a1a20; --muted: #71717a;
  --border: #e4e4e7; --accent: #2563eb; --pos: #15803d; --neg: #b91c1c;
  --dim: #f4f4f5; --gold: #b45309;
}
[data-theme="dark"] {
  --bg: #131318; --card: #1c1c24; --ink: #e7e7ea; --muted: #9d9da8;
  --border: #33333e; --accent: #7aa2ff; --pos: #4ade80; --neg: #f87171;
  --dim: #22222b; --gold: #fbbf24;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #131318; --card: #1c1c24; --ink: #e7e7ea; --muted: #9d9da8;
    --border: #33333e; --accent: #7aa2ff; --pos: #4ade80; --neg: #f87171;
    --dim: #22222b; --gold: #fbbf24;
  }
}

* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  line-height: 1.5;
}
.shell { max-width: 720px; margin: 0 auto; padding: 1rem; }
.shell.wide { max-width: 1100px; }
.masthead { position: relative; }
.masthead h1 { margin: 0.5rem 0 0; font-size: 1.4rem; }
.season-line { color: var(--muted); margin: 0.2rem 0 1rem; font-size: 0.85rem; }
#theme-toggle {
  position: absolute; top: 0.5rem; right: 0; background: var(--card);
  color: var(--ink); border: 1px solid var(--border); border-radius: 999px;
  width: 2rem; height: 2rem; cursor: pointer;
}
nav { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 1.2rem; }
.pill {
  padding: 0.35rem 0.8rem; border-radius: 999px; text-decoration: none;
  color: var(--ink); background: var(--card); border: 1px solid var(--border);
  font-size: 0.9rem;
}
.pill.current { background: var(--accent); color: #fff; border-color: var(--accent); }

h2 { font-size: 1.15rem; margin: 1.6rem 0 0.6rem; }
table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
th, td { padding: 0.35rem 0.55rem; border-bottom: 1px solid var(--border); text-align: left; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.table-scroll { overflow-x: auto; }
.table-scroll thead th { position: sticky; top: 0; background: var(--bg); }

.cell-pos { color: var(--pos); font-weight: 600; }
.cell-zero { color: var(--muted); }
.cell-none { color: var(--border); }
.divider-row td {
  border-bottom: 2px dashed var(--muted); color: var(--muted);
  text-align: center; font-size: 0.8rem; padding: 0.15rem;
}
.badge {
  display: inline-block; font-size: 0.7rem; padding: 0.05rem 0.45rem;
  border-radius: 999px; background: var(--dim); color: var(--muted);
  border: 1px solid var(--border); white-space: nowrap;
}
.notice {
  background: var(--dim); border: 1px solid var(--border); border-radius: 8px;
  padding: 0.8rem 1rem; margin: 1rem 0; color: var(--muted);
}
.locked { text-align: center; padding: 4rem 1rem; color: var(--muted); }
.up { color: var(--pos); } .down { color: var(--neg); } .flat { color: var(--muted); }
details { margin: 0.5rem 0; }
details > summary { cursor: pointer; padding: 0.45rem 0; }
.stats-line { color: var(--muted); font-size: 0.85rem; }
footer { margin: 2.5rem 0 1rem; color: var(--muted); font-size: 0.85rem; }
footer a { color: var(--muted); }

@media (max-width: 700px) {
  body { font-size: 0.92rem; }
  th, td { padding: 0.25rem 0.35rem; }
  .two-col { grid-template-columns: 1fr !important; }
}
```

- [ ] **Step 8: Run to verify pass**

Run: `pytest tests/test_page.py -v` — Expected: 7 PASS.

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "feat: render foundation — env, theme, nav, base and rules pages

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 15: Leaderboard — view models, live + current-points modes, snapshot (§10.3, §12.1)

**Files:**
- Create: `smw/render/views.py`, `smw/render/templates/index.html.j2`, `tests/test_views.py`, `tests/test_leaderboard_render.py`, `tests/fixtures/snapshot_index.html` (generated in Step 8)
- Modify: `smw/render/page.py` (add `render_leaderboard`)

**Interfaces:**
- Consumes: `Season`, `Group`, `MovieCatalog`, `SimResult | None`, `score_player`/`ranked_pick_points` from rules.
- Produces (in `smw.render.views`) — the render layer's finished input; templates do zero sorting or arithmetic (§11.4):
  - `Cell(kind: str, pts: int)` — kind ∈ `{"pts", "zero", "none"}`.
  - `MatrixRow(rank: int, title: str, gross: float, cells: list[Cell])`.
  - `PlayerColumn(username: str, footer_pts: int, win_pct: float | None)` — `win_pct` `None` in current-points mode.
  - `DetailRow(label: str, title: str, projected_rank: int | None, diff: int | None, gross: float | None, pts: int, missing: bool)`.
  - `PlayerDetail(username: str, stats_line: str, rows: list[DetailRow], dark_rows: list[DetailRow])`.
  - `FilmRow(rank: int | None, title: str, released: str, badge: str, median: float, p10: float, p90: float, cumulative: float, source: str)`.
  - `LeaderboardView(mode, heading, columns, rows, divider_after, list_rows, details, films, notice)` — `mode` ∈ `{"live", "current"}`; `divider_after: int | None` (10, or None when ≤10 rows — §10.2); `list_rows: list[tuple[str, dict[str, str]]]` for the All Players' Lists grid.
  - `build_leaderboard_view(season, group, catalog, sim, current_points: dict[str, int], actual_top: list[str], reason: str | None, today) -> LeaderboardView`.
  - `projected_ranks(catalog) -> dict[str, int]` — rank across the whole catalog by median desc (ties broken by title), only films with `median > 0`; the single notion of "projected rank" (§12.1 rank semantics) — player detail and films table both read it.
- `render_leaderboard(env, out_dir, ctx, view)` in `page.py` writes `index.html` with the wide shell.

**Semantics locked in this task:**
- Live mode: matrix rows = top `season.matrix_rows` films by projected median (positive medians only); projected top ten = first ten of those ranks; a cell is `pts` when the row film sits in the projected top ten and on the player's roster (`ranked_pick_points(predicted, pos)`, or 1 for a dark horse), `zero` when on roster but outside the top ten, `none` otherwise. Columns ordered by simulated median points descending (tie → username). Footer row 1 is **the arithmetic sum of the cells above it** — NOT `sim.median_pts` (§12.1 footer total rule; the code comment is mandatory). Footer row 2 shows P(strict win) only. Stats line reuses the same footer sum.
- Current-points mode (`sim is None`): identical shape; rows ordered by cumulative gross descending (positive gross only); cells score against `actual_top`; footer row 1 = current pts; footer row 2 omitted entirely; stats line `N pts current`; detail tables collapse to `#`/Movie/Pts; notice carries the §9.5 reason string; **no projected value and no win percentage anywhere**.
- Diff: `pick_position − projected_rank` sign decides `▲ n` (projection above the pick, affirmative) / `▼ n` / `–`; `None` renders muted `—` with no arithmetic.
- Badges: source `release after window` → `won't score`; source `no analyst entry` → `no projection`; otherwise status maps `pre_release`→`pre-release`, `in_theaters`→`in theaters`, `closed`→`closed`.
- A picked film absent from the catalog gets a `DetailRow(missing=True)` placeholder, never a KeyError (§10.2).

- [ ] **Step 1: Write the failing view-model tests** — `tests/test_views.py`:

```python
from datetime import date
import pytest
from smw.catalog.normalize import Film
from smw.model.project import MovieCatalog, Projection, bands
from smw.model.simulate import simulate
from smw.render.views import build_leaderboard_view, projected_ranks
from smw.score.rules import score_player

TODAY = date(2026, 8, 15)

def _proj(title, median, floor=0.0, source="decay model"):
    p10, p90 = bands(median, 0.2, floor)
    return Projection(title, median, 0.2, floor, source, p10, p90)

def _film(title, gross=0.0, status="in_theaters"):
    return Film(title, date(2026, 5, 1), status, "wide", gross, None)

def _catalog(n=18):
    projs = [_proj(f"M{i:02d}", 400e6 / i, floor=100e6 / i) for i in range(1, n + 1)]
    films = [_film(p.title, gross=p.floor) for p in projs]
    return MovieCatalog(films, projs, [])

def _view(season, group, cat=None, with_sim=True, reason=None):
    cat = cat or _catalog()
    sim = simulate(season, group, cat) if with_sim else None
    actual = [f.title for f in sorted(cat.films, key=lambda f: -f.cumulative_gross)
              if f.cumulative_gross > 0][:10]
    current = {u: score_player(group.players[u], actual) for u in group.players}
    return build_leaderboard_view(season, group, cat, sim, current, actual,
                                  reason, TODAY)

def test_live_mode_shape(season, group):
    v = _view(season, group)
    assert v.mode == "live"
    assert v.heading == "🏆 Projected Standings"
    assert len(v.rows) == season.matrix_rows
    assert v.divider_after == 10
    assert [c.username for c in v.columns] == sorted(
        group.players, key=lambda u: (-_sim_median(season, group)[u], u))

def _sim_median(season, group):
    return simulate(season, group, _catalog()).median_pts

def test_footer_is_arithmetic_sum_of_cells(season, group):
    v = _view(season, group)
    for ci, col in enumerate(v.columns):
        assert col.footer_pts == sum(r.cells[ci].pts for r in v.rows)

def test_cell_states(season, group):
    v = _view(season, group)
    row1 = v.rows[0]           # M01, projected #1
    ci = [c.username for c in v.columns].index("alice")
    assert row1.cells[ci].kind == "pts"
    assert row1.cells[ci].pts == 13    # alice predicted M01 at #1
    row12 = v.rows[11]         # M12: on carol's roster (dark horse), outside top ten
    carol = [c.username for c in v.columns].index("carol")
    assert row12.cells[carol].kind == "zero"
    bob = [c.username for c in v.columns].index("bob")
    assert row12.cells[bob].kind == "none"  # bob never picked M12

def test_projected_ranks_whole_catalog(season):
    ranks = projected_ranks(_catalog())
    assert ranks["M01"] == 1
    assert ranks["M18"] == 18

def test_current_mode_no_forecast_artifacts(season, group):
    v = _view(season, group, with_sim=False, reason="only 3 films have non-zero projections")
    assert v.mode == "current"
    assert v.heading == "🏆 Current Standings"
    assert all(c.win_pct is None for c in v.columns)
    assert "only 3 films" in v.notice
    for d in v.details:
        assert "win" not in d.stats_line
        assert "projected" not in d.stats_line
    # cells are current points vs the actual top ten
    ci = [c.username for c in v.columns].index("alice")
    assert v.columns[ci].footer_pts == sum(r.cells[ci].pts for r in v.rows)

def test_divider_suppressed_with_ten_or_fewer_rows(season, group):
    v = _view(season, group, cat=_catalog(n=10))
    assert v.divider_after is None

def test_missing_picked_film_renders_placeholder(season, group):
    # M15..M18 exist; alice's dark horses M15-17 exist, but strip the catalog to 12
    v = _view(season, group, cat=_catalog(n=12))
    alice = next(d for d in v.details if d.username == "alice")
    assert any(r.missing for r in alice.dark_rows)  # M15+ absent → placeholder, no crash

def test_diff_arrows(season, group):
    v = _view(season, group)
    bob = next(d for d in v.details if d.username == "bob")
    # bob predicted M10 at #1; projection ranks it #10 → diff 1-10 = -9 → ▼
    row = next(r for r in bob.rows if r.title == "M10")
    assert row.diff == -9

def test_empty_roster_set_renders_empty_lists(season):
    from smw.config.groups import Group
    empty = Group("g", "G", {})
    cat = _catalog()
    v = build_leaderboard_view(season, empty, cat, None, {}, [], "r", TODAY)
    assert v.list_rows == [] or all(not d[1] for d in v.list_rows)
    assert v.columns == []
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_views.py -v` — Expected: FAIL with import error.

- [ ] **Step 3: Implement `smw/render/views.py`**

```python
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
        if p.source == "release after window":
            badge = "won't score"
        elif p.source == "no analyst entry":
            badge = "no projection"
        else:
            badge = BADGES[f.status]
        rows.append(FilmRow(ranks.get(f.title), f.title, f.release_date.isoformat(),
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
        rows.append((f"🐴 Dark Horse {i + 1}",
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
            stats = (f"{footer[u]} pts projected · {current_points.get(u, 0)} pts current"
                     f" · {sim.win_prob[u] * 100:.1f}% win")
        else:
            stats = f"{current_points.get(u, 0)} pts current"
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
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_views.py -v` — Expected: all PASS.

- [ ] **Step 5: Write `smw/render/templates/index.html.j2`**

```jinja
{% extends "base.html.j2" %}
{% block content %}
{% if view.notice %}<div class="notice">{{ view.notice }}</div>{% endif %}

<h2>{{ view.heading }}</h2>
<div class="table-scroll">
<table>
<thead>
<tr><th>#</th><th>Film</th>
  <th class="num">{% if view.mode == "live" %}Projected (in-window){% else %}Gross to date{% endif %}</th>
  {% for col in view.columns %}<th class="num">{{ col.username }}</th>{% endfor %}
</tr>
</thead>
<tbody>
{% for row in view.rows %}
<tr>
  <td>{{ row.rank }}</td><td>{{ row.title }}</td>
  <td class="num">{{ row.gross | money }}</td>
  {% for cell in row.cells %}
  <td class="num {% if cell.kind == "pts" %}cell-pos{% elif cell.kind == "zero" %}cell-zero{% else %}cell-none{% endif %}">
    {%- if cell.kind == "pts" %}{{ cell.pts }}{% elif cell.kind == "zero" %}0{% else %}—{% endif -%}
  </td>
  {% endfor %}
</tr>
{% if view.divider_after and loop.index == view.divider_after %}
<tr class="divider-row"><td colspan="{{ 3 + view.columns | length }}">Outside the top 10</td></tr>
{% endif %}
{% endfor %}
</tbody>
<tfoot>
<tr><td colspan="3">{% if view.mode == "live" %}Projected pts{% else %}Current pts{% endif %}</td>
  {% for col in view.columns %}<td class="num"><strong>{{ col.footer_pts }}</strong></td>{% endfor %}
</tr>
{% if view.mode == "live" %}
<tr><td colspan="3">Win odds</td>
  {% for col in view.columns %}<td class="num">{{ col.win_pct }}%</td>{% endfor %}
</tr>
{% endif %}
</tfoot>
</table>
</div>

<h2>All Players' Lists</h2>
{% if view.list_rows %}
<div class="table-scroll">
<table>
<thead><tr><th></th>{% for col in view.columns %}<th>{{ col.username }}</th>{% endfor %}</tr></thead>
<tbody>
{% for label, picks in view.list_rows %}
{% if loop.index == 11 %}
<tr class="divider-row"><td colspan="{{ 1 + view.columns | length }}">Dark Horses</td></tr>
{% endif %}
<tr><td>{{ label }}</td>{% for col in view.columns %}<td>{{ picks[col.username] }}</td>{% endfor %}</tr>
{% endfor %}
</tbody>
</table>
</div>
{% endif %}

<h2>Players</h2>
{% for d in view.details %}
<details>
<summary><strong>{{ d.username }}</strong> <span class="stats-line">{{ d.stats_line }}</span></summary>
<div class="table-scroll">
<table>
{% if view.mode == "live" %}
<thead><tr><th>#</th><th>Movie</th><th class="num">Projected rank</th><th class="num">Diff</th><th class="num">Projected gross</th><th class="num">Pts</th></tr></thead>
{% else %}
<thead><tr><th>#</th><th>Movie</th><th class="num">Pts</th></tr></thead>
{% endif %}
<tbody>
{% for row in d.rows + [none] + d.dark_rows %}
{% if row is none %}
<tr class="divider-row"><td colspan="{% if view.mode == "live" %}6{% else %}3{% endif %}">Dark Horses</td></tr>
{% else %}
<tr>
  <td>{{ row.label }}</td>
  <td>{% if row.missing %}<span class="cell-none">{{ row.title }}</span>{% else %}{{ row.title }}{% endif %}</td>
  {% if view.mode == "live" %}
  <td class="num">{% if row.projected_rank %}#{{ row.projected_rank }}{% else %}<span class="cell-none">—</span>{% endif %}</td>
  <td class="num">
    {%- if row.diff is none %}<span class="cell-none">—</span>
    {%- elif row.diff > 0 %}<span class="up">▲ {{ row.diff }}</span>
    {%- elif row.diff < 0 %}<span class="down">▼ {{ -row.diff }}</span>
    {%- else %}<span class="flat">–</span>{% endif -%}
  </td>
  <td class="num">{% if row.gross %}{{ row.gross | money }}{% else %}<span class="cell-none">—</span>{% endif %}</td>
  {% endif %}
  <td class="num">{{ row.pts }}</td>
</tr>
{% endif %}
{% endfor %}
</tbody>
</table>
</div>
</details>
{% endfor %}

<h2>Films</h2>
<details>
<summary>All tracked films ({{ view.films | length }})</summary>
<div class="table-scroll">
<table>
<thead><tr><th>#</th><th>Movie</th><th>Released</th><th>Status</th>
<th class="num">Projected median (in-window)</th><th class="num">80% range</th>
<th class="num">Cumulative</th><th>Source</th></tr></thead>
<tbody>
{% for f in view.films %}
<tr>
  <td>{% if f.rank %}{{ f.rank }}{% else %}<span class="cell-none">—</span>{% endif %}</td>
  <td>{{ f.title }}</td>
  <td>{{ f.released }}</td>
  <td><span class="badge">{{ f.badge }}</span></td>
  <td class="num">{{ f.median | money }}</td>
  <td class="num">{{ f.p10 | money }} – {{ f.p90 | money }}</td>
  <td class="num">{{ f.cumulative | money }}</td>
  <td class="stats-line">{{ f.source }}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</details>
{% endblock %}
```

- [ ] **Step 6: Add `render_leaderboard` to `smw/render/page.py`**

```python
def render_leaderboard(env: Environment, out_dir: Path, ctx: dict, view) -> None:
    write_page(env, "index.html.j2", out_dir, "index.html",
               {**ctx, "title": "Leaderboard", "wide_shell": True, "view": view})
```

- [ ] **Step 7: Write the render tests** — `tests/test_leaderboard_render.py`:

```python
from datetime import date
from smw.model.simulate import simulate
from smw.render.page import base_context, make_env, render_leaderboard
from smw.render.views import build_leaderboard_view
from smw.score.rules import score_player
from tests.test_views import _catalog  # reuse the deterministic catalog factory

TODAY = date(2026, 8, 15)

def _render(tmp_path, season, group, with_sim=True):
    cat = _catalog()
    sim = simulate(season, group, cat) if with_sim else None
    actual = [f.title for f in sorted(cat.films, key=lambda f: -f.cumulative_gross)
              if f.cumulative_gross > 0][:10]
    current = {u: score_player(group.players[u], actual) for u in group.players}
    view = build_leaderboard_view(season, group, cat, sim, current, actual,
                                  None if with_sim else "only 3 films have projections",
                                  TODAY)
    env = make_env()
    ctx = base_context(season, group, "leaderboard", TODAY)
    render_leaderboard(env, tmp_path, ctx, view)
    return (tmp_path / "index.html").read_text()

def test_hostile_title_escaped(tmp_path, season, group):
    # Titles come from an external HTML document and are untrusted (§11.4).
    from smw.catalog.normalize import Film
    from smw.model.project import MovieCatalog, Projection
    hostile = "</script><script>alert(1)</script> The Movie"
    f = Film(hostile, date(2026, 5, 1), "in_theaters", "wide", 5.0, None)
    p = Projection(hostile, 10.0, 0.2, 5.0, "decay model", 8.0, 12.0)
    cat = MovieCatalog([f], [p], [])
    view = build_leaderboard_view(season, group, cat, None,
                                  {u: 0 for u in group.players}, [hostile],
                                  "reason", TODAY)
    env = make_env()
    ctx = base_context(season, group, "leaderboard", TODAY)
    render_leaderboard(env, tmp_path, ctx, view)
    html = (tmp_path / "index.html").read_text()
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html

def test_current_points_mode_has_no_forecast_numbers(tmp_path, season, group):
    # §13.5 named gap: below the threshold the page contains no win percentage
    # and no projected total.
    html = _render(tmp_path, season, group, with_sim=False)
    assert "Win odds" not in html
    assert "% win" not in html
    assert "Projected pts" not in html
    assert "Current pts" in html
    assert "🏆 Current Standings" in html

def test_live_mode_has_forecast_rows(tmp_path, season, group):
    html = _render(tmp_path, season, group)
    assert "Win odds" in html
    assert "🏆 Projected Standings" in html
    assert "Outside the top 10" in html

def test_no_external_references(tmp_path, season, group):
    html = _render(tmp_path, season, group)
    assert "http://" not in html and "https://" not in html
```

- [ ] **Step 8: The snapshot test and its ritual** — append to `tests/test_leaderboard_render.py`:

```python
def test_leaderboard_snapshot(tmp_path, season, group):
    """Byte-exact snapshot (§13.5). REGENERATION RITUAL: delete
    tests/fixtures/snapshot_index.html, run this test once (it rewrites the fixture
    and fails), OPEN THE FILE IN A BROWSER AND LOOK AT IT, then re-run to lock.
    A snapshot regenerated without human inspection tests nothing."""
    from tests.conftest import FIXTURES
    html = _render(tmp_path, season, group)
    fixture = FIXTURES / "snapshot_index.html"
    if not fixture.exists():
        fixture.write_text(html)
        raise AssertionError(
            "Snapshot fixture created. Open tests/fixtures/snapshot_index.html in a "
            "browser, inspect it, then re-run to lock.")
    assert html == fixture.read_text()
```

Run: `pytest tests/test_leaderboard_render.py -v` — first run FAILS creating the fixture. **Open `tests/fixtures/snapshot_index.html` in a browser and inspect it** (matrix renders, divider after row 10, footer sums, badges, theme toggle). Then re-run: all PASS.

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "feat: leaderboard with live and current-points modes, snapshot test

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 16: What If? sandbox (§12.2)

**Files:**
- Create: `smw/render/templates/whatif.html.j2`, `smw/render/static/scoring.js`, `smw/render/static/whatif.js`, `tests/test_whatif_render.py`
- Modify: `smw/render/page.py` (add `build_whatif_data`, `render_whatif`), `smw/render/static/site.css` (sandbox styles)

**Interfaces:**
- Produces:
  - `build_whatif_data(season, group, catalog, sim) -> dict` — `{"films": [top matrix_rows titles in projected order], "players": [{"name", "ranked", "dark"} in column order (simulated median desc)], "baseline": {username: pts vs projected top ten}}`. Computed server-side; the page only re-scores.
  - `render_whatif(env, out_dir, ctx, data: dict | None, reason: str | None)` — `data=None` renders the locked state (§11.3) with the exact notice text.
  - `smw/render/static/scoring.js` — client-side mirror of §2 scoring: `rankedPickPoints(predicted, actual)`, `scorePlayer(ranked, dark, topTitles)`, `pointsFor(ranked, dark, title, topTitles)`; exports via `module.exports` when under Node so Task 20's cross-implementation vector test can drive it.
- Keyboard parity, touch press-and-hold, polite live region, competition ranking, reset, footnote — all per §12.2.

- [ ] **Step 1: Write the failing render tests** — `tests/test_whatif_render.py`:

```python
from datetime import date
from smw.model.simulate import simulate
from smw.render.page import base_context, build_whatif_data, make_env, render_whatif
from tests.test_views import _catalog

TODAY = date(2026, 8, 15)

def _render(tmp_path, season, group, locked=False):
    env = make_env()
    ctx = base_context(season, group, "whatif", TODAY)
    if locked:
        render_whatif(env, tmp_path, ctx, None, "only 3 films have non-zero projections")
    else:
        cat = _catalog()
        data = build_whatif_data(season, group, cat, simulate(season, group, cat))
        render_whatif(env, tmp_path, ctx, data, None)
    return (tmp_path / "whatif.html").read_text()

def test_locked_state_notice(tmp_path, season, group):
    html = _render(tmp_path, season, group, locked=True)
    assert "unlocks once the forecast is live" in html
    assert "only 3 films" in html
    assert "film-list" not in html  # no sandbox content in locked state

def test_embedded_data_and_scripts(tmp_path, season, group):
    html = _render(tmp_path, season, group)
    assert "window.WHATIF" in html
    assert "rankedPickPoints" in html   # scoring.js inlined
    assert "aria-live" in html          # polite live region
    assert "If it ends this way" in html
    assert "can't be dragged in and score 0" in html

def test_data_shape(season, group):
    cat = _catalog()
    data = build_whatif_data(season, group, cat, simulate(season, group, cat))
    assert len(data["films"]) == season.matrix_rows
    assert data["films"][0] == "M01"
    names = [p["name"] for p in data["players"]]
    assert set(names) == set(group.players)
    assert all(len(p["ranked"]) == 10 and len(p["dark"]) == 3 for p in data["players"])
    assert set(data["baseline"]) == set(group.players)

def test_no_external_references(tmp_path, season, group):
    html = _render(tmp_path, season, group)
    assert "http://" not in html and "https://" not in html
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_whatif_render.py -v` — Expected: FAIL with import error.

- [ ] **Step 3: Write `smw/render/static/scoring.js`** (mirrors §2 exactly; kept tiny and dependency-free so both the page and Node can run it)

```javascript
"use strict";
function rankedPickPoints(predicted, actual) {
  if (actual === null || actual === undefined) return 0;
  var d = Math.abs(predicted - actual);
  if (d === 0) return (actual === 1 || actual === 10) ? 13 : 10;
  if (d === 1) return 7;
  if (d === 2) return 5;
  return 3;
}
function positionMap(topTitles) {
  var pos = {};
  for (var i = 0; i < topTitles.length; i++) pos[topTitles[i]] = i + 1;
  return pos;
}
function pointsFor(ranked, dark, title, topTitles) {
  var pos = positionMap(topTitles)[title];
  var ri = ranked.indexOf(title);
  if (ri >= 0) return pos ? rankedPickPoints(ri + 1, pos) : 0;
  if (dark.indexOf(title) >= 0) return pos ? 1 : 0;
  return null; // not picked
}
function scorePlayer(ranked, dark, topTitles) {
  var pos = positionMap(topTitles), total = 0;
  for (var i = 0; i < ranked.length; i++)
    if (pos[ranked[i]]) total += rankedPickPoints(i + 1, pos[ranked[i]]);
  for (var j = 0; j < dark.length; j++)
    if (pos[dark[j]]) total += 1;
  return total;
}
if (typeof module !== "undefined") {
  module.exports = { rankedPickPoints: rankedPickPoints, scorePlayer: scorePlayer };
}
```

- [ ] **Step 4: Write `smw/render/static/whatif.js`**

```javascript
"use strict";
(function () {
  var D = window.WHATIF;
  var list = document.getElementById("film-list");
  var order = D.films.slice();

  function top10() { return order.slice(0, 10); }

  function rebuild() {
    list.innerHTML = "";
    order.forEach(function (title, idx) {
      var li = document.createElement("li");
      li.draggable = true;
      li.dataset.title = title;
      var name = document.createElement("span");
      name.className = "wi-title";
      name.textContent = title;
      li.appendChild(name);
      [["▲", -1], ["▼", 1]].forEach(function (pair) {
        var b = document.createElement("button");
        b.type = "button";
        b.textContent = pair[0];
        b.setAttribute("aria-label",
          "Move " + title + (pair[1] < 0 ? " up" : " down") + " one slot");
        b.addEventListener("click", function () {
          var j = order.indexOf(title), k = j + pair[1];
          if (k < 0 || k >= order.length) return;
          order.splice(j, 1); order.splice(k, 0, title);
          rebuild(); rescore();
          // return focus so repeated presses keep walking the film (§12.2)
          var again = list.children[k].querySelectorAll("button")[pair[1] < 0 ? 0 : 1];
          again.focus();
        });
        li.appendChild(b);
      });
      li.addEventListener("dragstart", function (e) {
        e.dataTransfer.setData("text/plain", title);
        li.classList.add("dragging");
      });
      li.addEventListener("dragend", function () { li.classList.remove("dragging"); });
      li.addEventListener("dragover", function (e) { e.preventDefault(); });
      li.addEventListener("drop", function (e) {
        e.preventDefault();
        var dragged = e.dataTransfer.getData("text/plain");
        if (!dragged || dragged === title) return;
        var from = order.indexOf(dragged), to = order.indexOf(title);
        order.splice(from, 1); order.splice(to, 0, dragged);
        rebuild(); rescore();
      });
      // touch: press-and-hold before a drag begins so page scrolling still works
      var holdTimer = null, touchDragging = false;
      li.addEventListener("touchstart", function () {
        holdTimer = setTimeout(function () { touchDragging = true;
          li.classList.add("dragging"); }, 350);
      }, { passive: true });
      li.addEventListener("touchmove", function (e) {
        if (!touchDragging) { clearTimeout(holdTimer); return; }
        e.preventDefault();
        var y = e.touches[0].clientY;
        var target = document.elementFromPoint(e.touches[0].clientX, y);
        var over = target && target.closest("#film-list li");
        if (over && over !== li) {
          var from = order.indexOf(title), to = order.indexOf(over.dataset.title);
          order.splice(from, 1); order.splice(to, 0, title);
          rebuild(); rescore();
        }
      }, { passive: false });
      li.addEventListener("touchend", function () {
        clearTimeout(holdTimer); touchDragging = false;
        li.classList.remove("dragging");
      });
      list.appendChild(li);
    });
  }

  function rescore() {
    var finish = top10();
    var rowsData = D.players.map(function (p) {
      return { name: p.name, pts: scorePlayer(p.ranked, p.dark, finish),
               base: D.baseline[p.name] };
    });
    rowsData.sort(function (a, b) { return b.pts - a.pts || (a.name < b.name ? -1 : 1); });
    var tbody = document.getElementById("standings-body");
    tbody.innerHTML = "";
    var place = 0, shown = 0, prev = null;
    rowsData.forEach(function (r) {
      shown += 1;
      if (r.pts !== prev) { place = shown; prev = r.pts; }  // competition ranking 1,1,3
      var tr = document.createElement("tr");
      var delta = r.pts - r.base;
      var deltaTxt = delta > 0 ? "▲" + delta : delta < 0 ? "▼" + (-delta) : "–";
      [place, (place === 1 ? "👑 " : "") + r.name, r.pts, deltaTxt].forEach(function (v) {
        var td = document.createElement("td");
        td.textContent = v;
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    var grid = document.getElementById("points-grid-body");
    grid.innerHTML = "";
    order.forEach(function (title, i) {
      var tr = document.createElement("tr");
      var td0 = document.createElement("td"); td0.textContent = (i + 1) + ". " + title;
      tr.appendChild(td0);
      rowsData.forEach(function (r) {
        var p = D.players.filter(function (x) { return x.name === r.name; })[0];
        var pts = pointsFor(p.ranked, p.dark, title, finish);
        var td = document.createElement("td");
        td.className = "num " + (pts === null ? "cell-none" : pts > 0 ? "cell-pos" : "cell-zero");
        td.textContent = pts === null ? "—" : String(pts);
        tr.appendChild(td);
      });
      grid.appendChild(tr);
    });
    var head = document.getElementById("points-grid-head");
    head.innerHTML = "<th>Film</th>" + rowsData.map(function (r) {
      return "<th class=\"num\"></th>"; }).join("");
    var ths = head.querySelectorAll("th.num");
    rowsData.forEach(function (r, i) { ths[i].textContent = r.name; });
  }

  document.getElementById("reset-order").addEventListener("click", function () {
    order = D.films.slice();
    rebuild(); rescore();
  });
  rebuild(); rescore();
})();
```

- [ ] **Step 5: Write `smw/render/templates/whatif.html.j2`**

```jinja
{% extends "base.html.j2" %}
{% block content %}
{% if data is none %}
<div class="locked">Not enough films have projections yet to simulate win
probabilities — {{ reason }}. This view unlocks once the forecast is live.</div>
{% else %}
<h2>🎬 What If?</h2>
<p class="stats-line">Drag films into any finish order — or use the ▲ ▼ buttons —
and watch every score recompute.</p>
<div class="two-col">
  <div>
    <ol id="film-list"></ol>
    <button type="button" id="reset-order">Reset to projected order</button>
    <p class="stats-line">Films outside the projected top {{ data.films | length }}
    can't be dragged in and score 0.</p>
  </div>
  <div class="standings" aria-live="polite">
    <h3>If it ends this way…</h3>
    <table>
      <thead><tr><th>#</th><th>Player</th><th class="num">Pts</th><th class="num">Δ</th></tr></thead>
      <tbody id="standings-body"></tbody>
    </table>
  </div>
</div>
<h3>Points by film</h3>
<div class="table-scroll">
<table>
  <thead><tr id="points-grid-head"></tr></thead>
  <tbody id="points-grid-body"></tbody>
</table>
</div>
<script>window.WHATIF = {{ data | json_embed }};</script>
<script>{{ scoring_js }}</script>
<script>{{ whatif_js }}</script>
{% endif %}
{% endblock %}
```

- [ ] **Step 6: Add to `smw/render/page.py`**

```python
from smw.model.project import MovieCatalog
from smw.model.simulate import SimResult
from smw.render.views import projected_ranks
from smw.score.rules import score_player


def build_whatif_data(season: Season, group: Group,
                      catalog: MovieCatalog, sim: SimResult) -> dict:
    ranks = projected_ranks(catalog)
    films = [t for t, _ in sorted(ranks.items(), key=lambda kv: kv[1])
             ][: season.matrix_rows]
    order = sorted(group.players, key=lambda u: (-sim.median_pts[u], u))
    top10 = films[:10]
    return {
        "films": films,
        "players": [
            {"name": u,
             "ranked": list(group.players[u].ranked),
             "dark": list(group.players[u].dark_horses)}
            for u in order
        ],
        "baseline": {u: score_player(group.players[u], top10) for u in order},
    }


def render_whatif(env: Environment, out_dir: Path, ctx: dict,
                  data: dict | None, reason: str | None) -> None:
    write_page(env, "whatif.html.j2", out_dir, "whatif.html", {
        **ctx, "title": "What If?", "data": data, "reason": reason,
        "scoring_js": Markup((STATIC / "scoring.js").read_text()),
        "whatif_js": Markup((STATIC / "whatif.js").read_text()),
    })
```

- [ ] **Step 7: Append sandbox styles to `smw/render/static/site.css`**

```css
/* What If? sandbox */
.two-col { display: grid; grid-template-columns: 1fr 300px; gap: 1.5rem; align-items: start; }
.standings { position: sticky; top: 1rem; background: var(--card);
  border: 1px solid var(--border); border-radius: 8px; padding: 0.8rem; }
#film-list { list-style: none; counter-reset: slot; padding: 0; margin: 0; }
#film-list li { counter-increment: slot; display: flex; align-items: center; gap: 0.4rem;
  background: var(--card); border: 1px solid var(--border); border-radius: 6px;
  padding: 0.35rem 0.6rem; margin-bottom: 0.3rem; cursor: grab; }
#film-list li::before { content: counter(slot); color: var(--muted); width: 1.5rem;
  font-variant-numeric: tabular-nums; }
#film-list .wi-title { flex: 1; }
#film-list li button { background: var(--dim); color: var(--ink);
  border: 1px solid var(--border); border-radius: 4px; cursor: pointer; }
/* pure-CSS top-10 cutoff (§12.2): dashed border + generated label, 11+ dimmed */
#film-list li:nth-child(10) { border-bottom: 3px dashed var(--muted); }
#film-list li:nth-child(10)::after { content: "top 10 cutoff"; color: var(--muted);
  font-size: 0.7rem; }
#film-list li:nth-child(n+11) { opacity: 0.55; }
#film-list li.dragging { opacity: 0.4; }
```

- [ ] **Step 8: Run to verify pass**

Run: `pytest tests/test_whatif_render.py -v` — Expected: 4 PASS.
Then run the full suite: `pytest -v`. **The leaderboard snapshot now fails** because `site.css` changed — expected. Re-lock via the ritual: delete `tests/fixtures/snapshot_index.html`, run once, open the regenerated file in a browser and inspect, re-run to lock.

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "feat: What If? sandbox with drag, keyboard, and touch reorder

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 17: Winning Scenarios page (§12.3)

**Files:**
- Create: `smw/render/templates/scenarios.html.j2`, `smw/render/static/scenarios.js`, `tests/test_scenarios_render.py`
- Modify: `smw/render/page.py` (add `build_scenarios_view`, `render_scenarios`), `smw/render/static/site.css` (tab styles)

**Interfaces:**
- Produces:
  - `build_scenarios_view(group: Group, sim: SimResult) -> list[dict]` — one entry per player ordered by win probability descending (tie → username): `{"username", "win_pct", "scenario": None | {"caption", "columns": [usernames re-sorted by that scenario's totals desc, winner leftmost], "rows": [{"title", "cells": [int per column]}], "totals": [int per column]}}`.
  - `render_scenarios(env, out_dir, ctx, tabs: list[dict] | None, reason: str | None)` — `tabs=None` renders the locked state with the same notice text as What If? (§11.3).
- The template renders every panel server-side; `scenarios.js` only switches visibility and `aria-pressed`. Zero cells render a muted middle dot `·` (§12.3). A player with no path gets a genuinely `disabled` button showing `0%` with a `title` tooltip explaining itself.

- [ ] **Step 1: Write the failing tests** — `tests/test_scenarios_render.py`:

```python
from datetime import date
import pytest
from smw.config.groups import Group, PlayerPicks
from smw.model.simulate import simulate
from smw.render.page import base_context, build_scenarios_view, make_env, render_scenarios
from tests.test_views import _catalog

TODAY = date(2026, 8, 15)

@pytest.fixture
def sim(season, group):
    return simulate(season, group, _catalog())

def test_tabs_ordered_by_win_prob(group, sim):
    tabs = build_scenarios_view(group, sim)
    probs = [sim.win_prob[t["username"]] for t in tabs]
    assert probs == sorted(probs, reverse=True)

def test_winner_column_leftmost(group, sim):
    tabs = build_scenarios_view(group, sim)
    top = tabs[0]
    assert top["scenario"] is not None
    cols = top["scenario"]["columns"]
    totals = top["scenario"]["totals"]
    assert cols[0] == top["username"]          # winner sits leftmost
    assert totals == sorted(totals, reverse=True)

def test_grid_is_ten_rows_and_consistent(group, sim):
    s = build_scenarios_view(group, sim)[0]["scenario"]
    assert len(s["rows"]) == 10
    for ci in range(len(s["columns"])):
        assert sum(r["cells"][ci] for r in s["rows"]) == s["totals"][ci]

def test_no_path_player_disabled(season, group):
    players = dict(group.players)
    players["dave"] = PlayerPicks("dave", tuple(f"Z{i}" for i in range(10)),
                                  ("Z10", "Z11", "Z12"))
    hopeless = Group(group.group_id, group.display_name, players)
    sim = simulate(season, hopeless, _catalog())
    tabs = build_scenarios_view(hopeless, sim)
    dave = next(t for t in tabs if t["username"] == "dave")
    assert dave["scenario"] is None

def _render(tmp_path, season, group, tabs, reason=None):
    env = make_env()
    ctx = base_context(season, group, "scenarios", TODAY)
    render_scenarios(env, tmp_path, ctx, tabs, reason)
    return (tmp_path / "scenarios.html").read_text()

def test_rendered_page(tmp_path, season, group, sim):
    html = _render(tmp_path, season, group, build_scenarios_view(group, sim))
    assert "aria-pressed" in html
    assert "crowns them champion" in html
    assert "http://" not in html and "https://" not in html

def test_zero_cells_render_middle_dot_and_no_path_disabled(tmp_path, season, group):
    tabs = [
        {"username": "alice", "win_pct": 50.0, "scenario": {
            "caption": "cap", "columns": ["alice", "bob", "carol"],
            "rows": [{"title": f"T{i}", "cells": [10, 0, 3]} for i in range(10)],
            "totals": [100, 0, 30]}},
        {"username": "bob", "win_pct": 0.0, "scenario": None},
    ]
    html = _render(tmp_path, season, group, tabs)
    assert "·" in html          # zero cells as middle dot
    assert "disabled" in html   # genuinely disabled no-path button

def test_locked_state(tmp_path, season, group):
    html = _render(tmp_path, season, group, None, "only 3 films have projections")
    assert "unlocks once the forecast is live" in html
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_scenarios_render.py -v` — Expected: FAIL with import error.

- [ ] **Step 3: Add to `smw/render/page.py`**

```python
def build_scenarios_view(group: Group, sim: SimResult) -> list[dict]:
    tabs = []
    order = sorted(group.players, key=lambda u: (-sim.win_prob[u], u))
    for u in order:
        sc = sim.scenarios[u]
        entry = {"username": u, "win_pct": round(sim.win_prob[u] * 100, 1),
                 "scenario": None}
        if sc is not None:
            cols = sorted(sc.totals, key=lambda v: (-sc.totals[v], v))
            entry["scenario"] = {
                "caption": (
                    f"Most likely finish in which {u} wins the wager 🏆 — {u} edges "
                    f"the field by just {sc.margin} pt"
                    f"{'s' if sc.margin != 1 else ''}; they win ~{entry['win_pct']}% "
                    "of all sims."),
                "columns": cols,
                "rows": [{"title": t, "cells": [sc.grid[v][i] for v in cols]}
                         for i, t in enumerate(sc.films)],
                "totals": [sc.totals[v] for v in cols],
            }
        tabs.append(entry)
    return tabs


def render_scenarios(env: Environment, out_dir: Path, ctx: dict,
                     tabs: "list[dict] | None", reason: str | None) -> None:
    write_page(env, "scenarios.html.j2", out_dir, "scenarios.html", {
        **ctx, "title": "Winning Scenarios", "tabs": tabs, "reason": reason,
        "scenarios_js": Markup((STATIC / "scenarios.js").read_text()),
    })
```

- [ ] **Step 4: Write `smw/render/templates/scenarios.html.j2`**

```jinja
{% extends "base.html.j2" %}
{% block content %}
{% if tabs is none %}
<div class="locked">Not enough films have projections yet to simulate win
probabilities — {{ reason }}. This view unlocks once the forecast is live.</div>
{% else %}
<h2>🔮 Winning Scenarios</h2>
<p class="stats-line">Pick a player to see the single most-likely top-10 box-office
finish order that crowns them champion — and exactly how everyone's predictions score
against it. Grayed-out players have no realistic path to winning.</p>
<div class="tab-row" role="tablist">
{% for t in tabs %}
  {% if t.scenario %}
  <button type="button" class="tab" data-tab="{{ loop.index0 }}"
    aria-pressed="{{ 'true' if loop.first else 'false' }}">
    {{ t.username }} <span class="stats-line">{{ t.win_pct }}%</span></button>
  {% else %}
  <button type="button" class="tab" disabled
    title="{{ t.username }} wins in none of the simulated seasons">
    {{ t.username }} <span class="stats-line">0%</span></button>
  {% endif %}
{% endfor %}
</div>
{% for t in tabs %}{% if t.scenario %}
<section class="scenario-panel" data-panel="{{ loop.index0 }}"
  {% if not loop.first %}hidden{% endif %}>
<p>{{ t.scenario.caption }}</p>
<div class="table-scroll">
<table>
<thead><tr><th>#</th><th>Film</th>
{% for u in t.scenario.columns %}
<th class="num {% if u == t.username %}highlight-col{% endif %}">{{ u }}</th>
{% endfor %}</tr></thead>
<tbody>
{% for row in t.scenario.rows %}
<tr><td>{{ loop.index }}</td><td>{{ row.title }}</td>
{% for c in row.cells %}
<td class="num {% if t.scenario.columns[loop.index0] == t.username %}highlight-col{% endif %}">
  {%- if c > 0 %}<span class="cell-pos">{{ c }}</span>{% else %}<span class="cell-none">·</span>{% endif -%}
</td>
{% endfor %}</tr>
{% endfor %}
</tbody>
<tfoot><tr><td colspan="2">Total</td>
{% for total in t.scenario.totals %}
<td class="num"><strong>{% if loop.first %}👑 {% endif %}{{ total }}</strong></td>
{% endfor %}</tr></tfoot>
</table>
</div>
</section>
{% endif %}{% endfor %}
<script>{{ scenarios_js }}</script>
{% endif %}
{% endblock %}
```

- [ ] **Step 5: Write `smw/render/static/scenarios.js`**

```javascript
"use strict";
(function () {
  var buttons = document.querySelectorAll(".tab[data-tab]");
  buttons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      buttons.forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
      btn.setAttribute("aria-pressed", "true");
      document.querySelectorAll(".scenario-panel").forEach(function (p) {
        p.hidden = p.dataset.panel !== btn.dataset.tab;
      });
    });
  });
})();
```

- [ ] **Step 6: Append tab styles to `smw/render/static/site.css`**

```css
/* Winning Scenarios tabs */
.tab-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.8rem 0; }
.tab { padding: 0.35rem 0.8rem; border-radius: 999px; background: var(--card);
  color: var(--ink); border: 1px solid var(--border); cursor: pointer; }
.tab[aria-pressed="true"] { background: var(--accent); color: #fff; border-color: var(--accent); }
.tab:disabled { opacity: 0.45; cursor: not-allowed; }
th.highlight-col, td.highlight-col { background: var(--dim); }
```

- [ ] **Step 7: Run to verify pass, re-lock snapshot, commit**

Run: `pytest tests/test_scenarios_render.py -v` — Expected: 8 PASS. Full suite: the CSS change invalidates the leaderboard snapshot again — re-lock via the ritual (delete fixture, regenerate, inspect in browser, re-run).

```bash
git add -A && git commit -m "feat: winning scenarios page with per-player tabs

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 18: Odds Over Time — hand-rolled SVG chart (§12.4)

**Files:**
- Create: `smw/render/chart.py`, `smw/render/templates/history.html.j2`, `smw/render/static/history.js`, `tests/test_chart.py`
- Modify: `smw/render/page.py` (add `render_history`), `smw/render/static/site.css` (palette + chart styles)

**Interfaces:**
- Produces (in `smw.render.chart`):
  - `build_history_data(rows: list[dict]) -> dict | None` — `rows` are parsed `forecast_history.jsonl` lines in file order. Returns `None` when empty; else `{"dates": [iso strings, sorted unique], "series": [{"name", "color": int 0–7, "values": [float | None per date]}]}` with series **sorted by username** so color binding is alphabetical and stable (§12.4); where two runs share a date the later line supersedes.
  - `render_chart_svg(data) -> str` — the full inline `<svg>`: y axis zero to the next decile above the max, gridlines every 10% labeled as percentages; x labels thinned to ≤8 always including the most recent; one path per series with round joins/caps and a marker per observation; **a `None` breaks the path** (a new `M` subpath after the gap — never interpolated); direct labels for the top four by latest value, nudged ≥14px apart, text in body ink with a colored swatch; colors via CSS classes `series-0`…`series-7` only.
- `render_history(env, out_dir, ctx, data: dict | None)` in `page.py` — `data=None` renders the locked state *"No forecast history yet — this chart fills in after the first production refresh."* This page gates on **its own data**, never on `forecast_available` (§11.3 asymmetry — deliberate: history is real information even when today's forecast is degraded).
- Page carries a legend (every player by latest odds), a table fallback in a collapsed `<details>` (dates × players, middle dot for gaps), and a pointer crosshair tooltip fed by embedded JSON.

- [ ] **Step 1: Write the failing tests** — `tests/test_chart.py`:

```python
from smw.render.chart import build_history_data, render_chart_svg

ROWS = [
    {"date": "2026-06-01", "player": "bob", "win_prob": 0.30},
    {"date": "2026-06-01", "player": "alice", "win_prob": 0.55},
    {"date": "2026-06-08", "player": "alice", "win_prob": 0.60},
    {"date": "2026-06-08", "player": "bob", "win_prob": 0.25},
    # alice missing on 06-15 → gap in her line
    {"date": "2026-06-15", "player": "bob", "win_prob": 0.20},
    {"date": "2026-06-22", "player": "alice", "win_prob": 0.70},
    {"date": "2026-06-22", "player": "bob", "win_prob": 0.15},
    # same-date duplicate: later line supersedes
    {"date": "2026-06-22", "player": "bob", "win_prob": 0.18},
]

def test_empty_rows_is_none():
    assert build_history_data([]) is None

def test_series_sorted_by_username_with_stable_colors():
    d = build_history_data(ROWS)
    assert [s["name"] for s in d["series"]] == ["alice", "bob"]
    assert [s["color"] for s in d["series"]] == [0, 1]

def test_missing_value_is_null_not_interpolated():
    d = build_history_data(ROWS)
    alice = d["series"][0]
    assert alice["values"] == [0.55, 0.60, None, 0.70]

def test_later_run_supersedes_same_date():
    d = build_history_data(ROWS)
    bob = d["series"][1]
    assert bob["values"][-1] == 0.18

def test_gap_breaks_svg_path():
    svg = render_chart_svg(build_history_data(ROWS))
    # alice's path must contain two M (move) commands: one start, one after the gap
    import re
    alice_path = re.search(r'<path class="line series-0" d="([^"]+)"', svg).group(1)
    assert alice_path.count("M") == 2

def test_y_axis_next_decile_above_max():
    svg = render_chart_svg(build_history_data(ROWS))
    assert ">80%<" in svg      # max 0.70 → axis tops at 0.8
    assert ">90%<" not in svg

def test_x_labels_thinned_to_eight_max_including_latest():
    rows = [{"date": f"2026-06-{d:02d}", "player": "a", "win_prob": 0.5}
            for d in range(1, 29)]
    svg = render_chart_svg(build_history_data(rows))
    labels = svg.count('class="x-label"')
    assert labels <= 8
    assert "2026-06-28" in svg
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_chart.py -v` — Expected: FAIL with import error.

- [ ] **Step 3: Implement `smw/render/chart.py`**

```python
"""Hand-rolled SVG line chart for win odds over time (spec §12.4). A few hundred
lines of path arithmetic beats a charting library that would be the page's largest
dependency by an order of magnitude."""
import math

W, H = 660, 300
ML, MR, MT, MB = 48, 118, 12, 30  # right margin leaves room for direct labels
MAX_X_LABELS = 8
DIRECT_LABELS = 4
LABEL_MIN_GAP = 14


def build_history_data(rows: list[dict]) -> "dict | None":
    if not rows:
        return None
    dates = sorted({r["date"] for r in rows})
    players = sorted({r["player"] for r in rows})
    values: dict[tuple[str, str], float] = {}
    for r in rows:  # file order: later run supersedes a shared date
        values[(r["date"], r["player"])] = r["win_prob"]
    return {
        "dates": dates,
        "series": [
            {"name": p, "color": i % 8,
             "values": [values.get((d, p)) for d in dates]}
            for i, p in enumerate(players)
        ],
    }


def _x(i: int, n: int) -> float:
    if n == 1:
        return ML + (W - ML - MR) / 2
    return ML + i * (W - ML - MR) / (n - 1)


def _y(v: float, ymax: float) -> float:
    return MT + (1 - v / ymax) * (H - MT - MB)


def render_chart_svg(data: dict) -> str:
    dates, series = data["dates"], data["series"]
    n = len(dates)
    vmax = max((v for s in series for v in s["values"] if v is not None), default=0.0)
    ymax = max(0.1, math.floor(vmax * 10 + 1) / 10)  # next decile above the max
    ymax = min(ymax, 1.0)

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" class="odds-chart" '
             'aria-label="Each player\'s win probability at every refresh">']
    # gridlines every 10%
    tick = 0.0
    while tick <= ymax + 1e-9:
        y = _y(tick, ymax)
        parts.append(f'<line class="grid" x1="{ML}" y1="{y:.1f}" '
                     f'x2="{W - MR}" y2="{y:.1f}"/>')
        parts.append(f'<text class="y-label" x="{ML - 6}" y="{y + 4:.1f}" '
                     f'text-anchor="end">{round(tick * 100)}%</text>')
        tick += 0.1
    # x labels, thinned, always including the most recent
    step = max(1, math.ceil(n / MAX_X_LABELS))
    idxs = sorted(set(range(0, n, step)) | {n - 1})[-MAX_X_LABELS:]
    for i in idxs:
        parts.append(f'<text class="x-label" x="{_x(i, n):.1f}" y="{H - 8}" '
                     f'text-anchor="middle">{dates[i]}</text>')
    # one path per series; a None breaks the line (§12.4 — a gap means no forecast
    # was produced; drawing through it would assert a number never computed)
    for s in series:
        d_cmds, pen_down = [], False
        for i, v in enumerate(s["values"]):
            if v is None:
                pen_down = False
                continue
            cmd = "L" if pen_down else "M"
            d_cmds.append(f"{cmd}{_x(i, n):.1f} {_y(v, ymax):.1f}")
            pen_down = True
        parts.append(f'<path class="line series-{s["color"]}" d="{" ".join(d_cmds)}"/>')
        for i, v in enumerate(s["values"]):
            if v is not None:
                parts.append(f'<circle class="marker series-{s["color"]}" '
                             f'cx="{_x(i, n):.1f}" cy="{_y(v, ymax):.1f}" r="2.5"/>')
    # direct labels: top four by latest value, nudged apart
    latest = []
    for s in series:
        vals = [v for v in s["values"] if v is not None]
        if vals:
            last_i = max(i for i, v in enumerate(s["values"]) if v is not None)
            latest.append((s, s["values"][last_i], last_i))
    latest.sort(key=lambda t: -t[1])
    placed = []
    for s, v, last_i in latest[:DIRECT_LABELS]:
        y = _y(v, ymax)
        while any(abs(y - py) < LABEL_MIN_GAP for py in placed):
            y += LABEL_MIN_GAP
        placed.append(y)
        x = W - MR + 8
        parts.append(f'<rect class="swatch series-{s["color"]}" x="{x}" '
                     f'y="{y - 8:.1f}" width="8" height="8"/>')
        parts.append(f'<text class="direct-label" x="{x + 12}" y="{y:.1f}">'
                     f'{s["name"]} {round(v * 100)}%</text>')
    parts.append("</svg>")
    return "".join(parts)
```

- [ ] **Step 4: Write `smw/render/templates/history.html.j2`**

```jinja
{% extends "base.html.j2" %}
{% block content %}
{% if data is none %}
<div class="locked">No forecast history yet — this chart fills in after the first
production refresh.</div>
{% else %}
<h2>📈 Odds Over Time</h2>
<div class="chart-wrap">{{ svg }}</div>
<div id="crosshair-tip" class="notice" hidden></div>
<h3>Legend</h3>
<ul class="legend">
{% for s in legend %}
<li><span class="legend-swatch series-{{ s.color }}"></span>
  {{ s.name }} — {{ s.latest_pct }}%</li>
{% endfor %}
</ul>
<details>
<summary>Data table</summary>
<div class="table-scroll">
<table>
<thead><tr><th>Date</th>
{% for s in data.series %}<th class="num">{{ s.name }}</th>{% endfor %}</tr></thead>
<tbody>
{% for row in table_rows %}
<tr><td>{{ row.date }}</td>
{% for cell in row.cells %}
<td class="num">{% if cell is none %}<span class="cell-none">·</span>{% else %}{{ cell }}%{% endif %}</td>
{% endfor %}
</tr>
{% endfor %}
</tbody>
</table>
</div>
</details>
<script>window.HISTORY = {{ data | json_embed }};</script>
<script>{{ history_js }}</script>
{% endif %}
{% endblock %}
```

The table body iterates a prebuilt `table_rows` (dates × players, `None` for gaps)
rather than indexing nested lists in Jinja — the render layer receives finished data
(§11.4). `render_history` in Step 5 builds it.

- [ ] **Step 5: Add `render_history` to `smw/render/page.py`**

```python
from smw.render.chart import render_chart_svg


def render_history(env: Environment, out_dir: Path, ctx: dict,
                   data: "dict | None") -> None:
    extra: dict = {"title": "Odds Over Time", "data": data}
    if data is not None:
        legend = []
        for s in data["series"]:
            vals = [v for v in s["values"] if v is not None]
            legend.append({"name": s["name"], "color": s["color"],
                           "latest_pct": round(vals[-1] * 100, 1) if vals else 0.0})
        legend.sort(key=lambda e: -e["latest_pct"])
        table_rows = [
            {"date": d,
             "cells": [
                 (round(s["values"][i] * 100, 1) if s["values"][i] is not None else None)
                 for s in data["series"]]}
            for i, d in enumerate(data["dates"])
        ]
        extra.update({
            "svg": Markup(render_chart_svg(data)),
            "legend": legend,
            "table_rows": table_rows,
            "history_js": Markup((STATIC / "history.js").read_text()),
        })
    write_page(env, "history.html.j2", out_dir, "history.html", {**ctx, **extra})
```

- [ ] **Step 6: Write `smw/render/static/history.js`** (crosshair tooltip — pointer-only, known gap; the table is the accessible path)

```javascript
"use strict";
(function () {
  var D = window.HISTORY;
  var svg = document.querySelector(".odds-chart");
  var tip = document.getElementById("crosshair-tip");
  if (!svg || !tip) return;
  var ML = 48, MR = 118;
  svg.addEventListener("mousemove", function (e) {
    var rect = svg.getBoundingClientRect();
    var frac = (e.clientX - rect.left) / rect.width;   // viewBox is 0..660
    var px = frac * 660;
    var n = D.dates.length;
    var span = 660 - ML - MR;
    var i = Math.round((px - ML) / (n > 1 ? span / (n - 1) : span));
    i = Math.max(0, Math.min(n - 1, i));
    var lines = [D.dates[i]];
    D.series.forEach(function (s) {
      var v = s.values[i];
      lines.push(s.name + ": " + (v === null ? "·" : Math.round(v * 1000) / 10 + "%"));
    });
    tip.hidden = false;
    tip.textContent = lines.join("  ");
  });
  svg.addEventListener("mouseleave", function () { tip.hidden = true; });
})();
```

- [ ] **Step 7: Append palette + chart styles to `smw/render/static/site.css`** (eight hues, separate light/dark values, contrast-checked against both backgrounds; §12.4)

```css
/* Series palette: bound to players ALPHABETICALLY, never by rank (§12.4). */
.series-0 { --series: #2563eb; } .series-1 { --series: #c2410c; }
.series-2 { --series: #15803d; } .series-3 { --series: #7c3aed; }
.series-4 { --series: #b91c1c; } .series-5 { --series: #0e7490; }
.series-6 { --series: #a16207; } .series-7 { --series: #be185d; }
[data-theme="dark"] .series-0 { --series: #7aa2ff; }
[data-theme="dark"] .series-1 { --series: #fb923c; }
[data-theme="dark"] .series-2 { --series: #4ade80; }
[data-theme="dark"] .series-3 { --series: #a78bfa; }
[data-theme="dark"] .series-4 { --series: #f87171; }
[data-theme="dark"] .series-5 { --series: #22d3ee; }
[data-theme="dark"] .series-6 { --series: #facc15; }
[data-theme="dark"] .series-7 { --series: #f472b6; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .series-0 { --series: #7aa2ff; }
  :root:not([data-theme="light"]) .series-1 { --series: #fb923c; }
  :root:not([data-theme="light"]) .series-2 { --series: #4ade80; }
  :root:not([data-theme="light"]) .series-3 { --series: #a78bfa; }
  :root:not([data-theme="light"]) .series-4 { --series: #f87171; }
  :root:not([data-theme="light"]) .series-5 { --series: #22d3ee; }
  :root:not([data-theme="light"]) .series-6 { --series: #facc15; }
  :root:not([data-theme="light"]) .series-7 { --series: #f472b6; }
}
.chart-wrap { overflow-x: auto; }
.odds-chart { width: 100%; height: auto; }
.odds-chart .grid { stroke: var(--border); stroke-width: 1; }
.odds-chart .y-label, .odds-chart .x-label { fill: var(--muted); font-size: 10px; }
.odds-chart .line { fill: none; stroke: var(--series); stroke-width: 2;
  stroke-linejoin: round; stroke-linecap: round; }
.odds-chart .marker { fill: var(--series); }
.odds-chart .swatch { fill: var(--series); }
.odds-chart .direct-label { fill: var(--ink); font-size: 11px; }
.legend { list-style: none; padding: 0; }
.legend-swatch { display: inline-block; width: 10px; height: 10px;
  background: var(--series); margin-right: 0.4rem; border-radius: 2px; }
```

- [ ] **Step 8: Run to verify pass, re-lock snapshot, commit**

Run: `pytest tests/test_chart.py -v` — Expected: 7 PASS. Full suite: re-lock the leaderboard snapshot one more time via the ritual (browser inspection). This is the last CSS change; T19+ do not touch static assets.

```bash
git add -A && git commit -m "feat: odds-over-time SVG chart with stable palette and table fallback

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 19: Pipeline glue — `build.py`, `data.json`, history writers, season states, CLI (§5.5–5.7, §6.4, §9.5, §10.1, §13.4)

**Files:**
- Create: `smw/render/build.py`, `smw/__main__.py`, `tests/test_build.py`

**Interfaces:**
- Consumes: everything above.
- Produces (in `smw.render.build`):
  - `run_build(data_dir: Path, out_dir: Path, today: date, local: bool) -> None` — the only place that knows the order of operations. `local=True` runs the full pipeline and writes the site but appends to **neither** history file (§13.4).
  - `fetch = fetch_chart` module attribute — the network call goes through this seam so tests monkeypatch it; no other function performs I/O to the network.
  - `build_data_json(season, group, catalog, sim, current_points, non_zero, reason, today) -> dict` — the §5.7 shape exactly.
  - `append_box_office_history(path, grosses: dict[str, float], today)` — one line per film with `gross > 0` (a picked film with no gross is never written), sorted by title for determinism.
  - `append_forecast_history(path, sim: SimResult, today)` — one line per player; called only when a forecast exists (a degraded run appends nothing → the chart gap, §5.6).
- `smw/__main__.py`: `python -m smw --date YYYY-MM-DD --data data --out out [--local]`. `--date` defaults to the real today; every other date in the system flows from this argument.

**Order of operations inside `run_build`:**
1. Load season, groups (all of `data_dir/groups/*.yaml`, sorted), overrides, preopening, history (missing history file → print a warning, not an error — §10.2).
2. If `(today − 1 day) <= window_end`: fetch + parse the chart, apply chart aliases (§6.5 point 1), compute the floor over all parsed rows, window-filter (Guards A/B). Otherwise the chart is frozen (§6.1): skip the fetch entirely; empty row list, floor 0.
3. `resolve_grosses` (Guard C inside).
4. `build_films` with all groups; `build_catalog` with the union of every group's picked titles (canonicalized). Print every catalog warning.
5. Actual top ten: titles with `gross > 0` sorted by gross descending (tie → title), first ten. Current points per player via `score_player`.
6. `non_zero = count(p.median > 0)`. States (§10.1, Final first): Final when `today > window_end + 1`; else Live when `non_zero >= season.min_projections_for_forecast`, else Early. Forecast runs in Live and Final; in Early build the reason string exactly as §9.5: `"only {non_zero} films have non-zero projections ({threshold} required for a meaningful top-ten ranking)"`.
7. Render all five pages + `data.json` into `out_dir` (leaderboard wide; whatif/scenarios locked when no forecast; history gated on its own file's rows only).
8. Unless `local`: append both history files (forecast only if it exists).

- [ ] **Step 1: Write the failing tests** — `tests/test_build.py`:

```python
import json
from datetime import date
from pathlib import Path
import pytest
import smw.render.build as build
from tests.conftest import FIXTURES

TODAY = date(2026, 8, 15)
CHART_HTML = (FIXTURES / "year_chart.html").read_text()

@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    (d / "groups").mkdir(parents=True)
    (d / "season.yaml").write_text(
        "year: 2026\nwindow_start: 2026-05-01\nwindow_end: 2026-09-07\n"
        "seed: 42\nmonte_carlo_trials: 500\nmin_projections_for_forecast: 25\n")
    (d / "groups" / "g.yaml").write_text(
        "group_id: g\ndisplay_name: G\nplayers:\n"
        "  alice:\n"
        "    ranked: [Big Summer Film, Mid June Comedy, Labor Day Opener, F4, F5, F6, F7, F8, F9, F10]\n"
        "    dark_horses: [D1, D2, Tiny Tail Film]\n")
    return d

@pytest.fixture(autouse=True)
def offline_chart(monkeypatch):
    monkeypatch.setattr(build, "fetch", lambda year: CHART_HTML)

def _run(data_dir, tmp_path, today=TODAY, local=True):
    out = tmp_path / "out"
    build.run_build(data_dir, out, today, local=local)
    return out

def test_writes_all_pages_and_data_json(data_dir, tmp_path):
    out = _run(data_dir, tmp_path)
    for f in ("index.html", "whatif.html", "scenarios.html", "history.html",
              "rules.html", "data.json"):
        assert (out / f).exists()

def test_degraded_run_data_json_shape(data_dir, tmp_path):
    # 4 windowed chart films, but Labor Day Opener (Sep 7) is pre_release on Aug 15
    # with no analyst entry → 3 non-zero projections, threshold 25 → Early.
    # §5.7: the six forecast keys MUST be present as maps of every username to null.
    out = _run(data_dir, tmp_path)
    d = json.loads((out / "data.json").read_text())
    assert d["forecast_available"] is False
    assert "only 3 films have non-zero projections" in d["forecast_unavailable_reason"]
    for key in ("win_prob", "tie_prob", "median_final_pts",
                "p10_final_pts", "p90_final_pts"):
        assert d[key] == {"alice": None}
    assert d["winning_scenarios"] == {"alice": None}
    assert d["captured_at"] == "2026-08-15"
    assert isinstance(d["current_points"]["alice"], int)
    assert d["non_zero_projections"] == 3

def _add_estimates(data_dir, n=8):
    # Complete analyst entries for n extra in-window films → n more non-zero
    # projections (3 chart films + n).
    entries = "".join(
        f'"Estimated Film {i}":\n'
        "  release_date: 2026-07-10\n"
        "  opening_weekend_estimate: 40_000_000\n"
        "  total_domestic_estimate: 110_000_000\n"
        "  confidence: med\n"
        for i in range(n))
    (data_dir / "preopening_projections.yaml").write_text(entries)

def test_forecast_gate_boundary(data_dir, tmp_path):
    # §13.5 named gap: one below the threshold degrades, at the threshold forecasts.
    _add_estimates(data_dir, n=8)   # 3 + 8 = 11 non-zero projections
    season_yaml = (data_dir / "season.yaml").read_text()
    (data_dir / "season.yaml").write_text(
        season_yaml.replace("min_projections_for_forecast: 25",
                            "min_projections_for_forecast: 12"))
    out = _run(data_dir, tmp_path)  # 11 < 12 → degraded, no forecast keys populated
    d = json.loads((out / "data.json").read_text())
    assert d["forecast_available"] is False
    assert d["win_prob"] == {"alice": None}
    (data_dir / "season.yaml").write_text(
        season_yaml.replace("min_projections_for_forecast: 25",
                            "min_projections_for_forecast: 11"))
    out = _run(data_dir, tmp_path)  # 11 >= 11 (and >= 10 structural) → forecasts
    d = json.loads((out / "data.json").read_text())
    assert d["forecast_available"] is True
    assert isinstance(d["win_prob"]["alice"], float)

def test_structural_floor_dominates_policy_threshold(data_dir, tmp_path):
    # Threshold met but fewer than 10 projected films: a top ten cannot be ranked
    # (§9.5 structural). The site build must degrade, not crash.
    season_yaml = (data_dir / "season.yaml").read_text()
    (data_dir / "season.yaml").write_text(
        season_yaml.replace("min_projections_for_forecast: 25",
                            "min_projections_for_forecast: 3"))
    out = _run(data_dir, tmp_path)  # 3 >= 3 policy, but 3 < 10 structural
    d = json.loads((out / "data.json").read_text())
    assert d["forecast_available"] is False

def test_local_run_appends_nothing(data_dir, tmp_path):
    _run(data_dir, tmp_path, local=True)
    assert not (data_dir / "box_office_history.jsonl").exists()
    assert not (data_dir / "forecast_history.jsonl").exists()

def test_production_run_appends_box_office_rows(data_dir, tmp_path):
    # §13.5 named gap: a production run appends the expected rows; local appends none.
    _run(data_dir, tmp_path, local=False)
    lines = [json.loads(l) for l in
             (data_dir / "box_office_history.jsonl").read_text().splitlines()]
    titles = {l["movie"] for l in lines}
    assert "Big Summer Film" in titles and "Tiny Tail Film" in titles
    assert all(l["date"] == "2026-08-15" for l in lines)
    assert all(l["cumulative_gross"] > 0 for l in lines)
    # degraded run → no forecast history line (the chart gap, §5.6)
    assert not (data_dir / "forecast_history.jsonl").exists()

def test_frozen_run_never_fetches(data_dir, tmp_path, monkeypatch):
    def boom(year):
        raise AssertionError("chart fetched after freeze")
    monkeypatch.setattr(build, "fetch", boom)
    # seed history so resolution has something to carry
    (data_dir / "box_office_history.jsonl").write_text(
        '{"movie": "Big Summer Film", "date": "2026-09-08", "cumulative_gross": 100.0}\n')
    out = _run(data_dir, tmp_path, today=date(2026, 9, 9))
    assert (out / "index.html").exists()

def test_missing_history_file_is_warning_not_error(data_dir, tmp_path, capsys):
    _run(data_dir, tmp_path)
    assert "history" in capsys.readouterr().out.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_build.py -v` — Expected: FAIL with import error.

- [ ] **Step 3: Implement `smw/render/build.py`**

```python
"""Pipeline glue: the only module that knows the order of operations (Appendix B)."""
import json
from datetime import date, timedelta
from pathlib import Path

from smw.catalog.normalize import (apply_chart_aliases, build_films, canonical,
                                   load_overrides, load_preopening)
from smw.catalog.resolve import load_history, resolve_grosses
from smw.config.groups import Group, load_group
from smw.config.season import Season, load_season
from smw.ingest.boxoffice import chart_floor, fetch_chart, parse_chart, windowed
from smw.model.project import MovieCatalog, build_catalog
from smw.model.simulate import MIN_FILMS_FOR_TOP_TEN, SimResult, simulate
from smw.render.chart import build_history_data
from smw.render.page import (base_context, build_scenarios_view, build_whatif_data,
                             make_env, render_history, render_leaderboard,
                             render_rules, render_scenarios, render_whatif)
from smw.render.views import build_leaderboard_view
from smw.score.rules import score_player

fetch = fetch_chart  # network seam; tests monkeypatch this


def build_data_json(season, group, catalog, sim, current_points,
                    non_zero, reason, today) -> dict:
    players = sorted(group.players)
    if sim is None:
        null_map = {u: None for u in players}
        forecast = {
            "win_prob": dict(null_map), "tie_prob": dict(null_map),
            "median_final_pts": dict(null_map), "p10_final_pts": dict(null_map),
            "p90_final_pts": dict(null_map), "winning_scenarios": dict(null_map),
        }
    else:
        forecast = {
            "win_prob": sim.win_prob, "tie_prob": sim.tie_prob,
            "median_final_pts": sim.median_pts, "p10_final_pts": sim.p10_pts,
            "p90_final_pts": sim.p90_pts,
            "winning_scenarios": {
                u: None if sc is None else {
                    "films": sc.films, "grid": sc.grid, "totals": sc.totals,
                    "win_pct": sc.win_pct, "margin": sc.margin}
                for u, sc in sim.scenarios.items()},
        }
    out = {
        "captured_at": today.isoformat(),
        "current_points": current_points,
        "forecast_available": sim is not None,
        "non_zero_projections": non_zero,
        "projections": [
            {"movie_title": p.title, "median_in_window_gross": p.median,
             "sigma": p.sigma, "floor": p.floor}
            for p in catalog.projections],
        **forecast,
    }
    if sim is None:
        out["forecast_unavailable_reason"] = reason
    return out


def append_box_office_history(path: Path, grosses: dict[str, float], today: date):
    with open(path, "a") as f:
        for title in sorted(grosses):
            if grosses[title] > 0:
                f.write(json.dumps({"movie": title, "date": today.isoformat(),
                                    "cumulative_gross": grosses[title]}) + "\n")


def append_forecast_history(path: Path, sim: SimResult, today: date):
    with open(path, "a") as f:
        for u in sorted(sim.win_prob):
            f.write(json.dumps({
                "date": today.isoformat(), "player": u,
                "win_prob": sim.win_prob[u],
                "median_final_pts": sim.median_pts[u],
                "p10": sim.p10_pts[u], "p90": sim.p90_pts[u]}) + "\n")


def _load_forecast_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def run_build(data_dir: Path, out_dir: Path, today: date, local: bool) -> None:
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    season = load_season(data_dir / "season.yaml")
    groups = [load_group(p) for p in sorted((data_dir / "groups").glob("*.yaml"))]
    overrides = load_overrides(data_dir / "movies_overrides.yaml")
    preopening = load_preopening(data_dir / "preopening_projections.yaml")
    history_path = data_dir / "box_office_history.jsonl"
    if not history_path.exists():
        print("warning: no box-office history file yet (normal on the first run)")
    history = load_history(history_path)

    if (today - timedelta(days=1)) <= season.window_end:
        raw = apply_chart_aliases(parse_chart(fetch(season.year), season.year), overrides)
        floor = chart_floor(raw)
        chart_rows = windowed(raw, season)  # Guards A and B
    else:
        # §6.1: chart frozen from window_end + 2 — MUST NOT be read at all.
        chart_rows, floor = [], 0.0

    grosses, carried, chart_usable = resolve_grosses(
        season, history, chart_rows, floor, today)

    films = build_films(season, groups, chart_rows, grosses, carried,
                        overrides, preopening, today)
    picked = {canonical(t, overrides)
              for g in groups for p in g.players.values()
              for t in p.ranked + p.dark_horses}
    catalog = build_catalog(season, films, history, picked, overrides, today)
    for w in catalog.warnings:
        print(f"warning: {w}")

    gross_ranked = sorted(((g, t) for t, g in grosses.items() if g > 0),
                          key=lambda x: (-x[0], x[1]))
    actual_top = [t for _, t in gross_ranked[:10]]

    non_zero = sum(1 for p in catalog.projections if p.median > 0)
    # §10.1: Final first, then the projection count decides Early vs Live.
    # The structural floor (§9.5) also degrades here: a site build must not crash
    # merely because the season is young.
    forecastable = (non_zero >= season.min_projections_for_forecast
                    and non_zero >= MIN_FILMS_FOR_TOP_TEN)
    reason = None
    if not forecastable:
        reason = (f"only {non_zero} films have non-zero projections "
                  f"({season.min_projections_for_forecast} required for a "
                  "meaningful top-ten ranking)")

    env = make_env()
    for group in groups:
        # Multi-group output layout is explicitly deferred (§3.6): with one group,
        # output goes to the output root. Loop kept so roster-dependent work is
        # already per-group.
        sim = simulate(season, group, catalog) if forecastable else None
        current_points = {u: score_player(group.players[u], actual_top)
                          for u in group.players}
        ctx = base_context(season, group, "leaderboard", today)
        view = build_leaderboard_view(season, group, catalog, sim, current_points,
                                      actual_top, reason, today)
        render_leaderboard(env, out_dir, ctx, view)
        render_whatif(env, out_dir, {**ctx, "active": "whatif"},
                      build_whatif_data(season, group, catalog, sim) if sim else None,
                      reason)
        render_scenarios(env, out_dir, {**ctx, "active": "scenarios"},
                         build_scenarios_view(group, sim) if sim else None, reason)
        render_history(env, out_dir, {**ctx, "active": "history"},
                       build_history_data(_load_forecast_rows(
                           data_dir / "forecast_history.jsonl")))
        render_rules(env, out_dir, {**ctx, "active": "rules"})
        (out_dir / "data.json").write_text(json.dumps(
            build_data_json(season, group, catalog, sim, current_points,
                            non_zero, reason, today),
            indent=2, sort_keys=True))

        if not local and sim is not None:
            append_forecast_history(data_dir / "forecast_history.jsonl", sim, today)

    if not local:
        # Roster-independent: appended once per build, never once per group.
        append_box_office_history(history_path, grosses, today)
```

- [ ] **Step 4: Implement `smw/__main__.py`**

```python
import argparse
from datetime import date
from pathlib import Path

from smw.render.build import run_build

parser = argparse.ArgumentParser(description="Summer Movie Wager site builder")
parser.add_argument("--date", type=date.fromisoformat, default=date.today(),
                    help="run date (default: today); the only wall-clock input")
parser.add_argument("--data", type=Path, default=Path("data"))
parser.add_argument("--out", type=Path, default=Path("out"))
parser.add_argument("--local", action="store_true",
                    help="write the site but append to NO history file (dev runs)")
args = parser.parse_args()
run_build(args.data, args.out, args.date, local=args.local)
```

- [ ] **Step 5: Run to verify pass**

Run: `pytest tests/test_build.py -v` — Expected: 8 PASS. Fix `render_history`'s ctx `active` handling if the nav highlights wrong (each page's ctx overrides `active` as shown).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: build pipeline, data.json, history writers, CLI

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 20: Cross-implementation scoring test vector (§12.2, §13.5)

**Files:**
- Create: `tests/fixtures/scoring_vectors.json`, `tests/run_js_vectors.mjs`, `tests/test_cross_impl.py`

**Interfaces:**
- Consumes: `smw/score/rules.py` (Python side) and `smw/render/static/scoring.js` (client side, exports under Node).
- Produces: one shared vector file asserted against **both** implementations, so a change to one that is not mirrored in the other fails a test rather than silently producing two different answers on two pages of the same site.

- [ ] **Step 1: Write the shared vectors** — `tests/fixtures/scoring_vectors.json`. Each case: a roster, a finish order, the expected total. Cover both endpoints, the middle, every distance rung, dark horses, and a partial finish.

```json
[
  {
    "name": "perfect season",
    "ranked": ["A","B","C","D","E","F","G","H","I","J"],
    "dark_horses": ["X","Y","Z"],
    "finish": ["A","B","C","D","E","F","G","H","I","J"],
    "expected": 106
  },
  {
    "name": "endpoints plus dark horse",
    "ranked": ["A","B","C","D","E","F","G","H","I","J"],
    "dark_horses": ["X","Y","Z"],
    "finish": ["A","Q","R","S","T","U","V","W","X","J"],
    "expected": 27
  },
  {
    "name": "every distance rung",
    "ranked": ["A","B","C","D","E","F","G","H","I","J"],
    "dark_horses": ["X","Y","Z"],
    "finish": ["B","A","E","C","J","D","S","T","U","V"],
    "expected": 34
  },
  {
    "name": "partial finish early season",
    "ranked": ["A","B","C","D","E","F","G","H","I","J"],
    "dark_horses": ["X","Y","Z"],
    "finish": ["C","X","A"],
    "expected": 11
  },
  {
    "name": "nothing hits",
    "ranked": ["A","B","C","D","E","F","G","H","I","J"],
    "dark_horses": ["X","Y","Z"],
    "finish": ["Q","R","S","T","U","V","W","N","O","P"],
    "expected": 0
  }
]
```

The expected values, hand-derived from §2.3–2.4 (they are the contract; if either
implementation disagrees with them, the implementation is wrong):
- *perfect season*: 13 + 10×8 + 13 = 106 (dark horses X/Y/Z miss).
- *endpoints plus dark horse*: A exact at #1 (13) + J exact at #10 (13) + X dark horse at #9 (1) = 27.
- *every distance rung*: B 2→1 (off 1: 7) + A 1→2 (off 1: 7) + C 3→4 (off 1: 7) + D 4→6 (off 2: 5) + E 5→3 (off 2: 5) + J 10→5 (off 5: 3) = 34.
- *partial finish*: C 3→1 (off 2: 5) + X dark horse at #2 (1) + A 1→3 (off 2: 5) = 11.
- *nothing hits*: 0.

- [ ] **Step 2: Write and run the Python side** — `tests/test_cross_impl.py`:

```python
import json
import shutil
import subprocess
import pytest
from smw.config.groups import PlayerPicks
from smw.score.rules import score_player
from tests.conftest import FIXTURES

VECTORS = json.loads((FIXTURES / "scoring_vectors.json").read_text())

@pytest.mark.parametrize("case", VECTORS, ids=[c["name"] for c in VECTORS])
def test_python_scoring_matches_vector(case):
    picks = PlayerPicks("v", tuple(case["ranked"]), tuple(case["dark_horses"]))
    assert score_player(picks, case["finish"]) == case["expected"]

@pytest.mark.skipif(shutil.which("node") is None,
                    reason="node required for the client-side half of §12.2's "
                           "shared vector — install node; do not delete this test")
def test_js_scoring_matches_vector():
    result = subprocess.run(
        ["node", str(FIXTURES.parent / "run_js_vectors.mjs")],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
```

Run the Python cases: `pytest tests/test_cross_impl.py -k python -v`. Where a vector's
`expected` disagrees, hand-check the case against §2.3–2.4; `rules.py` has already been
verified rung-by-rung, so a disagreement here is an arithmetic slip in the JSON —
correct the JSON and re-run until all five pass *and* each value has been hand-derived.

- [ ] **Step 3: Write the Node runner** — `tests/run_js_vectors.mjs`:

```javascript
import { createRequire } from "module";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const scoring = require(join(here, "..", "smw", "render", "static", "scoring.js"));
const vectors = JSON.parse(
  readFileSync(join(here, "fixtures", "scoring_vectors.json"), "utf8"));

let failures = 0;
for (const c of vectors) {
  const got = scoring.scorePlayer(c.ranked, c.dark_horses, c.finish);
  if (got !== c.expected) {
    console.log(`FAIL ${c.name}: js=${got} expected=${c.expected}`);
    failures += 1;
  }
}
if (failures > 0) process.exit(1);
console.log(`ok: ${vectors.length} vectors`);
```

(`scoring.js` is plain CommonJS-compatible script; `createRequire` loads it without
modification.)

- [ ] **Step 4: Run to verify both sides pass**

Run: `pytest tests/test_cross_impl.py -v` — Expected: 5 Python cases PASS + JS test PASS (or SKIP only on a machine without node).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "test: shared scoring vectors asserted against Python and JS

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 21: Self-containment audit, operator README, 2026 first build

**Files:**
- Create: `tests/test_self_containment.py`, `README.md`
- Modify: `tests/fixtures/snapshot_index.html` (final re-lock if anything drifted)
- Generate: `out/` (first committed local build)

- [ ] **Step 1: Write the self-containment test** — `tests/test_self_containment.py` (§13.1: a test asserting no external-origin references appear in the output — run against a full build, all five pages):

```python
import json
from datetime import date
import pytest
import smw.render.build as build
from tests.conftest import FIXTURES

PAGES = ("index.html", "whatif.html", "scenarios.html", "history.html", "rules.html")

@pytest.fixture
def built_site(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "fetch",
                        lambda year: (FIXTURES / "year_chart.html").read_text())
    d = tmp_path / "data"
    (d / "groups").mkdir(parents=True)
    (d / "season.yaml").write_text(
        "year: 2026\nwindow_start: 2026-05-01\nwindow_end: 2026-09-07\n"
        "seed: 42\nmonte_carlo_trials: 500\nmin_projections_for_forecast: 3\n")
    (d / "groups" / "g.yaml").write_text(
        "group_id: g\ndisplay_name: G\nplayers:\n"
        "  alice:\n"
        "    ranked: [Big Summer Film, Mid June Comedy, Labor Day Opener,"
        " F4, F5, F6, F7, F8, F9, F10]\n"
        "    dark_horses: [D1, D2, Tiny Tail Film]\n")
    out = tmp_path / "out"
    build.run_build(d, out, date(2026, 8, 15), local=True)
    return out

def test_no_external_origin_references(built_site):
    for page in PAGES:
        html = (built_site / page).read_text()
        for marker in ("http://", "https://", "//cdn", "@import", "url(http"):
            assert marker not in html, f"{page} contains {marker}"

def test_no_page_fetches_data_json(built_site):
    # data.json is published for humans and tools; no page fetches it (§13.1).
    for page in PAGES:
        html = (built_site / page).read_text()
        assert "fetch(" not in html
        assert "XMLHttpRequest" not in html

def test_reproducible_build(built_site, tmp_path, monkeypatch):
    # Byte-identical output for identical inputs (§1.3): rebuild into a second
    # directory from the same inputs and diff every page.
    monkeypatch.setattr(build, "fetch",
                        lambda year: (FIXTURES / "year_chart.html").read_text())
    out2 = tmp_path / "out2"
    # rebuild with the same data dir the fixture created
    build.run_build(tmp_path / "data", out2, date(2026, 8, 15), local=True)
    for page in PAGES + ("data.json",):
        assert (built_site / page).read_bytes() == (out2 / page).read_bytes(), page
```

- [ ] **Step 2: Run to verify pass**

Run: `pytest tests/test_self_containment.py -v` — Expected: 3 PASS. Common failures to fix here, not suppress: an `https://` left in a template comment; nondeterministic dict ordering leaking into a page (sort at the source).

- [ ] **Step 3: Write `README.md`** — operator documentation. MUST contain the end-of-season protocol (§6.4, §13.4 — the only unrecoverable failure in the system):

```markdown
# Summer Movie Wager — Tracker & Forecaster

Static-site tracker and Monte Carlo forecaster for a season-long box-office
prediction game. One network dependency (Box Office Mojo's yearly chart),
no server, no build toolchain. Output in `out/` is generated — never hand-edit it.

## Running

    .venv/bin/pytest                       # tests run BEFORE any production build
    .venv/bin/python -m smw --local        # dev run: writes out/, appends NO history
    .venv/bin/python -m smw                # production run: also appends history files

Every exploratory or development run uses `--local`. A production run on an
off-cadence day skews the observed-decay estimator, which assumes roughly
weekly snapshots.

## Weekly cadence

Refresh manually (never on a schedule — a bad upstream day should be noticed,
not committed), roughly weekly, on a consistent weekday. Monday is the natural
choice: the weekend is fully reported. Commit the updated `data/` and `out/`.

## ⚠️ End-of-season protocol (hard deadline, no recovery path)

- **The final production run MUST happen on `window_end + 1 day`**
  (for 2026: run on **2026-09-08**). That is the single day the chart reports
  exactly through the window's last day.
- Running on `window_end` is too early — it misses the final day (Labor Day,
  typically substantial grosses).
- Running on `window_end + 2` or later is too late — the chart is frozen by
  design and the site stays at whatever the previous run recorded.
- **Before accepting the final run, verify the top titles actually advanced**
  versus the previous run. Identical figures mean the source has not posted the
  final weekend yet; wait and re-run later the same day (same-day re-runs are
  safe — history merges by max).
- If the deadline is missed there is no recovery in code: final figures must be
  appended to `data/box_office_history.jsonl` by hand.

## Operator files (maintained through the season)

- `data/preopening_projections.yaml` — analyst estimates. The build's
  "no projection" warnings are your to-do list.
- `data/movies_overrides.yaml` — categories (classify EVERY picked film,
  including genuinely wide ones), title aliases, date/status corrections.
  A Guard C failure prints the exact alias block to add here.
- `data/groups/*.yaml` — rosters; locked once the window opens.
- `data/season.yaml` — dates, thresholds, seed.

## Snapshot ritual

The leaderboard has a byte-exact snapshot test. To regenerate deliberately:
delete `tests/fixtures/snapshot_index.html`, run the test once (it rewrites the
fixture and fails), **open the file in a browser and look at it**, then re-run
to lock. A snapshot regenerated without inspection tests nothing.
```

- [ ] **Step 4: Full suite, final snapshot check**

Run: `pytest -v` — Expected: everything PASSES, including the snapshot. If any earlier task drifted the CSS or templates since the last lock, do the ritual one final time (delete, regenerate, inspect in a browser, re-lock).

- [ ] **Step 5: First real local build (network required, one-off operator step)**

```bash
.venv/bin/python -m smw --local --date "$(date +%F)"
open out/index.html   # look at every page; verify warnings list expected films
```

Expected console output: the missing-history warning, the unclassified-category
warning for any picked film not yet in `movies_overrides.yaml`, and the
no-projection warning listing picked films without analyst entries. The site is in
current-points mode until ~25 films project. Also save the real fetched chart over
`tests/fixtures/year_chart.html` now (`curl -A "smw-tracker" https://www.boxofficemojo.com/year/2026/ > tests/fixtures/year_chart.html`),
adjust the fixture-dependent test expectations to the real chart's contents
(titles/counts in `tests/test_boxoffice.py`, `tests/test_build.py`,
`tests/test_self_containment.py`), and re-run the suite — §13.5 wants parsing tests
against the real committed chart, offline.

- [ ] **Step 6: Commit the build output and README**

```bash
git add -A && git commit -m "docs: operator README; first local build committed

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Self-review notes (spec coverage check)

- §2 scoring → T4; §2.6 strict-win/tie separation → T12 (aggregation) + §12.1 footer (win odds shows strict only; both in `data.json`, T19).
- §3 config/tenancy → T2/T3; catalog carries no roster data (T11 docstring + structure); per-group loop in T19; expensive half runs once per build (T19 order of operations).
- §4 ingest rules + Guards A/B → T5; §4.5 coverage floor → carry-forward T7.
- §5 data files → T2 (season), T3 (groups), T6 (preopening/overrides), T7 (box-office history dedup), T19 (forecast history, data.json §5.7 null-map requirement).
- §6 resolution, Guard C, aliases at both points (T6 ingest-side, T8 normalize-side), end-of-season protocol → T19 freeze logic + T21 README.
- §7 both models, clamp, no-fallback, bands, in-window labeling (T15 films/matrix column headers) → T9/T10/T11.
- §8 category warning → T11.
- §9 simulation, floor test, thresholds named distinctly (T12 structural raise; T19 degrades and composes the reason string), medoid scenarios → T13.
- §10 lifecycle states → T19; day-zero requirements → T3 (empty roster), T15 (divider suppression, missing-pick placeholder, empty lists), T19 (missing history warning).
- §11 output files, nav always-live, locked states (whatif/scenarios on forecast, history on own data), autoescape + `<` → T14–T19.
- §12 four pages → T15–T18, incl. footer-sum rule with mandatory comment, single projected-rank notion, keyboard parity, competition ties, CSS cutoff, medoid grid with middle dots, SVG chart with gap-breaking paths and alphabetical palette.
- §13 self-containment test, theming order, snapshot ritual, five named test gaps (gate boundary T19, history writers T19, decay clamp T9, cross-impl vector T20, current-points render T15), README protocol → T14/T15/T19/T20/T21.
- Known accepted gaps (per spec): chart tooltip pointer-only (table fallback is the path); palette ceiling of 8 players.
