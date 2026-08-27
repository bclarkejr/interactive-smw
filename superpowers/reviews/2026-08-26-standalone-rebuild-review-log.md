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

