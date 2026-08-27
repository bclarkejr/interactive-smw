# Cross-review log — standalone rebuild (feat/standalone-rebuild)

Spec: `superpowers/specs/2026-08-15-standalone-rebuild-spec.md`
Reviewer: Codex via `scripts/codex-review.sh` (model/effort printed per round).
Deterministic checks: `.venv/bin/pytest` (lint/types not configured).
Raw reviewer output per round is copied verbatim to `round-N.json` in this directory;
the script's stdout/stderr to `round-N.log`.

## Implementation notes before review (deviations from the plan, all deliberate)

- Task 1: repo already had git; skipped `git init`. Python 3.12.13 skips the setuptools
  "hidden" editable `.pth`, so the install uses `--config-settings editable_mode=compat`
  and pytest sets `pythonpath = ["."]`.
- Task 7: plan's test `test_observations_after_cutoff_ignored` passes an empty chart with a
  carried film above the floor and expects no Guard C; plan's impl would raise. Resolved by
  skipping Guard C when there are no chart rows (nothing to be absent from; Guard A already
  covers an empty chart upstream).
- Task 13/19: `_scenarios` margin used `max()` over runner-ups, which is empty for a
  single-player group (the plan's own Task 19 test uses one). Fixed with `default=0`.
- Task 16: plan's locked-state test asserted `"film-list" not in html`, but the inlined CSS
  contains `#film-list`. Test tightened to `id="film-list"`.
- Task 21: real 2026 chart saved as `tests/fixtures/year_chart.html` and the parser tests
  retargeted to it; the synthetic chart kept as `synthetic_chart.html` for the pipeline
  tests, which need a small controlled catalog to exercise the Early/degraded state.
- Note for operators: BOM's yearly chart shows dates without a year, so a Dec-2025 holdover
  is stamped Dec 2026. Harmless for the window filter (out either way) but the
  `release_date` on such rows is wrong.

## Round 1 — 2026-08-26 22:48 EDT

- Reviewed head: `2710923` · model `gpt-5.6-sol/medium` · exit **10** (`changes_requested`, 5 blocking) · raw: `round-1.json`
- Deterministic checks before review: 154 passed.

| # | Sev | File | Finding (verbatim summary) | Verdict | Action |
|---|-----|------|----------------------------|---------|--------|
| 1 | high | `smw/render/build.py:88` | Roster titles never canonicalized through `alias_of`; aliased roster spellings score 0 | **Valid** (§6.5 point 2 says rosters resolve to canonical; `build_films` canonicalized candidates but `Group` kept variants) | Added `canonical_group()` in `normalize.py`; `run_build` canonicalizes every group after overrides load. Test: `test_roster_alias_scores_against_canonical_title`. |
| 2 | high | `smw/render/build.py:124` | Final-state precedence (§10.1) not implemented: zero-gross films with estimates keep speculative projections; policy gate still decides | **Valid** — the plan's comment claimed "Final first" but nothing implemented it | `_project_one` collapses every projection to `(gross, σ=0, "final gross")` when `today > window_end+1`; `run_build` gates Final on the structural 10-film floor only. Tests: `test_final_state_collapses_every_projection`, `test_final_state_collapses_projections_and_forecasts`. |
| 3 | med | `smw/render/build.py:149` | `history.html` rendered before the forecast row is appended → page lags one refresh, first production forecast leaves it locked | **Valid** | Forecast-history append moved before `render_history` (same-date last-write-wins preserved by `build_history_data`). Test: `test_production_history_page_includes_current_refresh`. |
| 4 | med | `smw/model/simulate.py:68` | Empty `Group` crashes on `score_matrix.max(axis=0)` (violates §10.2) | **Valid** — reproduced `ValueError: zero-size array` | `simulate()` returns an empty `SimResult` for an empty roster. Test: `test_empty_group_returns_empty_result`. |
| 5 | med | `smw/render/chart.py:98` | Player names/dates interpolated unescaped into SVG marked `Markup` → HTML injection in `history.html` | **Valid** | `html.escape` on every dynamic SVG text. Test: `test_hostile_player_name_is_escaped_in_svg`. |

- After fixes: 160 passed. Real build (`out/`) byte-identical to the round-1 build.
- Checkpoint commit: see round 2 header.

## Round 2 — 2026-08-26 22:52 EDT

- Reviewed head: `ba071e4` · model `gpt-5.6-sol/medium` · exit **10** (`changes_requested`, 3 blocking) · raw: `round-2.json`
- Deterministic checks before review: 160 passed.

| # | Sev | File | Finding (verbatim summary) | Verdict | Action |
|---|-----|------|----------------------------|---------|--------|
| 1 | med | `smw/render/build.py:113` | Projections built from persisted history only; today's chart snapshot joins the series only after rendering, so the observed-decay blend lags one refresh and local builds never see it | **Valid** | New `resolve.with_snapshot()` folds today's resolved grosses into an in-memory series (same-date max, sorted); `run_build` passes that to `build_catalog`. Persistence unchanged (production only). Tests: `test_with_snapshot_merges_today_by_max`, `test_projection_uses_todays_snapshot_not_just_persisted_history`. |
| 2 | med | `smw/render/chart.py:17` | Date axis derived from forecast rows only, so a degraded production refresh vanishes and lines connect across it instead of showing the §12.4 gap | **Valid** | `build_history_data(rows, refresh_dates)` unions production refresh dates (from box-office history) into the axis; missing forecasts map to `None` → path break. Tests: `test_degraded_refresh_dates_appear_as_gaps`, `test_degraded_production_refresh_shows_as_history_gap`. |
| 3 | med | `smw/catalog/normalize.py:167` | `alias_of` can collapse two distinct roster titles onto one film after load-time validation, double-counting it | **Valid** | `canonical_group` re-validates the 13-distinct rule after resolution and raises naming the player and the collision. Test: `test_alias_collapsing_two_picks_is_rejected`. |

- After fixes: 165 passed. Real build (`out/`) unchanged.

## Round 3 (cap) — 2026-08-26 22:56 EDT

- Reviewed head: `4f08a84` · model `gpt-5.6-sol/medium` · exit **10** (`changes_requested`, 3 blocking) · raw: `round-3.json`
- Deterministic checks before review: 165 passed.
- **Hard cap of 3 rounds reached — loop stopped. Nothing below has been changed in code.**
  Each finding is assessed here for the user to decide; `4f08a84` is the last reviewed commit.

| # | Sev | File | Finding (verbatim summary) | My assessment |
|---|-----|------|----------------------------|---------------|
| 1 | med | `smw/render/build.py:99` | `chart_floor(raw)` runs before `windowed()` enforces Guard A; an empty parse dies with `min() arg is an empty sequence` instead of the Guard A message | **Agree.** Real, ~2-line fix: call `windowed(raw, season)` (or check `raw`) before `chart_floor`. Recommend fixing. |
| 2 | med | `smw/render/build.py:158` | `refresh_dates` is read from the box-office history *before* today's rows are appended, so a degraded *production* refresh still doesn't get its gap; my round-2 test passed only because today's date also appears in the page header | **Agree — and the reviewer is right that my test was weak.** Fix: add `today.isoformat()` to `refresh_dates` on non-local runs (or append box-office rows before rendering) and assert on the SVG/table rather than the whole page. Recommend fixing. |
| 3 | med | `smw/__main__.py:8` | `--date` defaults to `date.today()`, so the same inputs built on different days differ; README's production command omits `--date` | **Disputed / judgment call.** The plan (Task 19) explicitly specifies "`--date` defaults to the real today; every other date in the system flows from this argument", and spec §1.3 allows wall-clock only via `--date` — the CLI boundary supplying a default is the intended operator convenience; the pipeline itself is reproducible given `today`. Reviewer's reading is stricter but defensible: making `--date` required is a one-line change plus README edits. User's call. |

### Where things stand
- Reviewed/approved SHA: **none** — the branch was never approved. Last reviewed commit `4f08a84`.
- Suggested next step: apply #1 and #2 (both small), decide #3, checkpoint, run `/cross-review superpowers/specs/2026-08-15-standalone-rebuild-spec.md` once more.

### Post-cap follow-up — 2026-08-27 (user decision)
- #1 and #2 applied in `a8b2cbf` (user-directed); tests: `test_empty_chart_parse_fails_with_guard_a`,
  tightened `test_degraded_production_refresh_shows_as_history_gap` to assert on the SVG/table.
  166 passed. Not yet re-reviewed by Codex.
- #3 pending user decision.
- #3 **rejected by user** (2026-08-27): spec §1.3 permits wall-clock time to enter via the
  explicitly passed run day, and only there; a build differing by run date is intended.
  README now documents `--date`, its default-to-today behaviour, and shows examples.
