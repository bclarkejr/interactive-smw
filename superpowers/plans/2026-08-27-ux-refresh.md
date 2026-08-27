# UX Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the site multi-season / multi-group (`out/<year>/<group>/`), bring every page to `brainstorming/mockup.html` parity, add masthead year/group selectors, and replace the hand-rolled What If? drag code with vendored SortableJS.

**Architecture:** `run_build` discovers `data/seasons/<year>/`, runs the existing per-season body once per season, and writes each group to `<out>/<year>/<group_id>/` plus a root redirect. `site.css`/`theme.js` become the mockup's verbatim blocks; every template is rewritten to the mockup's skeleton and class vocabulary; all selector hrefs, chart geometry and footer copy are computed in Python and passed in finished (rebuild §11.4).

**Tech Stack:** Python ≥3.11, Jinja2, PyYAML, numpy, pytest; SortableJS 1.15.6 (vendored, minified, MIT) as the only client dependency.

**Spec:** `superpowers/specs/2026-08-27-ux-refresh-spec.md` (amends `superpowers/specs/2026-08-15-standalone-rebuild-spec.md`). Executors read both. `brainstorming/mockup.html` is normative for presentation.

## Global Constraints

Copied from the spec / AGENTS.md; every task implicitly includes these.

- Reproducible output: identical inputs (including `--date`) produce byte-identical output for every file under `<out>/`, including the root redirect.
- Self-contained pages: zero network requests; all CSS/JS inlined; no `http://`, `https://`, `//cdn`, `@import`, `url(http`, `fetch(`, `XMLHttpRequest` in any page — including the page carrying the vendored library.
- No module-level date or threshold constants in projection, simulation, or render layers. Chart geometry (`W, H, ML, MR, MT, MB`) is a game/presentation constant and allowed.
- Render layer never sorts, ranks, or computes; view models arrive finished. Templates only emit.
- `score`, `simulate`, `render` take `(Season, Group, MovieCatalog)`; render functions take an output directory.
- Autoescaping forced on; embedded JSON escapes `<` as `<`.
- Persisted data: `data/seasons/<year>/{season.yaml, groups/*.yaml, preopening_projections.yaml, movies_overrides.yaml, box_office_history.jsonl, forecast_history/<group_id>.jsonl}`. **No persisted refresh/run-date record.** No new persisted file kinds.
- `site.css` = mockup `<style>` (lines 12–144) verbatim minus `.mocknote`, `.page`/`.page.active`, and the `--s-<username>` declarations, plus exactly one `/* ---------- site additions ---------- */` section holding only `.series-N` rules and selector styling. Token vocabulary is the mockup's: `--bg --surface --ink --ink2 --muted --grid --baseline --border --affirm --neg --accent --pill --hl`. Old tokens `--card --dim --pos --gold` and old classes `.num .table-scroll .cell-* .divider-row .stats-line .standings #film-list .two-col .tab-row .tab .highlight-col .chart-wrap .odds-chart .legend-swatch` are gone.
- `<h1>` is `🍿 Summer Movie Wager`; `<title>` is `{page} · Summer Movie Wager {year} · {display_name}`.
- SortableJS **1.15.6 minified**, vendored at `smw/render/static/sortable.min.js`, banner keeps copyright + licence, contains no URL.
- Deterministic checks before any review round: `.venv/bin/pytest`.
- Commit only this task's files (never `git add -A`); working tree clean before each cross-review.

## Decisions the spec forced (read before executing)

1. **Criterion 11 is tested against `whatif.js`, not `whatif.html`.** The genuine `Sortable.min.js` 1.15.6 contains the strings `dragstart`, `dragover`, `touchstart`, and `elementFromPoint` (verified by grep on the unpkg file), so a page that inlines the library can never satisfy "does not contain" them. The intent — the *site's own* drag code is gone — is checked on `smw/render/static/whatif.js`. `whatif.html` is still checked for `new Sortable(`.
2. **`brainstorming/mockup.html` is un-ignored and committed.** The §3.1 parity test must read it, and a test that depends on an untracked file is not reproducible. Only that one file; the rest of `brainstorming/` stays ignored.
3. **`table#wiStandings` is exempt from "every table in `div.scroller`".** §3.5 and the mockup both put it directly under `div[aria-live=polite]` inside `.wi-panel`. Mockup wins over criterion 8.
4. **Zero cells in scenarios are `td.mid`** (spec §3.3/§3.6), not the mockup's `span.mid` — the mockup's own CSS rule is `td.mid`, so the span is a mockup bug.
5. **Legend/direct-label "latest value" is the last non-null value** (existing behaviour), so a player missing the newest refresh is still labelled.
6. **Crosshair line is emitted server-side, hidden**, and only positioned by JS. The mockup creates it with `createElementNS("http://www.w3.org/2000/svg", …)`, which would put `http://` in the page and fail self-containment.

## File Structure

```
smw/config/season.py         + default_group field, load_season_dir()           (T1)
data/seasons/2026/…          git mv of the four data files                       (T1)
smw/render/build.py          run_build → discover seasons → _build_season()      (T2)
smw/render/templates/redirect.html.j2   root redirect                            (T2)
smw/render/static/site.css   mockup verbatim + additions                         (T3)
smw/render/static/theme.js   mockup head script + toggle handler                 (T3)
smw/render/page.py           Site dataclass, base_context selectors, money fmt   (T3, T4)
smw/render/templates/base.html.j2       mockup skeleton                          (T3)
smw/render/templates/index.html.j2      leaderboard                              (T4)
smw/render/views.py          list labels, stats copy, released fmt              (T4)
tests/fixtures/snapshot_index.html      regenerated                              (T4)
smw/render/static/sortable.min.js       vendored                                 (T5)
smw/render/static/whatif.js  SortableJS rewrite                                  (T5)
smw/render/templates/whatif.html.j2                                              (T5)
smw/render/templates/scenarios.html.j2, static/scenarios.js                      (T6)
smw/render/chart.py, templates/history.html.j2, static/history.js               (T7)
smw/render/templates/rules.html.j2                                               (T8)
tests/test_mockup_parity.py  site-wide criteria 7/8/9                            (T9)
AGENTS.md, README.md, out/   docs + regenerated site                             (T9)
```

Every task: run `.venv/bin/pytest -q` before committing. If `.venv` is missing: `uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python --config-settings editable_mode=compat -e '.[dev]'`.

---

### Task 1: Season `default_group`, `load_season_dir`, data move

**Files:**
- Modify: `smw/config/season.py`
- Move: `data/season.yaml`, `data/groups/*.yaml`, `data/preopening_projections.yaml`, `data/movies_overrides.yaml` → `data/seasons/2026/…`
- Test: `tests/test_season.py`

**Interfaces:**
- Consumes: `smw.config.groups.load_group(path) -> Group` (exists).
- Produces: `Season.default_group: str | None` (always a `str` after `load_season_dir`); `load_season_dir(season_dir: Path) -> tuple[Season, list[Group]]` — groups sorted by file name; raises `ValueError` on dir/year mismatch, unknown `default_group`, or no group files.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_season.py`)

```python
from smw.config.season import load_season_dir

def _season_dir(tmp_path, name="2026", extra="", groups=("b", "a")):
    d = tmp_path / name
    (d / "groups").mkdir(parents=True)
    (d / "season.yaml").write_text(BASE + extra)
    for g in groups:
        (d / "groups" / f"{g}.yaml").write_text(f"group_id: {g}\ndisplay_name: {g.upper()}\n")
    return d

def test_default_group_key_loads(tmp_path):
    p = tmp_path / "season.yaml"
    p.write_text(BASE + "default_group: smw-friends\n")
    assert load_season(p).default_group == "smw-friends"
    p.write_text(BASE)
    assert load_season(p).default_group is None

def test_default_group_must_be_string(tmp_path):
    p = tmp_path / "season.yaml"
    p.write_text(BASE + "default_group: 3\n")
    with pytest.raises(ValueError, match="default_group"):
        load_season(p)

def test_load_season_dir_fills_default_group_lexically(tmp_path):
    season, groups = load_season_dir(_season_dir(tmp_path))
    assert season.default_group == "a"
    assert [g.group_id for g in groups] == ["a", "b"]

def test_load_season_dir_keeps_explicit_default_group(tmp_path):
    season, _ = load_season_dir(_season_dir(tmp_path, extra="default_group: b\n"))
    assert season.default_group == "b"

def test_load_season_dir_unknown_default_group_raises(tmp_path):
    with pytest.raises(ValueError, match="default_group"):
        load_season_dir(_season_dir(tmp_path, extra="default_group: zzz\n"))

def test_load_season_dir_name_must_equal_year(tmp_path):
    with pytest.raises(ValueError, match="2026"):
        load_season_dir(_season_dir(tmp_path, name="2025"))

def test_load_season_dir_requires_a_group(tmp_path):
    with pytest.raises(ValueError, match="group"):
        load_season_dir(_season_dir(tmp_path, groups=()))
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_season.py -q`
Expected: ImportError on `load_season_dir` / `unknown key(s): default_group`.

- [ ] **Step 3: Implement** in `smw/config/season.py`

Add to imports: `from dataclasses import dataclass, field, fields, replace` and `from smw.config.groups import Group, load_group`.

Add field to `Season` (after `default_wow`):
```python
    default_group: str | None = None
```

Add to `_validate` (end of function):
```python
    if s.default_group is not None and not isinstance(s.default_group, str):
        raise ValueError(f"{where}: default_group must be a string")
```

Append:
```python
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
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_season.py -q` — Expected: all PASS.

- [ ] **Step 5: Move the data with `git mv`**

```bash
mkdir -p data/seasons/2026/groups
git mv data/season.yaml data/seasons/2026/season.yaml
git mv data/groups/filmcast.yaml data/seasons/2026/groups/filmcast.yaml
git mv data/groups/smw-friends.yaml data/seasons/2026/groups/smw-friends.yaml
git mv data/preopening_projections.yaml data/seasons/2026/preopening_projections.yaml
git mv data/movies_overrides.yaml data/seasons/2026/movies_overrides.yaml
rmdir data/groups 2>/dev/null; true
printf 'default_group: smw-friends\n' >> data/seasons/2026/season.yaml
.venv/bin/python -c "from smw.config.season import load_season_dir; s,g=load_season_dir('data/seasons/2026'); print(s.default_group, [x.group_id for x in g])"
```
Expected print: `smw-friends ['filmcast', 'smw-friends']`.

- [ ] **Step 6: Commit**

```bash
git add smw/config/season.py tests/test_season.py data
git commit -m "feat: season default_group, load_season_dir, data/seasons/<year> layout"
```

(The full suite is red after this task — `run_build` still reads the flat layout. Task 2 fixes it.)

---

### Task 2: Multi-season, multi-group build + root redirect

**Files:**
- Modify: `smw/render/build.py` (`run_build`, lines 121–201)
- Create: `smw/render/templates/redirect.html.j2`
- Modify: `smw/render/page.py` (add `render_redirect`)
- Test: `tests/test_build.py`, `tests/test_self_containment.py`

**Interfaces:**
- Consumes: `load_season_dir` (T1); `base_context(season, group, active, today)` (existing 4-arg form — T3 extends it with an optional `site` keyword; this task passes nothing extra).
- Produces: `run_build(data_dir, out_dir, today, local)` unchanged signature; output at `<out>/<year>/<group_id>/…` and `<out>/index.html`; `render_redirect(env, out_dir, target: str)`; `_build_season(env, season_dir, out_dir, season, groups, today, local)`.

- [ ] **Step 1: Repoint the existing test fixtures**

In `tests/test_build.py` replace the `data_dir` fixture and `_run`:
```python
@pytest.fixture
def data_dir(tmp_path):
    # The SEASON directory; run_build gets its grandparent (data/).
    d = tmp_path / "data" / "seasons" / "2026"
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

