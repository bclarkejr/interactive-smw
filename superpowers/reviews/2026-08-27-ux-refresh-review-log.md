# Cross-review log — UX refresh (feat/ux-refresh)

Spec: `superpowers/specs/2026-08-27-ux-refresh-spec.md` (amends the rebuild spec).
Plan: `superpowers/plans/2026-08-27-ux-refresh.md`.
Reviewer: Codex via `scripts/codex-review.sh` (model/effort printed per round).
Deterministic checks: `.venv/bin/pytest` (lint/types not configured).

## Implementation notes before review (deviations from the spec text, all deliberate)

Documented in the plan's "Decisions the spec forced" section and the SDD ledger rulings:

- **D1 — criterion 11 tested on `whatif.js`, not `whatif.html`.** The genuine `Sortable.min.js`
  1.15.6 contains `dragstart`/`dragover`/`touchstart`/`elementFromPoint`, so a page that inlines
  it can never satisfy "does not contain". `whatif.html` is still checked for `new Sortable(`.
- **D2 — `brainstorming/mockup.html` un-ignored and committed.** §3.1's parity test must read it.
- **D3 — `table#wiStandings` exempt from "every table in `div.scroller`".** §3.5 and the mockup
  both put it under `div[aria-live=polite]` inside `.wi-panel`.
- **D4 — scenario zero cells are `td.mid`** (spec §3.3), not the mockup's `span.mid`; the
  mockup's own CSS rule is `td.mid`.
- **D5 — legend/direct-label "latest value" is the last non-null value.**
- **D6 — crosshair `<line class="xh">` emitted server-side hidden**; `createElementNS` would put
  the SVG namespace URL in the page and fail self-containment.
- **Ruling (T3):** the plan's test fixture passed `Site.groups` unsorted and the first
  implementation sorted them in `base_context`; reverted — sorting stays in the pipeline
  (rebuild §11.4), fixture corrected, end-to-end order assertion added.
- **Ruling (T4):** plan-verbatim `fmt_money` rendered 999.95M–1B as `$1000.0M`; now branches
  on the rounded value.
- **Ruling (T5):** plan-verbatim `whatif.js` dropped keyboard focus when a ▲/▼ press landed a
  film at an end; focus now moves to the sibling arrow.
- **Ruling (final review):** rendering every season on every run (§2.2) left the two history
  appends gated only on `--local`, so a production run appended today's rows into past
  seasons. Persistence is now gated on the live window; the spec's §2.2 and criterion 5 were
  amended to say so, and §3.1/criterion 6 now name `.vh` alongside `.sel`.
- The snapshot's by-eye inspection (§3.9) was done via headless-Chrome screenshots of the
  fixture and of the built What If? / odds pages, compared against the mockup.

## Round 1 — 2026-08-27

- Reviewed head: `31efc11` · model `gpt-5.6-sol/high` · exit **10** (`changes_requested`, 4 blocking)
- Deterministic checks before review: 249 passed.

| # | Sev | File | Finding (verbatim summary) | Verdict | Action |
|---|-----|------|----------------------------|---------|--------|
| 1 | med | `smw/render/build.py:140` | Persistence gate uses yesterday's date: a production run on `window_start` persists nothing although the season is open | **Valid** — the yesterday boundary belongs to the chart fetch only | `persist` now spans `window_start ≤ today ≤ window_end + 1`; fetch keeps the yesterday-based gate. Test: `test_production_run_on_window_start_persists`. |
| 2 | med | `smw/config/season.py:78` | Roster filename not checked against `group_id`; duplicate IDs pass loading and clobber the same output dir / forecast file | **Valid** | `load_season_dir` requires `path.stem == group_id` and rejects duplicates. Tests: `test_load_season_dir_rejects_filename_id_mismatch`, `test_load_season_dir_rejects_duplicate_group_ids`. |
| 3 | med | `smw/render/templates/index.html.j2:32` | Explanatory paragraph is unconditional; in current-points mode it describes projections the table doesn't show (rebuild §10.3) | **Valid** | Live-mode copy kept verbatim; current-points mode gets actuals wording. Test: `test_current_points_mode_has_no_forecast_numbers` extended. |
| 4 | med | `smw/render/static/sortable.min.js:1` | Banner omits the copyright attribution §5.1 says the banner must retain | **Valid** — upstream's banner names no holder, but the spec requires it | Banner is now `/*! Sortable 1.15.6 - MIT | (c) 2019 Lebedev Konstantin */` (still URL-free); test updated. |
