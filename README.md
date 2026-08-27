# Summer Movie Wager — Tracker & Forecaster

Static-site tracker and Monte Carlo forecaster for a season-long box-office
prediction game. One network dependency (Box Office Mojo's yearly chart),
no server, no build toolchain. Output in `out/` is generated — never hand-edit it.

This repo also serves as a learning ground for a fully agentic coding workflow —
see `CONTRIBUTING.md` and `AGENTS.md`.

## Setup

    uv venv --python 3.12 .venv
    uv pip install --python .venv/bin/python --config-settings editable_mode=compat -e '.[dev]'

## Running

    .venv/bin/pytest                       # tests run BEFORE any production build
    .venv/bin/python -m smw --local        # dev run: writes out/, appends NO history
    .venv/bin/python -m smw                # production run: also appends history files

Every exploratory or development run uses `--local`. A production run on an
off-cadence day skews the observed-decay estimator, which assumes roughly
weekly snapshots.

### The run date (`--date`)

The run date is the **only** place wall-clock time enters the system. Every
date-dependent decision — which films are pre-release vs. in theaters, how far
each decay curve has elapsed, whether the chart is still fetched or frozen, the
history cutoff, and the `captured_at` / "refreshed" stamps — flows from it.

- `--date YYYY-MM-DD` sets it explicitly.
- **If `--date` is omitted it defaults to today's calendar date.** So the same
  `data/` built on two different days legitimately produces two different sites;
  that is expected, not a bug. Pass `--date` whenever you need a build you can
  reproduce or compare later (byte-identical output for identical inputs).

    .venv/bin/python -m smw --local --date 2026-08-26   # reproducible dev build
    .venv/bin/python -m smw --date 2026-09-08           # the final production run

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
  appended to `data/seasons/2026/box_office_history.jsonl` by hand.

## Operator files (maintained through the season)

- `data/seasons/<year>/preopening_projections.yaml` — analyst estimates. The build's
  "no projection" warnings are your to-do list.
- `data/seasons/<year>/movies_overrides.yaml` — categories (classify EVERY picked film,
  including genuinely wide ones), title aliases, date/status corrections.
  A Guard C failure prints the exact alias block to add here.
- `data/seasons/<year>/groups/*.yaml` — rosters; locked once the window opens.
- `data/seasons/<year>/season.yaml` — dates, thresholds, seed, `default_group`
  (the group the root redirect and the year selector land on).

## Site layout

The build renders every season under `data/seasons/` to `out/<year>/<group_id>/`
(five pages + `data.json` each) and writes `out/index.html`, a redirect to the newest
season's `default_group`. Pages link relatively, so the site works from any base path.

## Snapshot ritual

The leaderboard has a byte-exact snapshot test. To regenerate deliberately:
delete `tests/fixtures/snapshot_index.html`, run the test once (it rewrites the
fixture and fails), **open the file in a browser and look at it**, then re-run
to lock. A snapshot regenerated without inspection tests nothing.