def _run(data_dir, tmp_path, today=TODAY, local=True):
    out = tmp_path / "out"
    build.run_build(data_dir.parent.parent, out, today, local=local)
    return out / "2026" / "g"
```
Then:
```bash
sed -i '' 's#data_dir / "forecast_history.jsonl"#data_dir / "forecast_history" / "g.jsonl"#g' tests/test_build.py
```

In `tests/test_self_containment.py` change the fixture's `d = tmp_path / "data"` to `d = tmp_path / "data" / "seasons" / "2026"`, `build.run_build(d, out, …)` to `build.run_build(tmp_path / "data", out, …)`, and `return out` to `return out / "2026" / "g"`. In `test_reproducible_build` change `build.run_build(tmp_path / "data", out2, …)` (already correct) and compare `(built_site / page)` against `(out2 / "2026" / "g" / page)`; also add `assert (built_site.parent.parent / "index.html").read_bytes() == (out2 / "index.html").read_bytes()`.

- [ ] **Step 2: Add the new tests** (append to `tests/test_build.py`)

```python
def _add_group(data_dir, gid, name):
    (data_dir / "groups" / f"{gid}.yaml").write_text(
        f"group_id: {gid}\ndisplay_name: {name}\nplayers:\n"
        "  bob:\n"
        "    ranked: [Mid June Comedy, Big Summer Film, Labor Day Opener, F4, F5, F6, F7, F8, F9, F10]\n"
        "    dark_horses: [D1, D2, Tiny Tail Film]\n")

def test_two_groups_get_their_own_directories(data_dir, tmp_path):
    _add_group(data_dir, "h", "Second League")
    out = _run(data_dir, tmp_path).parent
    for gid, name in (("g", "G"), ("h", "Second League")):
        for f in ("index.html", "whatif.html", "scenarios.html", "history.html",
                  "rules.html", "data.json"):
            assert (out / gid / f).exists(), f"{gid}/{f}"
        assert name in (out / gid / "index.html").read_text().split("</title>")[0]
    assert not (out / "index.html").exists()  # nothing written to <out>/<year>/ itself

def test_root_redirect_targets_newest_default_group(data_dir, tmp_path):
    _add_group(data_dir, "a", "Alpha")
    (data_dir / "season.yaml").write_text(
        (data_dir / "season.yaml").read_text() + "default_group: g\n")
    root = _run(data_dir, tmp_path).parent.parent
    html = (root / "index.html").read_text()
    assert 'content="0; url=2026/g/index.html"' in html
    assert 'href="2026/g/index.html"' in html
    assert "http://" not in html and "https://" not in html

def test_root_redirect_defaults_to_lexically_first_group(data_dir, tmp_path):
    _add_group(data_dir, "a", "Alpha")
    root = _run(data_dir, tmp_path).parent.parent
    assert "url=2026/a/index.html" in (root / "index.html").read_text()

def test_every_season_renders_and_redirect_picks_newest(data_dir, tmp_path):
    old = data_dir.parent / "2025"
    (old / "groups").mkdir(parents=True)
    (old / "season.yaml").write_text(
        "year: 2025\nwindow_start: 2025-05-02\nwindow_end: 2025-09-01\nseed: 7\n"
        "monte_carlo_trials: 500\n")
    (old / "groups" / "g.yaml").write_text((data_dir / "groups" / "g.yaml").read_text())
    (old / "box_office_history.jsonl").write_text(  # a Final season carries its frozen chart
        '{"movie": "Big Summer Film", "date": "2025-09-02", "cumulative_gross": 100.0}\n')
    out = _run(data_dir, tmp_path).parent.parent
    assert (out / "2025" / "g" / "index.html").exists()
    assert "url=2026/g/index.html" in (out / "index.html").read_text()

def test_missing_seasons_dir_is_a_build_error(tmp_path):
    (tmp_path / "data").mkdir()
    with pytest.raises(ValueError, match="seasons"):
        build.run_build(tmp_path / "data", tmp_path / "out", TODAY, local=True)

def test_production_run_appends_forecast_per_group_and_box_office_once(data_dir, tmp_path):
    _add_group(data_dir, "h", "H")
    _add_estimates(data_dir, n=8)
    (data_dir / "season.yaml").write_text(
        (data_dir / "season.yaml").read_text().replace(
            "min_projections_for_forecast: 25", "min_projections_for_forecast: 11"))
    _run(data_dir, tmp_path, local=False)
    for gid in ("g", "h"):
        rows = (data_dir / "forecast_history" / f"{gid}.jsonl").read_text().splitlines()
        assert len(rows) == 1  # one player per group, one refresh
    assert not (data_dir / "forecast_history.jsonl").exists()
    bo = (data_dir / "box_office_history.jsonl").read_text().splitlines()
    assert len(bo) == len({json.loads(l)["movie"] for l in bo})  # once per season, not per group
```

- [ ] **Step 3: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_build.py tests/test_self_containment.py -q`
Expected: failures (flat-layout `season.yaml` not found).

- [ ] **Step 4: Create `smw/render/templates/redirect.html.j2`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="0; url={{ target }}">
<title>Summer Movie Wager</title>
<script>{{ theme_js }}</script>
<style>{{ css }}</style>
</head>
<body>
<div class="wrap">
<p><a href="{{ target }}">Summer Movie Wager</a></p>
</div>
</body>
</html>
```

- [ ] **Step 5: Add `render_redirect` to `smw/render/page.py`** (after `write_page`)

```python
def render_redirect(env: Environment, out_dir: Path, target: str) -> None:
    write_page(env, "redirect.html.j2", out_dir, "index.html", {
        "css": Markup((STATIC / "site.css").read_text()),
        "theme_js": Markup((STATIC / "theme.js").read_text()),
        "target": target,
    })
