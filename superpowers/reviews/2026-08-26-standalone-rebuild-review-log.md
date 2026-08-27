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

## Loop 2 (user-invoked `/cross-review`, 2026-08-27) — Round 1, 07:20 EDT

- Reviewed head: `0209fce` · model `gpt-5.6-sol/medium` · exit **10** (`changes_requested`, 2 blocking) · raw: `round-4.json`
- Deterministic checks before review: 166 passed. (Stray untracked `uv.lock` parked outside the repo to satisfy the clean-tree check.)

| # | Sev | File | Finding (verbatim summary) | Verdict | Action |
|---|-----|------|----------------------------|---------|--------|
| 1 | med | `smw/render/build.py:97` | Pre-season builds fetch the chart, find no in-window rows, and trip Guard B — violating §10's "must work before the season starts" | **Valid** | Chart fetched only when `window_start ≤ today−1 ≤ window_end`; before the window there can be no in-window row, so the fetch is skipped. Test: `test_pre_season_build_never_fetches_and_renders`. |
| 2 | med | `smw/catalog/normalize.py:52` | A `release_date` override is applied only after `windowed()`, so it cannot rescue a row the source misdated outside the window | **Valid** | `apply_chart_aliases` now also applies `release_date` overrides (keyed on upstream or canonical title) before the window filter. Tests: `test_release_date_override_applied_to_chart_rows_before_window_filter`, `test_chart_release_date_override_rescues_out_of_window_row`. |

- After fixes: 169 passed. Real build unchanged.

### Loop 2 — Round 2, 07:27 EDT

- Reviewed head: `fffe0e3` · model `gpt-5.6-sol/medium` · exit **10** (`changes_requested`, 2 blocking) · raw: `round-5.json`
- Deterministic checks before review: 169 passed.

| # | Sev | File | Finding (verbatim summary) | Verdict | Action |
|---|-----|------|----------------------------|---------|--------|
| 1 | med | `smw/render/build.py:160` | Refresh dates are rebuilt from positive-gross box-office rows; a degraded production run with zero grosses (pre-season) leaves no durable record, so later builds drop that date and the line connects across it | **Disputed (scope), not fixed.** Factually correct for one case: a *production* run before any gross exists *and* below the forecast threshold. But spec §5 enumerates the persisted files and §5.6 states a degraded run appends nothing — the gap is the intended signal. Persisting run dates needs a new data file the spec doesn't define. Pre-season production runs are also not part of the documented weekly cadence. Left for the user: either accept the edge or add a `refresh_history.jsonl` (spec change). | none |
| 2 | med | `smw/__main__.py:8` | `--date` defaults to `date.today()` | **Rejected by user (2026-08-27)** — spec §1.3 permits wall-clock time to enter via the explicitly passed run day and only there; day-to-day differences are intended. AGENTS.md convention reworded to make the CLI default explicit so the reviewer stops re-raising it. | AGENTS.md wording only |

### Loop 2 — Round 3 (cap), 07:30 EDT

- Reviewed head: `a015e4b` · model `gpt-5.6-sol/medium` · exit **10** (`changes_requested`, 2 blocking) · raw: `round-6.json`
- Deterministic checks before review: 169 passed. The `--date` finding did not recur after the AGENTS.md clarification.
- **Cap reached — loop stopped; nothing below changed in code.**

| # | Sev | File | Finding (verbatim summary) | My assessment |
|---|-----|------|----------------------------|---------------|
| 1 | med | `smw/render/build.py:160` | Same as loop-2 round-2 #1: a degraded production run before any gross leaves no durable date, so later charts connect across it | Still disputed on spec grounds (§5 file set, §5.6 "degraded run appends nothing"). Fixing requires a spec addition (a persisted refresh-date file). **User decision.** |
| 2 | med | `smw/config/season.py:38` | `load_season` doesn't validate types/ranges/`default_wow` keys; zero trials or a missing category fails later (division by zero, `KeyError`) instead of at the load boundary | **Agree.** Small: assert positive ints for counts/thresholds, dates for the window, and that `default_wow` has both `wide` and `animated_family` in (0, 1]. Recommend fixing. |

Last reviewed commit: `a015e4b`. No approved SHA exists.