```

- [ ] **Step 6: Rewrite `run_build` in `smw/render/build.py`**

Change imports: replace `from smw.config.groups import Group, load_group` with `from smw.config.groups import Group`; replace `from smw.config.season import Season, load_season` with `from smw.config.season import Season, load_season_dir`; add `render_redirect` to the `smw.render.page` import list.

Replace everything from `def run_build(` to the end of the file with:

```python
def run_build(data_dir: Path, out_dir: Path, today: date, local: bool) -> None:
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    seasons_root = data_dir / "seasons"
    season_dirs = sorted(p for p in seasons_root.glob("*") if p.is_dir()) \
        if seasons_root.is_dir() else []
    if not season_dirs:
        raise ValueError(f"{seasons_root}: no seasons found (an empty site is an error)")
    loaded = [load_season_dir(p) for p in season_dirs]  # dir name == year, so sorted by year
    env = make_env()
    for season_dir, (season, groups) in zip(season_dirs, loaded):
        _build_season(env, season_dir, out_dir / str(season.year), season, groups,
                      today, local)
    newest, _ = loaded[-1]
    render_redirect(env, out_dir, f"{newest.year}/{newest.default_group}/index.html")


def _build_season(env, season_dir: Path, out_dir: Path, season: Season,
                  groups: list[Group], today: date, local: bool) -> None:
    overrides = load_overrides(season_dir / "movies_overrides.yaml")
    groups = [canonical_group(g, overrides) for g in groups]  # §6.5 point 2
    preopening = load_preopening(season_dir / "preopening_projections.yaml")
    history_path = season_dir / "box_office_history.jsonl"
    if not history_path.exists():
        print(f"warning: {season.year}: no box-office history file yet (normal on the first run)")
    history = load_history(history_path)

    if season.window_start <= today - timedelta(days=1) <= season.window_end:
        raw = apply_chart_aliases(parse_chart(fetch(season.year), season.year), overrides)
        chart_rows = windowed(raw, season)  # Guards A and B — before the floor, so an
        floor = chart_floor(raw)            # empty parse fails with Guard A, not min()
    else:
        # §6.1: chart frozen from window_end + 2 — MUST NOT be read at all. Before the
        # window opens no in-window row can exist either (§10.1 pre-season is just
        # Early/Live on analyst numbers), so skip the fetch instead of tripping Guard B.
        chart_rows, floor = [], 0.0

    grosses, carried, chart_usable = resolve_grosses(
        season, history, chart_rows, floor, today)

    films = build_films(season, groups, chart_rows, grosses, carried,
                        overrides, preopening, today)
    picked = {canonical(t, overrides)
              for g in groups for p in g.players.values()
              for t in p.ranked + p.dark_horses}
    # Today's snapshot joins the series in memory (persisted only for production runs).
    catalog = build_catalog(season, films, with_snapshot(history, grosses, today),
                            picked, overrides, today)
    for w in catalog.warnings:
        print(f"warning: {w}")

    gross_ranked = sorted(((g, t) for t, g in grosses.items() if g > 0),
                          key=lambda x: (-x[0], x[1]))
    actual_top = [t for _, t in gross_ranked[:10]]

    non_zero = sum(1 for p in catalog.projections if p.median > 0)
    # §10.1: Final first, then the projection count decides Early vs Live.
    # The structural floor (§9.5) also degrades here: a site build must not crash
    # merely because the season is young.
    final = today > season.window_end + timedelta(days=1)
    forecastable = non_zero >= MIN_FILMS_FOR_TOP_TEN and (
        final or non_zero >= season.min_projections_for_forecast)
    reason = None
    if not forecastable:
        reason = (f"only {non_zero} films have non-zero projections "
                  f"({MIN_FILMS_FOR_TOP_TEN if final else season.min_projections_for_forecast}"
                  " required for a meaningful top-ten ranking)")

    # Date axis = every production refresh (box-office history), so a degraded
    # refresh shows as a gap in each line rather than vanishing (§12.4).
    refresh_dates = {d.isoformat() for obs in history.values() for d, _ in obs}
    if not local:
        refresh_dates.add(today.isoformat())  # this refresh persists after rendering

    for group in groups:
        group_out = out_dir / group.group_id
        sim = simulate(season, group, catalog) if forecastable else None
        current_points = {u: score_player(group.players[u], actual_top)
                          for u in group.players}
        ctx = base_context(season, group, "leaderboard", today)
        view = build_leaderboard_view(season, group, catalog, sim, current_points,
                                      actual_top, reason, today)
        render_leaderboard(env, group_out, ctx, view)
        render_whatif(env, group_out, {**ctx, "active": "whatif"},
                      build_whatif_data(season, group, catalog, sim) if sim else None,
                      reason)
        render_scenarios(env, group_out, {**ctx, "active": "scenarios"},
                         build_scenarios_view(group, sim) if sim else None, reason)
        forecast_path = season_dir / "forecast_history" / f"{group.group_id}.jsonl"
        if not local and sim is not None:
            # Appended before the history page renders so the page includes this refresh.
            forecast_path.parent.mkdir(exist_ok=True)
            append_forecast_history(forecast_path, sim, today)
        render_history(env, group_out, {**ctx, "active": "history"},
                       build_history_data(_load_forecast_rows(forecast_path), refresh_dates))
        render_rules(env, group_out, {**ctx, "active": "rules"})
        (group_out / "data.json").write_text(json.dumps(
            build_data_json(season, group, catalog, sim, current_points,
                            non_zero, reason, today),
            indent=2, sort_keys=True))

    if not local:
        # Roster-independent: appended once per season, never once per group.
        append_box_office_history(history_path, grosses, today)
```

(`refresh_dates` was previously recomputed inside the loop by re-reading the file; it is the same set because the box-office append happens after the loop.)

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/pytest -q` — Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add smw/render/build.py smw/render/page.py smw/render/templates/redirect.html.j2 tests/test_build.py tests/test_self_containment.py
git commit -m "feat: render every season and group to out/<year>/<group>/ with a root redirect"
```

---

### Task 3: Stylesheet, theme script, page skeleton, selectors, footer

**Files:**
- Modify: `.gitignore`; add `brainstorming/mockup.html` to git
- Rewrite: `smw/render/static/site.css`, `smw/render/static/theme.js`, `smw/render/templates/base.html.j2`
- Modify: `smw/render/page.py` (`Site`, `base_context`), `smw/render/build.py` (build `Site`)
- Test: `tests/test_site_css.py` (new), `tests/test_page.py`, `tests/test_build.py`

**Interfaces:**
- Produces: `Site(years: tuple[tuple[int, str], ...], groups: tuple[tuple[str, str], ...], forecast_note: str)` in `smw/render/page.py`; `base_context(season, group, active, today, site: Site | None = None)` returning keys `css theme_js nav active display_name year window_label window_and refreshed trials year_options group_options forecast_note`. `PAGES: dict[str, tuple[str, str]]` = active-key → (filename, page title).
- Template variables every page template may use: `title` (set by each `render_*`), the keys above.

- [ ] **Step 1: Un-ignore the mockup**

In `.gitignore` replace the line `brainstorming/` with:
```
brainstorming/*
!brainstorming/mockup.html
```
Then `git add brainstorming/mockup.html` and confirm `git status --short brainstorming` shows `A  brainstorming/mockup.html`.

- [ ] **Step 2: Write the CSS parity test** — create `tests/test_site_css.py`

```python
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
MARKER = "/* ---------- site additions ---------- */"
LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#a16207", "#be185d"]
DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#facc15", "#f472b6"]

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def _mockup_style() -> str:
    html = (ROOT / "brainstorming" / "mockup.html").read_text()
    style = html.split("<style>", 1)[1].split("</style>", 1)[0]
    style = re.sub(r"\.mocknote\{[^}]*\}", "", style)           # the mockup's own banner
    style = style.replace(".page{display:none}.page.active{display:block}", "")
    style = re.sub(r"--s-[a-z0-9_-]+:#[0-9a-fA-F]{3,6};", "", style)  # per-user tokens
    return style

def _site_css():
    css = (ROOT / "smw" / "render" / "static" / "site.css").read_text()
    assert css.count(MARKER) == 1
    verbatim, additions = css.split(MARKER)
    return verbatim, additions

def test_verbatim_block_equals_mockup_style():
    verbatim, _ = _site_css()
    assert _norm(verbatim) == _norm(_mockup_style())

def test_additions_hold_only_series_and_selector_rules():
    _, additions = _site_css()
    additions = re.sub(r"/\*.*?\*/", "", additions, flags=re.S)  # comments are not rules
    selectors = [s.strip() for s in re.findall(r"([^{}]+)\{", additions)]
    assert selectors
    for sel in selectors:
        assert (".series-" in sel or sel.startswith("@media")
                or sel in (".sel", ".vh")), sel

def test_series_colours_in_all_three_token_blocks():
    _, additions = _site_css()
    flat = _norm(additions)
    for i, (light, dark) in enumerate(zip(LIGHT, DARK)):
        assert f".series-{i}{{--series:{light}}}" in flat
        assert f':root[data-theme="dark"] .series-{i}{{--series:{dark}}}' in flat
        assert f':root:not([data-theme="light"]) .series-{i}{{--series:{dark}}}' in flat

def test_no_legacy_tokens_anywhere():
    css = (ROOT / "smw" / "render" / "static" / "site.css").read_text()
    for tok in ("--card", "--dim", "--pos", "--gold", ".num", ".table-scroll"):
        assert tok not in css, tok
```

- [ ] **Step 3: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_site_css.py -q` — Expected: FAIL (no marker).

- [ ] **Step 4: Write `site.css`**

```bash
python3 - <<'EOF'
import re
html = open("brainstorming/mockup.html").read()
style = html.split("<style>", 1)[1].split("</style>", 1)[0]
style = re.sub(r"\n\.mocknote\{[^}]*\}\n", "\n", style)
style = style.replace(".page{display:none}.page.active{display:block}\n", "")
style = re.sub(r"\n  --s-[^\n]*\n  --s-[^\n]*\n", "\n", style)   # two per token block
assert "--s-" not in style and ".mocknote" not in style and ".page" not in style
open("smw/render/static/site.css", "w").write(style.lstrip("\n"))
EOF
```
Then append the additions section **exactly**:
```css
/* ---------- site additions ---------- */
/* Series palette: bound to players ALPHABETICALLY, never by rank (rebuild §12.4).
   0–5 are the mockup's six colours in the mockup's order; 6–7 are the site's extras. */
.series-0{--series:#2a78d6} .series-1{--series:#eb6834} .series-2{--series:#1baf7a}
.series-3{--series:#eda100} .series-4{--series:#e87ba4} .series-5{--series:#008300}
.series-6{--series:#a16207} .series-7{--series:#be185d}
:root[data-theme="dark"] .series-0{--series:#3987e5}
:root[data-theme="dark"] .series-1{--series:#d95926}
:root[data-theme="dark"] .series-2{--series:#199e70}
:root[data-theme="dark"] .series-3{--series:#c98500}
:root[data-theme="dark"] .series-4{--series:#d55181}
:root[data-theme="dark"] .series-5{--series:#008300}
:root[data-theme="dark"] .series-6{--series:#facc15}
:root[data-theme="dark"] .series-7{--series:#f472b6}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]) .series-0{--series:#3987e5}
  :root:not([data-theme="light"]) .series-1{--series:#d95926}
  :root:not([data-theme="light"]) .series-2{--series:#199e70}
  :root:not([data-theme="light"]) .series-3{--series:#c98500}
  :root:not([data-theme="light"]) .series-4{--series:#d55181}
  :root:not([data-theme="light"]) .series-5{--series:#008300}
  :root:not([data-theme="light"]) .series-6{--series:#facc15}
  :root:not([data-theme="light"]) .series-7{--series:#f472b6}
}
/* Masthead selectors (spec §4): the #themeToggle recipe on a native <select>. */
.sel{background:var(--surface);border:1px solid var(--border);border-radius:999px;
  padding:4px 10px;color:var(--ink);font-size:.85rem;margin-left:6px;cursor:pointer}
.vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
```
Run: `.venv/bin/pytest tests/test_site_css.py -q` — Expected: PASS. If `test_verbatim_block_equals_mockup_style` fails, diff `_norm` outputs; the only legal fix is to the stripping script, never to the mockup text.

- [ ] **Step 5: Write `theme.js`**

```js
/* Theme resolution runs in the head, before body paint (spec §13.2). */
(function(){try{var t=localStorage.getItem('smw-theme');if(t)document.documentElement.setAttribute('data-theme',t);}catch(e){}})();
document.addEventListener("DOMContentLoaded",function(){
  var b=document.getElementById("themeToggle"); if(!b) return;
  b.addEventListener("click",function(){
    var cur=document.documentElement.getAttribute("data-theme")
      ||(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");
    var next=cur==="dark"?"light":"dark";
    document.documentElement.setAttribute("data-theme",next);
    try{localStorage.setItem("smw-theme",next);}catch(e){}
  });
});
```

- [ ] **Step 6: Write the failing context/skeleton tests** (append to `tests/test_page.py`)

```python
from smw.render.page import Site

def test_title_h1_selectors_and_footer(tmp_path, season, group):
    site = Site(years=((2027, "x"), (2026, "testers")),
                groups=(("aaa", "Zed League"), ("testers", "Test League")),
                forecast_note="Forecast: 2,000 seeded Monte Carlo seasons over 18 projected films.")
    env = make_env()
    ctx = base_context(season, group, "rules", TODAY, site)
    write_page(env, "rules.html.j2", tmp_path, "rules.html", {**ctx, "title": "Scoring rules"})
    html = (tmp_path / "rules.html").read_text()
    assert "<title>Scoring rules · Summer Movie Wager 2026 · Test League</title>" in html
    assert "<h1>🍿 Summer Movie Wager</h1>" in html
    assert "Wager window: May 1 – Sep 7, 2026" in html
    assert "Refreshed Aug 15, 2026" in html
    # year selector: newest first, current selected, target = that year's default group leaderboard
    assert html.index('value="../../2027/x/index.html"') < html.index('value="../../2026/testers/index.html" selected')
    # group selector: by display name, current selected, same page filename
    assert html.index('value="../testers/rules.html" selected') < html.index('value="../aaa/rules.html"')
    assert 'onchange="location.href=this.value"' in html
    assert "2,000 seeded Monte Carlo seasons over 18 projected films." in html
    assert 'id="themeToggle"' in html and "◐ Theme" in html
    assert 'class="pills"' in html and 'footer class="site"' in html

def test_single_option_selectors_still_render(tmp_path, season, group):
    html = _render_rules(tmp_path, season, group)   # site=None → one year, one group
    assert html.count("<select") == 2
    assert 'value="../../2026/testers/index.html" selected' in html
    assert 'value="../testers/rules.html" selected' in html
```

Run: `.venv/bin/pytest tests/test_page.py -q` — Expected: FAIL (`Site` import).

- [ ] **Step 7: Implement `Site` and the new `base_context`** in `smw/render/page.py`

Add `from dataclasses import dataclass` to imports. Replace `NAV` + `base_context` with:

```python
NAV = [
    ("index.html", "🏆 Leaderboard", "leaderboard"),
    ("whatif.html", "🎬 What If?", "whatif"),
    ("scenarios.html", "🔮 Winning Scenarios", "scenarios"),
    ("history.html", "📈 Odds Over Time", "history"),
]
PAGES = {  # active key → (filename, page title)
    "leaderboard": ("index.html", "Leaderboard"),
    "whatif": ("whatif.html", "What If?"),
    "scenarios": ("scenarios.html", "Winning Scenarios"),
    "history": ("history.html", "Odds Over Time"),
    "rules": ("rules.html", "Scoring rules"),
}


@dataclass(frozen=True)
class Site:
    """Cross-season / cross-group facts a page needs for its masthead (spec §4)."""
    years: tuple[tuple[int, str], ...]     # (year, default_group_id), newest first
    groups: tuple[tuple[str, str], ...]    # (group_id, display_name), by display_name
    forecast_note: str


def base_context(season: Season, group: Group, active: str, today: date,
                 site: Site | None = None) -> dict:
    if site is None:  # single-page renders (tests): one year, one group
        site = Site(((season.year, group.group_id),),
                    ((group.group_id, group.display_name),),
                    "Forecast: unavailable — no forecast.")
    filename = PAGES[active][0]
    return {
        # Repo-controlled build assets, inlined verbatim; everything external
        # still flows through autoescape.
        "css": Markup((STATIC / "site.css").read_text()),
        "theme_js": Markup((STATIC / "theme.js").read_text()),
        "nav": NAV,
        "active": active,
        "display_name": group.display_name,
        "year": season.year,
        "window_label": (
            f"{season.window_start.strftime('%b %-d')} – "
            f"{season.window_end.strftime('%b %-d, %Y')}"
        ),
        "window_and": (
            f"{season.window_start.strftime('%b %-d')} and "
            f"{season.window_end.strftime('%b %-d, %Y')}"
        ),
        "refreshed": today.strftime("%b %-d, %Y"),
        "trials": f"{season.monte_carlo_trials:,}",
        "year_options": [
            {"value": f"../../{y}/{g}/index.html", "label": str(y), "selected": y == season.year}
            for y, g in site.years],
        "group_options": [
            {"value": f"../{gid}/{filename}", "label": name, "selected": gid == group.group_id}
            for gid, name in site.groups],
        "forecast_note": site.forecast_note,
    }
```
Delete the `wide_shell` key usage in `render_leaderboard` (`"wide_shell": True`).

- [ ] **Step 8: Write `base.html.j2`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} · Summer Movie Wager {{ year }} · {{ display_name }}</title>
<script>{{ theme_js }}</script>
<style>{{ css }}</style>
</head>
<body>
<div class="wrap">

<header class="site">
  <div>
    <h1>🍿 Summer Movie Wager</h1>
    <div class="sub">Wager window: {{ window_label }} &nbsp;·&nbsp; <span class="small">Refreshed {{ refreshed }}</span>
      <label class="vh" for="yearSelect">Season</label>
      <select id="yearSelect" class="sel" onchange="location.href=this.value">
        {%- for o in year_options %}<option value="{{ o.value }}"{% if o.selected %} selected{% endif %}>{{ o.label }}</option>{% endfor -%}
      </select>
      <label class="vh" for="groupSelect">Group</label>
      <select id="groupSelect" class="sel" onchange="location.href=this.value">
        {%- for o in group_options %}<option value="{{ o.value }}"{% if o.selected %} selected{% endif %}>{{ o.label }}</option>{% endfor -%}
      </select>
    </div>
  </div>
  <button id="themeToggle" type="button" aria-label="Toggle color theme">◐ Theme</button>
</header>

<nav class="pills" aria-label="Site">
  {% for href, label, key in nav -%}
  <a href="{{ href }}"{% if key == active %} aria-current="page"{% endif %}>{{ label }}</a>
  {% endfor -%}
</nav>

{% block content %}{% endblock %}

<footer class="site">
  Raw numbers: <a href="data.json">data.json</a> &nbsp;·&nbsp;
  <a href="rules.html">Scoring rules</a> &nbsp;·&nbsp;
  <span class="small">{{ forecast_note }}</span>
</footer>

</div>
</body>
</html>
```

- [ ] **Step 9: Build the `Site` in `_build_season`** (`smw/render/build.py`)

Add `Site` to the `smw.render.page` import. `run_build` computes once, before the season loop:
```python
    years = tuple((s.year, s.default_group) for s, _ in sorted(loaded, key=lambda x: -x[0].year))
```
and passes `years` into `_build_season(env, season_dir, out_dir / str(season.year), season, groups, years, today, local)` — add `years: tuple[tuple[int, str], ...]` as the parameter after `groups`. Inside `_build_season`, after `reason` is computed:
```python
    site = Site(
        years=years,
        groups=tuple((g.group_id, g.display_name)
                     for g in sorted(groups, key=lambda g: (g.display_name, g.group_id))),
        forecast_note=(f"Forecast: {season.monte_carlo_trials:,} seeded Monte Carlo seasons "
                       f"over {non_zero} projected films." if forecastable
                       else f"Forecast: unavailable — {reason}."),
    )
```
Replace the per-group `ctx = base_context(season, group, "leaderboard", today)` and the `{**ctx, "active": …}` overrides with one `base_context` call per page (group option hrefs depend on the page filename):
```python
        ctx = lambda page: base_context(season, group, page, today, site)  # noqa: E731
        render_leaderboard(env, group_out, ctx("leaderboard"), view)
        render_whatif(env, group_out, ctx("whatif"), …)
        render_scenarios(env, group_out, ctx("scenarios"), …)
        render_history(env, group_out, ctx("history"), …)
        render_rules(env, group_out, ctx("rules"))
```

- [ ] **Step 10: Build-level selector test** (append to `tests/test_build.py`)

```python
def test_pages_carry_selectors_and_footer_note(data_dir, tmp_path):
    _add_group(data_dir, "h", "Alpha League")
    out = _run(data_dir, tmp_path)
    for page in ("index.html", "whatif.html", "scenarios.html", "history.html", "rules.html"):
        html = (out / page).read_text()
        assert 'value="../../2026/g/index.html" selected' in html, page
        assert f'value="../h/{page}"' in html and f'value="../g/{page}" selected' in html, page
        assert "Forecast: unavailable — only 3 films" in html, page
    assert "<title>Leaderboard · Summer Movie Wager 2026 · G</title>" in (out / "index.html").read_text()
```

- [ ] **Step 11: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: everything passes **except** `tests/test_leaderboard_render.py::test_leaderboard_snapshot` (the header changed; the snapshot is regenerated in Task 4 after the leaderboard template lands — do not regenerate it here).

- [ ] **Step 12: Commit**

```bash
git add .gitignore brainstorming/mockup.html smw/render/static/site.css smw/render/static/theme.js smw/render/templates/base.html.j2 smw/render/page.py smw/render/build.py tests/test_site_css.py tests/test_page.py tests/test_build.py
git commit -m "feat: mockup stylesheet and skeleton, masthead year/group selectors, build footer"
```

---

### Task 4: Leaderboard to mockup + snapshot

**Files:**
- Rewrite: `smw/render/templates/index.html.j2`
- Modify: `smw/render/views.py` (`_list_rows`, `_details` stats, `FilmRow.released`), `smw/render/page.py` (`fmt_money`)
- Regenerate: `tests/fixtures/snapshot_index.html`
- Test: `tests/test_page.py`, `tests/test_leaderboard_render.py`, `tests/test_views.py`

**Interfaces:**
- Consumes: `LeaderboardView` (unchanged field names), `base_context` keys from T3.
- Produces: `fmt_money(x) -> str` = `$498.0M` / `$1.02B`; `FilmRow.released` = `Jun 19`; `list_rows` labels `Pick n` / `🐴 n`; `PlayerDetail.stats_line` starts with `— `.

- [ ] **Step 1: Failing tests**

`tests/test_page.py` — replace `test_fmt_money`:
```python
def test_fmt_money_matches_mockup():
    assert fmt_money(1_020_000_000) == "$1.02B"
    assert fmt_money(498_000_000) == "$498.0M"
    assert fmt_money(310_491_022) == "$310.5M"
    assert fmt_money(468_000) == "$0.5M"
```
`tests/test_views.py` — append:
```python
def test_list_rows_and_stats_copy_match_mockup(season, group):
    v = _view(season, group)
    assert v.list_rows[0][0] == "Pick 1" and v.list_rows[10][0] == "🐴 1"
    d = v.details[0]
    assert d.stats_line.startswith("— ") and " pts projected · " in d.stats_line
    assert d.stats_line.endswith("% win")
    assert v.films[0].released == "May 1"
```
`tests/test_leaderboard_render.py` — append:
```python
def test_leaderboard_structure_matches_mockup(tmp_path, season, group):
    html = _render(tmp_path, season, group)
    for s in ("<h2>🏆 Projected Standings</h2>", "<h2>📋 All Players' Lists</h2>",
              "<h2>👤 Per-Player Detail</h2>", "<h2>🎞️ Films</h2>",
              'id="matrix"', 'id="lists"', "Rows: top 15 films by projected median",
              "Show all tracked films", "projections, ranges, provenance",
              '<tr class="odds">', '<tr class="divider">', 'class="scroller" style="border:none"',
              '<th class="t">Slot</th>', "Dark horses", '<th class="t">Movie</th>'):
        assert s in html, s
    for gone in (".num", "table-scroll", "cell-pos", "divider-row", "stats-line"):
        assert gone not in html.split("</style>")[1], gone
```

Run: `.venv/bin/pytest tests/test_page.py tests/test_views.py tests/test_leaderboard_render.py -q` — Expected: FAIL.

- [ ] **Step 2: `fmt_money`** in `smw/render/page.py`

```python
def fmt_money(x: float) -> str:
    """Mockup formats: $498.0M, $1.02B."""
    x = float(x)
    if x >= 1e9:
        return f"${x / 1e9:.2f}B"
    return f"${x / 1e6:.1f}M"
```

- [ ] **Step 3: `views.py` changes**

`_list_rows`: label `f"🐴 {i + 1}"` instead of `f"🐴 Dark Horse {i + 1}"`.

`_details` stats:
```python
        if mode == "live":
            stats = (f"— {footer[u]} pts projected · {current_points.get(u, 0)} current"
                     f" · {sim.win_prob[u] * 100:.1f}% win")
        else:
            stats = f"— {current_points.get(u, 0)} pts current"
```
`_film_rows`: `f.release_date.strftime("%b %-d")` instead of `.isoformat()`.

- [ ] **Step 4: Rewrite `index.html.j2`**

```html
{% extends "base.html.j2" %}
{% block content %}
{% if view.notice %}<div class="caption">{{ view.notice }}</div>{% endif %}

<h2>{{ view.heading }}</h2>
<div class="scroller"><table id="matrix">
<thead><tr><th>#</th><th class="t">Movie</th>
  <th>{% if view.mode == "live" %}Projected (in-window){% else %}Gross to date{% endif %}</th>
  {%- for col in view.columns %}<th>{{ col.username }}</th>{% endfor %}</tr></thead>
<tbody>
{% for row in view.rows -%}
<tr><td>{{ row.rank }}</td><td class="t">{{ row.title }}</td><td>{{ row.gross | money }}</td>
  {%- for cell in row.cells %}
  {%- if cell.kind == "pts" %}<td class="pos">{{ cell.pts }}</td>
  {%- elif cell.kind == "zero" %}<td class="zero">0</td>
  {%- else %}<td class="dash">—</td>{% endif %}
  {%- endfor %}</tr>
{% if view.divider_after and loop.index == view.divider_after -%}
<tr class="divider"><td colspan="{{ 3 + view.columns | length }}">Outside the top 10</td></tr>
{% endif -%}
{% endfor -%}
</tbody>
<tfoot>
<tr><td colspan="3" class="t">{% if view.mode == "live" %}Projected pts{% else %}Current pts{% endif %}</td>
  {%- for col in view.columns %}<td>{{ col.footer_pts }}</td>{% endfor %}</tr>
{% if view.mode == "live" -%}
<tr class="odds"><td colspan="3" class="t">Win odds</td>
  {%- for col in view.columns %}<td>{{ col.win_pct }}%</td>{% endfor %}</tr>
{% endif -%}
</tfoot>
</table></div>
<p class="small">Rows: top {{ view.rows | length }} films by projected median in-window gross. Cells are each film's
projected points for that player; grey 0 = on their roster but outside the projected top ten,
— = not picked. Columns are ordered by simulated median points.</p>