## Loop 3 (user-invoked `/cross-review`, 2026-08-27)

- Pre-round: loop-2 cap finding #2 (Season load validation) fixed — `load_season` now
  rejects non-date windows, non-integer/non-positive counts, and a `default_wow` missing a
  category or outside (0, 1]. Tests: `test_invalid_values_fail_at_load`, `test_string_dates_rejected`.
  Finding #1 (persist refresh dates) remains disputed on spec grounds.

### Loop 3 — Round 1, 07:33 EDT

- Reviewed head: `24095da` · model `gpt-5.6-sol/medium` · exit **10** (`changes_requested`, 5 blocking) · raw: `round-7.json`
- Deterministic checks before review: 175 passed. (User's uncommitted `scripts/codex-review.sh` effort bump stashed at user's direction; reviews stay at medium.)

| # | Sev | File | Finding (verbatim summary) | Verdict | Action |
|---|-----|------|----------------------------|---------|--------|
| 1 | med | `smw/render/build.py:160` | Persist production refresh dates (3rd time) | **Still disputed** on spec grounds (§5 file set, §5.6). User decision pending. | none |
| 2 | med | `smw/catalog/normalize.py:136` | Override metadata on an `alias_of` variant entry (category/date/status) is discarded because lookups use the canonical title | **Valid** | `load_overrides` folds variant metadata onto the canonical entry; conflicting values raise. Tests: `test_alias_entry_metadata_folds_onto_canonical`, `test_alias_entry_conflicting_metadata_rejected`. |
| 3 | med | `smw/config/season.py:55` | `matrix_rows < 10` accepted, so the leaderboard/What If finish order would have fewer than ten films | **Valid** | `matrix_rows >= 10` enforced at load. Test: `test_matrix_rows_below_ten_rejected`. |
| 4 | med | `smw/catalog/normalize.py:96` | Pre-opening entries not type-checked; quoted numbers / string dates fail later | **Valid** | Dates, numbers, strings validated at load with path+title in the error. Test: `test_preopening_bad_types_fail_at_load`. |
| 5 | med | `smw/config/groups.py:36` | `group_id` not validated as a directory-safe slug (§3.3) | **Valid** | `[a-z0-9][a-z0-9_-]*` enforced. Test: `test_group_id_must_be_slug`. |

- After fixes: see next round header for test count.

### Loop 3 — Round 2, 07:38 EDT

- Reviewed head: `005073d` · model `gpt-5.6-sol/medium` · exit **10** (`changes_requested`, 3 blocking) · raw: `round-8.json`
- Deterministic checks before review: 186 passed.

| # | Sev | File | Finding (verbatim summary) | Verdict | Action |
|---|-----|------|----------------------------|---------|--------|
| 1 | med | `smw/render/build.py:160` | Persist production refresh dates (4th time) | **Still disputed** (§5 file set, §5.6). | none |
| 2 | med | `smw/config/groups.py:27` | Roster loader doesn't type-check display_name, players mapping, usernames, or titles | **Valid** | Types validated at load with player-specific errors. Test: `test_bad_types_fail_at_load`. |
| 3 | med | `smw/catalog/normalize.py:42` | `alias_of` / `release_date` overrides not type-checked | **Valid** | Non-empty string / `date` enforced at load. Test: `test_override_bad_types_fail_at_load`. |

### Loop 3 — Round 3 (cap), 07:42 EDT

- Reviewed head: `a85c6f1` · model `gpt-5.6-sol/medium` · exit **10** (`changes_requested`, 1 blocking) · raw: `round-9.json`
- Deterministic checks before review: 191 passed. The refresh-date dispute (build.py:160) was **not** raised this round.
- **Cap reached — loop stopped; nothing below changed in code.**

| # | Sev | File | Finding (verbatim summary) | My assessment |
|---|-----|------|----------------------------|---------------|
| 1 | med | `smw/config/groups.py:31` | `players: false` becomes an empty roster via `or {}`; a mapping-valued `ranked`/`dark_horses` becomes a tuple of its keys and can pass the count checks | **Agree.** Trivial: default only `None` to `{}`, and require `ranked`/`dark_horses` to be lists. Recommend fixing. |

Last reviewed commit: `a85c6f1`. No approved SHA exists.