<h2>📋 All Players' Lists</h2>
<div class="scroller"><table id="lists">
<thead><tr><th class="t">Slot</th>{% for col in view.columns %}<th class="t">{{ col.username }}</th>{% endfor %}</tr></thead>
<tbody>
{% for label, picks in view.list_rows -%}
{% if loop.index == 11 %}<tr class="divider"><td colspan="{{ 1 + view.columns | length }}">Dark horses</td></tr>
{% endif -%}
<tr><td class="t">{{ label }}</td>{% for col in view.columns %}<td class="t">{{ picks[col.username] }}</td>{% endfor %}</tr>
{% endfor -%}
</tbody>
</table></div>

<h2>👤 Per-Player Detail</h2>
{% for d in view.details -%}
<details class="acc"><summary>{{ d.username }} <span class="stats">{{ d.stats_line }}</span></summary>
<div class="scroller" style="border:none"><table>
{% if view.mode == "live" -%}
<thead><tr><th>#</th><th class="t">Movie</th><th>Projected rank</th><th>Diff</th><th>Projected gross</th><th>Pts</th></tr></thead>
{% else -%}
<thead><tr><th>#</th><th class="t">Movie</th><th>Pts</th></tr></thead>
{% endif -%}
<tbody>
{% for row in d.rows + [none] + d.dark_rows -%}
{% if row is none -%}
<tr class="divider"><td colspan="{% if view.mode == "live" %}6{% else %}3{% endif %}">Dark horses</td></tr>
{% else -%}
<tr><td>{{ row.label }}</td><td class="t">{{ row.title }}</td>
  {%- if view.mode == "live" %}
  <td>{% if row.projected_rank %}#{{ row.projected_rank }}{% else %}<span class="dash">—</span>{% endif %}</td>
  <td>{% if row.diff is none %}<span class="dash">—</span>{% elif row.diff > 0 %}<span class="up">▲ {{ row.diff }}</span>{% elif row.diff < 0 %}<span class="down">▼ {{ -row.diff }}</span>{% else %}<span class="dash">–</span>{% endif %}</td>
  <td>{% if row.gross %}{{ row.gross | money }}{% else %}<span class="dash">—</span> <span class="badge">no projection</span>{% endif %}</td>
  {%- endif %}
  {% if row.pts > 0 %}<td class="pos">{{ row.pts }}</td>{% else %}<td class="zero">0</td>{% endif %}</tr>
{% endif -%}
{% endfor -%}
</tbody>
</table></div>
</details>
{% endfor %}

<h2>🎞️ Films</h2>
<details class="acc"><summary>Show all tracked films <span class="stats">({{ view.films | length }} films · projections, ranges, provenance)</span></summary>
<div class="scroller" style="border:none"><table>
<thead><tr><th>#</th><th class="t">Movie</th><th>Released</th><th class="t">Status</th>
<th>Projected median (in-window)</th><th>80% range</th><th>Cumulative</th><th class="t">Source</th></tr></thead>
<tbody>
{% for f in view.films -%}
<tr><td>{% if f.rank %}{{ f.rank }}{% else %}<span class="dash">—</span>{% endif %}</td>
  <td class="t">{{ f.title }}</td><td>{{ f.released }}</td>
  <td class="t"><span class="badge">{{ f.badge }}</span></td>
  <td>{% if f.median > 0 %}{{ f.median | money }}{% else %}<span class="dash">—</span>{% endif %}</td>
  <td>{% if f.median <= 0 %}—{% elif f.p10 == f.p90 %}{{ f.p10 | money }} (final){% else %}{{ f.p10 | money }} – {{ f.p90 | money }}{% endif %}</td>
  <td>{% if f.cumulative > 0 %}{{ f.cumulative | money }}{% else %}<span class="dash">—</span>{% endif %}</td>
  <td class="t small">{{ f.source }}</td></tr>
{% endfor -%}
</tbody>
</table></div>
</details>
{% endblock %}
```
(The current-points `notice` uses the mockup's `.caption` box — the only mockup class for a bordered note.)

- [ ] **Step 5: Run the targeted tests**

Run: `.venv/bin/pytest tests/test_page.py tests/test_views.py tests/test_leaderboard_render.py -q`
Expected: all pass except `test_leaderboard_snapshot`.

- [ ] **Step 6: Snapshot ritual (spec §3.9 — required human inspection)**

```bash
rm tests/fixtures/snapshot_index.html
.venv/bin/pytest tests/test_leaderboard_render.py::test_leaderboard_snapshot -q   # writes fixture, FAILS once
open tests/fixtures/snapshot_index.html
```
Compare against the mockup's Leaderboard section (`open brainstorming/mockup.html`): card-bordered tables, right-aligned numbers, `Outside the top 10` dashed divider, `Win odds` row, emoji headings, accordion summaries with grey stats. Only then:
```bash
.venv/bin/pytest -q
```
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add smw/render/templates/index.html.j2 smw/render/views.py smw/render/page.py tests/fixtures/snapshot_index.html tests/test_page.py tests/test_views.py tests/test_leaderboard_render.py
git commit -m "feat: leaderboard rendered to the mockup; snapshot regenerated and inspected"
```

---

### Task 5: What If? with vendored SortableJS

**Files:**
- Create: `smw/render/static/sortable.min.js`
- Rewrite: `smw/render/static/whatif.js`, `smw/render/templates/whatif.html.j2`
- Modify: `smw/render/page.py` (`render_whatif` inlines `sortable_js`)
- Test: `tests/test_whatif_render.py`

**Interfaces:**
- Consumes: `window.WHATIF = {films, players:[{name, ranked, dark}], baseline}` (unchanged, `build_whatif_data`); `scoring.js` globals `scorePlayer`, `pointsFor`.
- Produces: `whatif.html` with `ol.wi-list#wiList`, `table#wiStandings`, `button#wiReset`, `table#wiGrid`, and `new Sortable(`.

- [ ] **Step 1: Vendor the library**

```bash
curl -sL https://unpkg.com/sortablejs@1.15.6/Sortable.min.js -o smw/render/static/sortable.min.js
head -1 smw/render/static/sortable.min.js      # /*! Sortable 1.15.6 - MIT | git://github.com/SortableJS/Sortable.git */
sed -i '' '1s#.*#/*! Sortable 1.15.6 - MIT */#' smw/render/static/sortable.min.js
grep -c "://" smw/render/static/sortable.min.js        # must print 0
grep -c "</script" smw/render/static/sortable.min.js   # must print 0
grep -c "Sortable 1.15.6" smw/render/static/sortable.min.js  # 1
```
The file is ~45 KB; that is the budget the spec accepts.

- [ ] **Step 2: Failing tests** — replace `tests/test_whatif_render.py` body after `_render` with:

```python
STATIC = Path(__file__).parent.parent / "smw" / "render" / "static"

def test_locked_state_notice(tmp_path, season, group):
    html = _render(tmp_path, season, group, locked=True)
    assert "unlocks once the forecast is live" in html
    assert "only 3 films" in html
    assert 'id="wiList"' not in html and "new Sortable(" not in html

def test_embedded_data_and_scripts(tmp_path, season, group):
    html = _render(tmp_path, season, group)
    assert "window.WHATIF" in html
    assert "rankedPickPoints" in html   # scoring.js inlined
    assert "new Sortable(" in html and "Sortable 1.15.6 - MIT" in html
    assert 'aria-live="polite"' in html
    for s in ("<h2>🎬 What If? sandbox</h2>", "player's score recompute",
              "If it ends this way…", "↺ Reset to projected order",
              "Films outside the projected top 15 can't be dragged in and score 0.",
              "<h2>Points by film, for this order</h2>", 'id="wiStandings"', 'id="wiGrid"',
              '<th>Place</th><th class="t">Player</th><th>Pts</th><th>vs proj.</th>'):
        assert s in html, s

def test_site_drag_code_is_gone():
    js = (STATIC / "whatif.js").read_text()
    for s in ("dragstart", "dragover", "touchstart", "elementFromPoint", "draggable"):
        assert s not in js, s
    assert "new Sortable(" in js and "ghostClass" in js and "delayOnTouchOnly" in js

def test_vendored_library_is_minified_1_15_6_without_urls():
    lib = (STATIC / "sortable.min.js").read_text()
    assert lib.startswith("/*! Sortable 1.15.6 - MIT */")
    assert "://" not in lib and "</script" not in lib
    assert lib.count("\n") < 5   # minified

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
Add `from pathlib import Path` at the top. Run: `.venv/bin/pytest tests/test_whatif_render.py -q` — Expected: FAIL.

- [ ] **Step 3: `render_whatif`** in `smw/render/page.py` — add `"sortable_js": Markup((STATIC / "sortable.min.js").read_text()),` to the context dict.

- [ ] **Step 4: `whatif.html.j2`**

```html
{% extends "base.html.j2" %}
{% block content %}
{% if data is none %}
<div class="locked">Not enough films have projections yet to simulate win
probabilities — {{ reason }}. This view unlocks once the forecast is live.</div>
{% else %}
<h2>🎬 What If? sandbox</h2>
<p class="sub">Drag the films into any finish order — or use the ▲▼ buttons — and watch every
player's score recompute.</p>
<div class="wi">
  <div>
    <ol class="wi-list" id="wiList"></ol>
    <p class="small">Films outside the projected top {{ data.films | length }} can't be dragged in and score 0.</p>
  </div>
  <div class="wi-panel">
    <h3>If it ends this way…</h3>
    <div aria-live="polite"><table id="wiStandings">
      <thead><tr><th>Place</th><th class="t">Player</th><th>Pts</th><th>vs proj.</th></tr></thead>
      <tbody></tbody>
    </table></div>
    <button id="wiReset" type="button">↺ Reset to projected order</button>
  </div>
</div>
<h2>Points by film, for this order</h2>
<div class="scroller"><table id="wiGrid"><thead><tr></tr></thead><tbody></tbody></table></div>
<script>window.WHATIF = {{ data | json_embed }};</script>
<script>{{ sortable_js }}</script>
<script>{{ scoring_js }}</script>
<script>{{ whatif_js }}</script>
{% endif %}
{% endblock %}
```

- [ ] **Step 5: `whatif.js`**

```js
"use strict";
(function () {
  var D = window.WHATIF;
  var list = document.getElementById("wiList");

  function order() {
    return Array.prototype.map.call(list.children, function (li) { return li.dataset.title; });
  }
  function cell(tr, text, cls) {
    var td = document.createElement("td");
    if (cls) td.className = cls;
    td.textContent = text;
    tr.appendChild(td);
  }
  function th(tr, text, cls) {
    var el = document.createElement("th");
    if (cls) el.className = cls;
    el.textContent = text;
    tr.appendChild(el);
  }
  function item(title) {
    var li = document.createElement("li");
    li.dataset.title = title;
    var film = document.createElement("span");
    film.className = "film";
    film.textContent = title;
    li.appendChild(film);
    var mv = document.createElement("span");
    mv.className = "mv";
    [["▲", -1], ["▼", 1]].forEach(function (pair) {
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = pair[0];
      b.setAttribute("aria-label",
        "Move " + title + (pair[1] < 0 ? " up" : " down") + " one slot");
      b.addEventListener("click", function () {
        var sib = pair[1] < 0 ? li.previousElementSibling : li.nextElementSibling;
        if (!sib) return;
        list.insertBefore(li, pair[1] < 0 ? sib : sib.nextElementSibling);
        rescore();
        b.focus();  // the <li> moved, not rebuilt: repeated presses keep walking the film
      });
      mv.appendChild(b);
    });
    li.appendChild(mv);
    return li;
  }
  function fill() {
    list.innerHTML = "";
    D.films.forEach(function (t) { list.appendChild(item(t)); });
    rescore();
  }

  function rescore() {
    var ord = order(), finish = ord.slice(0, 10);
    Array.prototype.forEach.call(list.children, function (li, i) {
      var bs = li.querySelectorAll("button");
      bs[0].disabled = i === 0;
      bs[1].disabled = i === ord.length - 1;
    });
    var rows = D.players.map(function (p) {
      return { name: p.name, pts: scorePlayer(p.ranked, p.dark, finish),
               base: D.baseline[p.name], picks: p };
    });
    rows.sort(function (a, b) { return b.pts - a.pts || (a.name < b.name ? -1 : 1); });

    var tbody = document.querySelector("#wiStandings tbody");
    tbody.innerHTML = "";
    var place = 0, prev = null;
    rows.forEach(function (r, i) {
      if (r.pts !== prev) { place = i + 1; prev = r.pts; }  // competition ranking 1,1,3
      var tr = document.createElement("tr");
      var d = r.pts - r.base;
      cell(tr, place);
      cell(tr, r.name, place === 1 ? "t crown" : "t");
      cell(tr, r.pts, "pos");
      cell(tr, d === 0 ? "–" : d > 0 ? "▲" + d : "▼" + (-d),
           d === 0 ? "dash" : d > 0 ? "up" : "down");
      tbody.appendChild(tr);
    });

    var head = document.querySelector("#wiGrid thead tr");
    head.innerHTML = "";
    th(head, "#"); th(head, "Movie", "t");
    rows.forEach(function (r) { th(head, r.name); });
    var grid = document.querySelector("#wiGrid tbody");
    grid.innerHTML = "";
    ord.forEach(function (title, i) {
      var tr = document.createElement("tr");
      cell(tr, i + 1); cell(tr, title, "t");
      rows.forEach(function (r) {
        var pts = pointsFor(r.picks.ranked, r.picks.dark, title, finish);
        cell(tr, pts === null ? "—" : pts, pts === null ? "dash" : pts > 0 ? "pos" : "zero");
      });
      grid.appendChild(tr);
      if (i === 9) {
        var div = document.createElement("tr");
        div.className = "divider";
        var td = document.createElement("td");
        td.colSpan = 2 + rows.length;
        td.textContent = "Outside the top 10";
        div.appendChild(td);
        grid.appendChild(div);
      }
    });
  }

  document.getElementById("wiReset").addEventListener("click", fill);
  fill();
  new Sortable(list, {
    animation: 150,                       // rows slide out of the way during the drag
    ghostClass: "dragging",               // the mockup's class: 40% opacity
    delay: 150, delayOnTouchOnly: true,   // press-and-hold on touch so the page still scrolls
    touchStartThreshold: 4,
    filter: ".mv button", preventOnFilter: false,   // ▲ ▼ still click
    onEnd: rescore                        // Sortable moved the <li>; just read the DOM order
  });
})();
```

- [ ] **Step 6: Run tests**

Run: `.venv/bin/pytest tests/test_whatif_render.py tests/test_cross_impl.py tests/test_self_containment.py -q` — Expected: PASS.

- [ ] **Step 7: Manual drag check** (behaviour the suite cannot see)

```bash
.venv/bin/python -m smw --local --date 2026-08-27 --out /tmp/smw-check && open /tmp/smw-check/2026/smw-friends/whatif.html
```
Drag a row: other rows must slide before release; standings recompute on drop; ▲▼ walk the film with focus kept; Reset restores. If the build needs the network and it is unavailable, use `.venv/bin/pytest tests/test_whatif_render.py -q` output dir instead: run `_render` from a Python shell into a temp dir.

- [ ] **Step 8: Commit**

```bash
git add smw/render/static/sortable.min.js smw/render/static/whatif.js smw/render/templates/whatif.html.j2 smw/render/page.py tests/test_whatif_render.py
git commit -m "feat: What If? reordering via vendored SortableJS 1.15.6, mockup markup"
```

---

### Task 6: Winning Scenarios to mockup

**Files:**
- Rewrite: `smw/render/templates/scenarios.html.j2`, `smw/render/static/scenarios.js`
- Test: `tests/test_scenarios_render.py`

**Interfaces:**
- Consumes: `build_scenarios_view` tabs (unchanged shape); `trials` from `base_context`.

- [ ] **Step 1: Failing tests** (append to `tests/test_scenarios_render.py`)

```python
def test_markup_matches_mockup(tmp_path, season, group, sim):
    html = _render(tmp_path, season, group, build_scenarios_view(group, sim))
    for s in ("<h2>🔮 Winning Scenarios</h2>", '<div class="tabs">', '<div class="caption">',
              '<div class="scroller"><table>', '<th class="hlcol">', 'class="t">Total</td>',
              " crown", '<th>#</th><th class="t">Movie</th>'):
        assert s in html, s
    body = html.split("</style>")[1]
    for gone in ("tab-row", 'class="tab"', "highlight-col", "cell-none", "cell-pos", "stats-line"):
        assert gone not in body, gone

def test_disabled_tab_title_names_trials(tmp_path, season, group):
    tabs = [{"username": "bob", "win_pct": 0.0, "scenario": None}]
    html = _render(tmp_path, season, group, tabs)
    assert 'disabled title="No winning path — bob wins in 0 of 2,000 simulated seasons"' in html
    assert "bob · 0.0%" in html
```
Also in `test_zero_cells_render_middle_dot_and_no_path_disabled` change `assert "·" in html` to `assert '<td class="mid">·</td>' in html`.

Run: `.venv/bin/pytest tests/test_scenarios_render.py -q` — Expected: FAIL.

- [ ] **Step 2: `scenarios.html.j2`**

```html
{% extends "base.html.j2" %}
{% block content %}
{% if tabs is none %}
<div class="locked">Not enough films have projections yet to simulate win
probabilities — {{ reason }}. This view unlocks once the forecast is live.</div>
{% else %}
<h2>🔮 Winning Scenarios</h2>
<p class="sub">Pick a player to see the single most-likely top-10 box-office finish order that
crowns them champion — and exactly how everyone's predictions score against it. Grayed-out
players have no realistic path to winning.</p>
<div class="tabs">
{% for t in tabs -%}
{% if t.scenario -%}
<button type="button" data-tab="{{ loop.index0 }}" aria-pressed="{{ 'true' if loop.first else 'false' }}">{{ t.username }} · {{ t.win_pct }}%</button>
{% else -%}
<button type="button" disabled title="No winning path — {{ t.username }} wins in 0 of {{ trials }} simulated seasons">{{ t.username }} · 0.0%</button>
{% endif -%}
{% endfor -%}
</div>
{% for t in tabs %}{% if t.scenario -%}
<section data-panel="{{ loop.index0 }}"{% if not loop.first %} hidden{% endif %}>
<div class="caption">{{ t.scenario.caption }}</div>
<div class="scroller"><table>
<thead><tr><th>#</th><th class="t">Movie</th>
{%- for u in t.scenario.columns %}<th{% if u == t.username %} class="hlcol"{% endif %}>{{ u }}</th>{% endfor %}</tr></thead>
<tbody>
{% for row in t.scenario.rows -%}
<tr><td>{{ loop.index }}</td><td class="t">{{ row.title }}</td>
{%- for c in row.cells %}
{%- set hl = t.scenario.columns[loop.index0] == t.username %}
{%- if c > 0 %}<td class="pos{% if hl %} hlcol{% endif %}">{{ c }}</td>{% else %}<td class="mid{% if hl %} hlcol{% endif %}">·</td>{% endif %}
{%- endfor %}</tr>
{% endfor -%}
</tbody>
<tfoot><tr><td colspan="2" class="t">Total</td>
{%- for total in t.scenario.totals %}<td class="{% if t.scenario.columns[loop.index0] == t.username %}hlcol{% endif %}{% if loop.first %} crown{% endif %}">{{ total }}</td>{% endfor %}</tr></tfoot>
</table></div>
</section>
{% endif %}{% endfor -%}
<script>{{ scenarios_js }}</script>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: `scenarios.js`**

```js
"use strict";
(function () {
  var buttons = document.querySelectorAll(".tabs button[data-tab]");
  buttons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      buttons.forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
      btn.setAttribute("aria-pressed", "true");
      document.querySelectorAll("section[data-panel]").forEach(function (p) {
        p.hidden = p.dataset.panel !== btn.dataset.tab;
      });
    });
  });
})();
```

- [ ] **Step 4: Run tests, commit**

Run: `.venv/bin/pytest tests/test_scenarios_render.py tests/test_scenarios.py -q` — Expected: PASS.
```bash
git add smw/render/templates/scenarios.html.j2 smw/render/static/scenarios.js tests/test_scenarios_render.py
git commit -m "feat: Winning Scenarios rendered to the mockup"
```

---

### Task 7: Odds Over Time — mockup chart geometry, legend, crosshair

**Files:**
- Rewrite: `smw/render/chart.py` (`render_chart_svg` + constants), `smw/render/templates/history.html.j2`, `smw/render/static/history.js`
- Modify: `smw/render/page.py` (`render_history` legend order)
- Test: `tests/test_chart.py`, `tests/test_build.py` (two assertions)

**Interfaces:**
- Consumes: `build_history_data` (unchanged: `{dates, series:[{name, color, values}]}`).
- Produces: `render_chart_svg(data) -> str` — `viewBox="0 0 920 360"`, constants `W=920 H=360 ML=52 MR=110 MT=16 MB=34 LABEL_MIN_GAP=15`; paths `<path class="series-N" d=… stroke="var(--series)">`; markers `<circle class="series-N" … r="3" fill="var(--series)">`; x labels `<text … text-anchor="middle">`; direct labels `<rect class="series-N" … width="10" height="10" rx="3">` + `<text class="dl" …>`; a hidden `<line class="xh" …>` for the crosshair.

- [ ] **Step 1: Update failing tests**

`tests/test_chart.py`:
- `test_gap_breaks_svg_path`: regex → `r'<path class="series-0" d="([^"]+)"'`.
- `test_x_labels_thinned_to_eight_max_including_latest`: `labels = svg.count('text-anchor="middle"')`.
- `test_direct_labels_stay_inside_viewbox`: regex → `r'class="dl" x="[\d.]+" y="([\d.]+)"'`.
- Append:
```python
def test_mockup_geometry_and_elements():
    svg = render_chart_svg(build_history_data(ROWS))
    assert svg.startswith('<svg viewBox="0 0 920 360" width="100%" role="img" aria-label="Line chart of win probability by refresh date for 2 players">')
    assert 'stroke="var(--baseline)"' in svg           # 0% baseline
    assert 'stroke="var(--grid)"' in svg               # gridlines
    assert svg.count('r="3"') == 7                     # one marker per value (8 rows, 1 superseded)
    assert 'width="10" height="10" rx="3"' in svg      # direct-label swatch
    assert 'class="dl"' in svg and ">alice</text>" in svg
    assert '<line class="xh"' in svg and 'display:none' in svg
    assert 'class="x-label"' not in svg and 'class="direct-label"' not in svg
```
`tests/test_build.py` in `test_degraded_production_refresh_shows_as_history_gap`: `'class="x-label"' in svg` → `'text-anchor="middle"' in svg`; `"<td>2026-08-15</td>" in html` → `'<td class="t">2026-08-15</td>' in html`.

Run: `.venv/bin/pytest tests/test_chart.py -q` — Expected: FAIL.

- [ ] **Step 2: Rewrite `chart.py` constants and `render_chart_svg`**

```python
W, H = 920, 360
ML, MR, MT, MB = 52, 110, 16, 34  # right margin leaves room for direct labels
MAX_X_LABELS = 8
DIRECT_LABELS = 4
LABEL_MIN_GAP = 15
```
`build_history_data`, `_x`, `_y` unchanged. New `render_chart_svg`:
```python
def render_chart_svg(data: dict) -> str:
    dates, series = data["dates"], data["series"]
    n = len(dates)
    vmax = max((v for s in series for v in s["values"] if v is not None), default=0.0)
    ymax = max(0.1, math.floor(vmax * 10 + 1) / 10)  # next decile above the max
    ymax = min(ymax, 1.0)
    iw = W - ML - MR

    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" '
             f'aria-label="Line chart of win probability by refresh date for '
             f'{len(series)} players">']
    tick = 0.0
    while tick <= ymax + 1e-9:  # gridlines every 10%
        y = _y(tick, ymax)
        parts.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{ML + iw}" y2="{y:.1f}" '
                     'stroke="var(--grid)"/>')
        parts.append(f'<text x="{ML - 8}" y="{y + 4:.1f}" text-anchor="end">'
                     f'{round(tick * 100)}%</text>')
        tick += 0.1
    # x labels thinned to <= 8, walking back from the most recent (mockup)
    step = max(1, math.ceil(n / MAX_X_LABELS))
    for i in sorted(range(n - 1, -1, -step)):
        parts.append(f'<text x="{_x(i, n):.1f}" y="{H - 10}" text-anchor="middle">'
                     f'{escape(str(dates[i]))}</text>')
    y0 = _y(0.0, ymax)
    parts.append(f'<line x1="{ML}" y1="{y0:.1f}" x2="{ML + iw}" y2="{y0:.1f}" '
                 'stroke="var(--baseline)"/>')
    # one path per series; a None breaks the line (§12.4 — a gap means no forecast
    # was produced; drawing through it would assert a number never computed)
    for s in series:
        d_cmds, pen_down = [], False
        for i, v in enumerate(s["values"]):
            if v is None:
                pen_down = False
                continue
            d_cmds.append(f'{"L" if pen_down else "M"}{_x(i, n):.1f} {_y(v, ymax):.1f}')
            pen_down = True
        parts.append(f'<path class="series-{s["color"]}" d="{" ".join(d_cmds)}" fill="none" '
                     'stroke="var(--series)" stroke-width="2" stroke-linejoin="round" '
                     'stroke-linecap="round"/>')
        for i, v in enumerate(s["values"]):
            if v is not None:
                parts.append(f'<circle class="series-{s["color"]}" cx="{_x(i, n):.1f}" '
                             f'cy="{_y(v, ymax):.1f}" r="3" fill="var(--series)"/>')
    # direct labels: top four by latest value, nudged apart; ink text + coloured swatch
    latest = []
    for s in series:
        idx = [i for i, v in enumerate(s["values"]) if v is not None]
        if idx:
            latest.append((s, s["values"][idx[-1]]))
    latest.sort(key=lambda t: (-t[1], t[0]["name"]))
    latest = latest[:DIRECT_LABELS]
    placed = []
    for s, v in latest:
        y = _y(v, ymax)
        while any(abs(y - py) < LABEL_MIN_GAP for py in placed):
            y += LABEL_MIN_GAP
        placed.append(y)
    # Keep the stack inside the plot: shift everything up by any overflow, then
    # re-separate from the top down so the minimum gap survives the shift.
    bottom, top = H - MB - 4, MT + 10
    overflow = max(0.0, max(placed, default=0.0) - bottom)
    placed = sorted(py - overflow for py in placed)
    for k in range(len(placed)):
        floor_y = top if k == 0 else placed[k - 1] + LABEL_MIN_GAP
        placed[k] = max(placed[k], floor_y)
    for (s, v), y in zip(latest, placed):  # latest is top-down; placed is ascending y
        x = ML + iw + 8
        parts.append(f'<rect class="series-{s["color"]}" x="{x}" y="{y - 9:.1f}" '
                     'width="10" height="10" rx="3" fill="var(--series)"/>')
        parts.append(f'<text class="dl" x="{x + 14}" y="{y:.1f}">'
                     f'{escape(str(s["name"]))}</text>')
    # crosshair: emitted hidden so history.js never needs the SVG namespace URL
    parts.append(f'<line class="xh" x1="{ML}" x2="{ML}" y1="{MT}" y2="{H - MB}" '
                 'stroke="var(--baseline)" stroke-dasharray="3 3" style="display:none"/>')
    parts.append("</svg>")
    return "".join(parts)
```
(Higher latest value → smaller y, so zipping `latest` (value-desc) with ascending `placed` keeps each label next to its own line.)

- [ ] **Step 3: `render_history`** in `page.py` — delete `legend.sort(key=lambda e: -e["latest_pct"])` (series are already alphabetical).

- [ ] **Step 4: `history.html.j2`**

```html
{% extends "base.html.j2" %}
{% block content %}
{% if data is none %}
<div class="locked">No forecast history yet — this chart fills in after the first
production refresh.</div>
{% else %}
<h2>📈 Odds Over Time</h2>
<p class="sub">Each player's win probability at every production refresh. A break in a line
means no forecast was produced that week.</p>
<div class="chartbox">
{{ svg }}
<div class="legend">
{%- for s in legend %}<span><span class="sw series-{{ s.color }}" style="background:var(--series)"></span>{{ s.name }} — {{ s.latest_pct }}%</span>{% endfor %}
</div>
</div>
<details class="acc"><summary>Data table <span class="stats">(accessible fallback)</span></summary>
<div class="scroller" style="border:none"><table>
<thead><tr><th class="t">Refresh</th>{% for s in data.series %}<th>{{ s.name }}</th>{% endfor %}</tr></thead>
<tbody>
{% for row in table_rows -%}
<tr><td class="t">{{ row.date }}</td>{% for cell in row.cells %}{% if cell is none %}<td class="dash">·</td>{% else %}<td>{{ cell }}%</td>{% endif %}{% endfor %}</tr>
{% endfor -%}
</tbody>
</table></div>
</details>
<div id="tipbox"></div>
<script>window.HISTORY = {{ data | json_embed }};</script>
<script>{{ history_js }}</script>
{% endif %}
{% endblock %}
```

- [ ] **Step 5: `history.js`** (crosshair tooltip, pointer-only, no innerHTML with data)

```js
"use strict";
(function () {
  var D = window.HISTORY;
  var svg = document.querySelector(".chartbox svg");
  var tip = document.getElementById("tipbox");
  if (!svg || !tip) return;
  var W = 920, L = 52, R = 110, iw = W - L - R;
  var n = D.dates.length;
  var xh = svg.querySelector(".xh");
  function x(i) { return n > 1 ? L + iw * i / (n - 1) : L + iw / 2; }
  svg.addEventListener("mousemove", function (ev) {
    var r = svg.getBoundingClientRect(), sx = W / r.width;
    var i = n > 1 ? Math.round(((ev.clientX - r.left) * sx - L) / (iw / (n - 1))) : 0;
    i = Math.max(0, Math.min(n - 1, i));
    xh.setAttribute("x1", x(i)); xh.setAttribute("x2", x(i));
    xh.style.display = "";
    tip.textContent = "";
    var b = document.createElement("strong");
    b.textContent = D.dates[i];
    tip.appendChild(b);
    D.series.forEach(function (s) {
      tip.appendChild(document.createElement("br"));
      var sw = document.createElement("span");
      sw.className = "dlsw series-" + s.color;
      sw.style.background = "var(--series)";
      tip.appendChild(sw);
      var v = s.values[i];
      tip.appendChild(document.createTextNode(
        s.name + ": " + (v === null ? "·" : (Math.round(v * 1000) / 10).toFixed(1) + "%")));
    });
    tip.style.display = "block";
    tip.style.left = (ev.clientX + 14) + "px";
    tip.style.top = (ev.clientY + 10) + "px";
  });
  svg.addEventListener("mouseleave", function () {
    tip.style.display = "none";
    xh.style.display = "none";
  });
})();
```

- [ ] **Step 6: Run and commit**

Run: `.venv/bin/pytest tests/test_chart.py tests/test_build.py tests/test_self_containment.py -q` — Expected: PASS.
```bash
git add smw/render/chart.py smw/render/page.py smw/render/templates/history.html.j2 smw/render/static/history.js tests/test_chart.py tests/test_build.py
git commit -m "feat: odds chart at mockup geometry with crosshair tooltip and alphabetical legend"
```

---

### Task 8: Scoring rules page

**Files:**
- Rewrite: `smw/render/templates/rules.html.j2`
- Test: `tests/test_page.py`

- [ ] **Step 1: Failing test** (append to `tests/test_page.py`)

```python
def test_rules_page_matches_mockup(tmp_path, season, group):
    html = _render_rules(tmp_path, season, group)
    for s in ("<h2>📜 Scoring rules</h2>", "between <strong>May 1 and Sep 7, 2026</strong>",
              '<th class="t">Ranked pick, vs. the actual top ten</th><th>Points</th>',
              "🐴 Dark horse anywhere in the top ten", '<td class="zero">0</td>',
              "13 + 10×8 + 13 + 3 = <strong>109</strong>", "no tiebreaker — tied players share the placement.",
              '<div class="scroller"><table>'):
        assert s in html, s
```
Run: `.venv/bin/pytest tests/test_page.py -q` — Expected: FAIL.

- [ ] **Step 2: `rules.html.j2`**

```html
{% extends "base.html.j2" %}
{% block content %}
<h2>📜 Scoring rules</h2>
<p>Before the window opens, each player locks <strong>10 ranked picks</strong> — the films they
believe will gross the most at the domestic box office between <strong>{{ window_and }}</strong>, in predicted finish order — plus <strong>3 dark horses</strong>, unordered.
All 13 titles must be distinct. Only films released inside the window count, and only money
earned through Labor Day counts.</p>
<div class="scroller"><table>
  <thead><tr><th class="t">Ranked pick, vs. the actual top ten</th><th>Points</th></tr></thead>
  <tbody>
    <tr><td class="t">Exact match at position 1 or position 10</td><td class="pos">13</td></tr>
    <tr><td class="t">Exact match at positions 2–9</td><td class="pos">10</td></tr>
    <tr><td class="t">In the top ten, off by exactly 1 position</td><td class="pos">7</td></tr>
    <tr><td class="t">In the top ten, off by exactly 2 positions</td><td class="pos">5</td></tr>
    <tr><td class="t">In the top ten, off by 3 or more positions</td><td class="pos">3</td></tr>
    <tr><td class="t">Not in the top ten</td><td class="zero">0</td></tr>
    <tr><td class="t">🐴 Dark horse anywhere in the top ten</td><td class="pos">1</td></tr>
  </tbody>
</table></div>
<p class="small">Maximum possible score: 13 + 10×8 + 13 + 3 = <strong>109</strong>.
Highest total wins; there is no tiebreaker — tied players share the placement.</p>
{% endblock %}
```
(`window_and` is `May 1 and Sep 7, 2026` on one line; the mockup's line break inside the `<strong>` is incidental.)

- [ ] **Step 3: Run and commit**

Run: `.venv/bin/pytest tests/test_page.py -q` — Expected: PASS (`test_scoring_rules_reproduced_on_site` still finds every needle).
```bash
git add smw/render/templates/rules.html.j2 tests/test_page.py
git commit -m "feat: scoring rules page to the mockup"
```

---

### Task 9: Site-wide parity tests, docs, regenerated `out/`

**Files:**
- Create: `tests/test_mockup_parity.py`
- Modify: `AGENTS.md` (line 18), `README.md` (operator files section)
- Replace: `out/` contents

- [ ] **Step 1: Write the parity tests** — `tests/test_mockup_parity.py`

```python
"""Acceptance criteria 7, 8, 9, 12, 13 across every page of every group."""
import re
from datetime import date
import pytest
import smw.render.build as build
from tests.conftest import FIXTURES

PAGES = ("index.html", "whatif.html", "scenarios.html", "history.html", "rules.html")
GONE = (".num", ".table-scroll", "--card", "--dim", "--pos", "--gold", "cell-", "divider-row",
        "stats-line", '"standings"', "film-list", "two-col", "tab-row", 'class="tab"',
        "highlight-col", "chart-wrap", "odds-chart", "legend-swatch", "season-line",
        "theme-toggle", "reset-order", "points-grid", "crosshair-tip")
HEADINGS = {
    "index.html": ("<h2>🏆 Projected Standings</h2>", "<h2>📋 All Players' Lists</h2>",
                   "<h2>👤 Per-Player Detail</h2>", "<h2>🎞️ Films</h2>"),
    "whatif.html": ("<h2>🎬 What If? sandbox</h2>", "<h2>Points by film, for this order</h2>",
                    "↺ Reset to projected order"),
    "scenarios.html": ("<h2>🔮 Winning Scenarios</h2>", "crowns them champion"),
    "history.html": ("<h2>📈 Odds Over Time</h2>", "A break in a line"),
    "rules.html": ("<h2>📜 Scoring rules</h2>", "<strong>109</strong>"),
}

@pytest.fixture(scope="module")
def site(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("site")
    d = tmp / "data" / "seasons" / "2026"
    (d / "groups").mkdir(parents=True)
    # 3 chart films + 8 analyst entries = 11 non-zero projections ≥ the structural 10
    # and the policy 11 → a LIVE forecast, so What If? and Scenarios are unlocked.
    (d / "season.yaml").write_text(
        "year: 2026\nwindow_start: 2026-05-01\nwindow_end: 2026-09-07\n"
        "seed: 42\nmonte_carlo_trials: 500\nmin_projections_for_forecast: 11\n"
        "default_group: g\n")
    (d / "preopening_projections.yaml").write_text("".join(
        f'"Estimated Film {i}":\n'
        "  release_date: 2026-07-10\n"
        "  opening_weekend_estimate: 40_000_000\n"
        "  total_domestic_estimate: 110_000_000\n"
        "  confidence: med\n"
        for i in range(8)))
    for gid, name in (("g", "G League"), ("h", "H League")):
        (d / "groups" / f"{gid}.yaml").write_text(
            f"group_id: {gid}\ndisplay_name: {name}\nplayers:\n"
            "  alice:\n"
            "    ranked: [Big Summer Film, Mid June Comedy, Labor Day Opener, F4, F5, F6, F7, F8, F9, F10]\n"
            "    dark_horses: [D1, D2, Tiny Tail Film]\n"
            "  bob:\n"
            "    ranked: [Mid June Comedy, Big Summer Film, Labor Day Opener, F4, F5, F6, F7, F8, F9, F10]\n"
            "    dark_horses: [D1, D2, Tiny Tail Film]\n")
    (d / "forecast_history").mkdir()
    for gid in ("g", "h"):
        (d / "forecast_history" / f"{gid}.jsonl").write_text(
            '{"date": "2026-08-08", "player": "alice", "win_prob": 0.6, "median_final_pts": 50, "p10": 40, "p90": 60}\n'
            '{"date": "2026-08-08", "player": "bob", "win_prob": 0.4, "median_final_pts": 45, "p10": 35, "p90": 55}\n')
    out = tmp / "out"
    with pytest.MonkeyPatch.context() as mp:  # module-scoped, so no `monkeypatch` fixture
        mp.setattr(build, "fetch", lambda year: (FIXTURES / "synthetic_chart.html").read_text())
        build.run_build(tmp / "data", out, date(2026, 8, 15), local=True)
    return out

def _pages(site):
    for gid in ("g", "h"):
        for page in PAGES:
            yield gid, page, (site / "2026" / gid / page).read_text()

def test_h1_title_and_selectors_everywhere(site):
    for gid, page, html in _pages(site):
        assert "<h1>🍿 Summer Movie Wager</h1>" in html, (gid, page)
        name = "G League" if gid == "g" else "H League"
        assert re.search(rf"<title>[^<]+ · Summer Movie Wager 2026 · {name}</title>", html), (gid, page)
        assert 'value="../../2026/g/index.html" selected' in html, (gid, page)
        assert f'value="../{gid}/{page}" selected' in html, (gid, page)
        other = "h" if gid == "g" else "g"
        assert f'value="../{other}/{page}"' in html, (gid, page)

def test_every_table_is_in_a_scroller(site):
    for gid, page, html in _pages(site):
        body = html.split("</style>")[1]
        for m in re.finditer(r"<table\b[^>]*>", body):
            before = body[:m.start()].rstrip()
            if 'id="wiStandings"' in m.group(0):
                assert before.endswith('<div aria-live="polite">'), (gid, page)  # §3.5: the panel table
            else:
                assert re.search(r'<div class="scroller"(?: style="border:none")?>$', before), (gid, page, m.group(0))

def test_no_legacy_classes_or_tokens(site):
    for gid, page, html in _pages(site):
        for s in GONE:
            assert s not in html, (gid, page, s)

def test_verbatim_copy_per_page(site):
    for gid, page, html in _pages(site):
        for s in HEADINGS[page]:
            assert s in html, (gid, page, s)
        assert "Raw numbers: <a href=\"data.json\">data.json</a>" in html
        assert "Forecast: 500 seeded Monte Carlo seasons over 11 projected films." in html

def test_odds_chart_geometry(site):
    html = (site / "2026" / "g" / "history.html").read_text()
    assert 'viewBox="0 0 920 360"' in html and 'class="dl"' in html
    assert html.count('text-anchor="middle"') <= 8

def test_self_contained_including_vendored_library(site):
    for gid, page, html in _pages(site):
        for marker in ("http://", "https://", "//cdn", "@import", "url(http", "fetch(", "XMLHttpRequest"):
            assert marker not in html, (gid, page, marker)
    root = (site / "index.html").read_text()
    assert "http://" not in root and "https://" not in root
```

Run: `.venv/bin/pytest tests/test_mockup_parity.py -q` — Expected: PASS. Any failure here is a real gap in Tasks 3–8; fix it in the responsible template and re-run the whole suite.

- [ ] **Step 2: Docs**

`AGENTS.md` line 18 — replace the parenthesised file list with:
```
- Persisted data is exactly the files in spec §5 laid out per season as `data/seasons/<year>/` (`season.yaml`, `groups/*.yaml`, `preopening_projections.yaml`, `movies_overrides.yaml`, `box_office_history.jsonl`, `forecast_history/<group_id>.jsonl`). There is deliberately **no persisted refresh/run-date record**: a degraded production refresh appends nothing (§5.6), and a refresh date that is consequently absent from the odds-over-time axis is accepted behaviour, not a defect. Reviewers must not request refresh-date persistence.
```
`README.md` — in "Operator files" and the end-of-season protocol replace `data/` paths with `data/seasons/<year>/…` (`data/seasons/2026/box_office_history.jsonl`, `data/seasons/<year>/preopening_projections.yaml`, `data/seasons/<year>/movies_overrides.yaml`, `data/seasons/<year>/groups/*.yaml`, `data/seasons/<year>/season.yaml`), and add one bullet:
```
- `data/seasons/<year>/season.yaml` — dates, thresholds, seed, `default_group`
  (the group the root redirect and the year selector land on).
```
Add under a new `## Site layout` heading:
```
The build renders every season under `data/seasons/` to `out/<year>/<group_id>/`
(five pages + `data.json` each) and writes `out/index.html`, a redirect to the newest
season's `default_group`. Pages link relatively, so the site works from any base path.
```

- [ ] **Step 3: Replace the committed site**

```bash
git rm -q out/index.html out/whatif.html out/scenarios.html out/history.html out/rules.html out/data.json
.venv/bin/python -m smw --local --date 2026-08-27      # fetches the BOM chart (network)
ls out out/2026 out/2026/smw-friends
open out/index.html                                     # should land on 2026/smw-friends/index.html
```
If the network is unavailable, leave `out/` deleted, say so in the commit message, and let the operator's next weekly refresh regenerate it.

- [ ] **Step 4: Full suite, then commit**

Run: `.venv/bin/pytest -q` — Expected: all PASS.
```bash
git add tests/test_mockup_parity.py AGENTS.md README.md out
git commit -m "test: site-wide mockup parity; docs for data/seasons layout; regenerate out/"
```

- [ ] **Step 5: Cross-review**

Working tree clean (`git status --porcelain` empty), then `/cross-review superpowers/specs/2026-08-27-ux-refresh-spec.md`. Point the reviewer at the "Decisions the spec forced" section of this plan for criteria 8 and 11.

---

## Self-review

**Spec coverage** — §2.1 data layout + `default_group` → T1; §2.2 output layout, every season rendered, empty seasons error → T2; §2.3 root redirect → T2; §2.4 pipeline shape → T2; §3.1 stylesheet + parity test → T3; §3.2 theme script → T3; §3.3 skeleton, dates, footer sentence, scroller/cell classes → T3 (skeleton) + T4–T8 (per page); §3.4 → T4; §3.5 → T5; §3.6 → T6; §3.7 → T7; §3.8 → T8; §3.9 snapshot → T4; §4 selectors + title → T3; §5 SortableJS → T5; criteria 1–6 → T1–T3 tests; 7–9 → T9; 10 → T7; 11–12 → T5/T9; 13 → T2 (`test_reproducible_build` + root); 14 → T4; 15 → T1 (`git mv`) + T9 (docs).

**Placeholders** — none; every code step carries the code.

**Type consistency** — `Site(years, groups, forecast_note)` defined T3, consumed T3 build + tests; `base_context(season, group, active, today, site=None)` used in T2 (4-arg, still valid) and T3+; `load_season_dir` T1 → T2; `PAGES[active][0]` filename T3; `render_redirect(env, out_dir, target)` T2; chart constants `W H ML MR MT MB LABEL_MIN_GAP` referenced by `tests/test_chart.py::test_direct_labels_stay_inside_viewbox` (`H, MB, LABEL_MIN_GAP`) still exported in T7.
