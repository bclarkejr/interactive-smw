# Summer Movie Wager — UX Refresh

**Amendment to the standalone rebuild specification: multi-season, multi-group site
layout; mockup-parity presentation; animated What If? reordering.**

Version 1.0 · 2026-08-27

---

## 0. How to read this document

This document amends `superpowers/specs/2026-08-15-standalone-rebuild-spec.md` (the
"rebuild spec"). Everything in the rebuild spec remains in force except where a section
below says **[Changed]** and names the rebuild-spec section it replaces. Section
references of the form "rebuild §N.M" point at that document; unqualified references point
at this one.

Requirements use RFC-2119 language: **MUST**, **MUST NOT**, **SHOULD**, **MAY**.

Section 1 states the problems. Sections 2–5 define the four changes. Section 6 lists the
numbered acceptance criteria that the cross-review checks. Section 7 lists what this
amendment deliberately does not do.

---

## 1. Purpose

Four things are wrong with the shipped site.

1. **A second group clobbers the first.** The build loops over every roster file but
   writes every group into the same output directory, so the alphabetically last group is
   the only one that survives. The rebuild spec deferred multi-group routing (§3.6); with
   two groups now configured, it can no longer be deferred.
2. **The site is named after a group.** The masthead reads "The Friends League". The
   site is *Summer Movie Wager*; a group is one roster playing it, and a season is one
   year of it. Both need to be selectable.
3. **Presentation drifted from the mockup.** `brainstorming/mockup.html` is the approved
   look. The shipped tables have no outer edge or card background, so adjacent sections
   run together; most headings dropped the mockup's emoji.
4. **Drag-and-drop gives no feedback until drop.** The What If? list uses the raw HTML5
   drag API: nothing moves until the pointer is released. The intended behaviour — rows
   sliding out of the way as the dragged row passes them — is what
   `bclarkejr.github.io/summer-movie-wager/whatif.html` does with SortableJS.

---

## 2. Seasons and groups

### 2.1 Data layout **[Changed — rebuild §3.6, §5 preamble, §5.1, §5.6]**

Persisted data is organised by season. Every file named in rebuild §5 keeps its name and
schema; only its location changes, and forecast history becomes per group.

```
data/
  seasons/
    2026/
      season.yaml
      groups/
        filmcast.yaml
        smw-friends.yaml
      preopening_projections.yaml
      movies_overrides.yaml
      box_office_history.jsonl
      forecast_history/
        filmcast.jsonl
        smw-friends.jsonl
```

- The season directory name MUST equal `season.yaml`'s `year`. A mismatch is a load
  error.
- `box_office_history.jsonl` is season-scoped and roster-independent, exactly as before.
- `forecast_history/<group_id>.jsonl` replaces the single `forecast_history.jsonl`. Its
  rows are per player, and two groups may share a player name, so one file per group is
  the only layout that keeps rebuild §5.6's schema unchanged. The row format is
  identical to rebuild §5.6.
- There is still **no persisted refresh-date record** (AGENTS.md); this amendment adds
  no new persisted file kinds.

**[Changed] `season.yaml` gains one optional key:**

| Field | Type | Default | Meaning |
|---|---|---|---|
| `default_group` | string | first `group_id` in lexical order | The group the root redirect and the year switch land on |

For 2026 the value is `smw-friends`. A `default_group` naming no roster file in the
season MUST fail at load time with a `ValueError`, in the same style as the season
loader's other checks.

### 2.2 Output layout **[Changed — rebuild §11.1]**

```
out/
  index.html                       ← redirect only (Section 2.3)
  2026/
    smw-friends/
      index.html  whatif.html  scenarios.html  history.html  rules.html  data.json
    filmcast/
      index.html  whatif.html  scenarios.html  history.html  rules.html  data.json
```

- Each group's five pages and `data.json` are written to `<out>/<year>/<group_id>/`.
  Nothing is written to `<out>/<year>/` directly.
- Nav pills and the footer's `data.json` / `rules.html` links stay page-relative
  (`whatif.html`, not `/2026/…/whatif.html`), so a group directory is self-contained and
  the site works from any base path.
- The build MUST render **every** season under `data/seasons/` on every run. A past
  season is in the Final state (rebuild §10.1) and reads no network, so this is cheap,
  and it is what keeps the year selector (Section 3.2) consistent without a separate
  index step.
- An empty or missing `data/seasons/` MUST be a build error, not an empty site.

### 2.3 Root redirect

`<out>/index.html` is a minimal static page containing a `<meta http-equiv="refresh"
content="0; url=<year>/<group_id>/index.html">` pointing at the **newest season's
`default_group`**, plus a visible fallback link to the same target for user agents that
ignore meta refresh. It carries the site's inlined CSS and theme script so the fallback
renders correctly, and nothing else. It is rendered from a template like every other page.

### 2.4 Pipeline shape

Rebuild §3.5 is unchanged: the roster-independent half of the build runs once per season,
the per-group half once per group. `run_build(data_dir, out_dir, today, local)` keeps its
signature; internally it discovers seasons and calls the existing per-season body once per
season with that season's directory and `<out>/<year>`. Render functions keep taking an
output directory (rebuild §3.5); only the call sites change.

---

## 3. Masthead

### 3.1 Identity **[Changed — rebuild §12.1 heading, §13.2]**

- The `<h1>` on every page MUST read **🍿 Summer Movie Wager** — the mockup's `h1`
  minus its hard-coded year, which now lives in the selector beside it.
- `<title>` MUST be `{page title} · Summer Movie Wager {year} · {group display_name}`.
- The season line (window, refreshed date) is unchanged.

### 3.2 Year and group selectors

Two native `<select>` elements sit in the masthead next to the `<h1>`. Both use a
visually-hidden `<label>` and navigate with `onchange="location.href=this.value"`. No
fetch, no client-side state, no library.

| Selector | Options | Selected | Target on change |
|---|---|---|---|
| Year | every season under `data/seasons/`, newest first | the page's season | `../../<year>/<that season's default_group>/index.html` |
| Group | every group in the page's season, by `display_name` | the page's group | `../<group_id>/<current page filename>` |

- Switching group MUST stay on the same page (What If? → the other group's What If?).
- Switching year MUST land on that year's default group's leaderboard: a group need not
  exist in another season.
- A selector with a single option still renders; it is not hidden. With one season and
  one group the site looks exactly as it does with many.
- Option values are computed in the pipeline and passed in finished; the render layer
  MUST NOT sort, rank, or compute (rebuild §11.4). Option lists MUST be deterministic
  for identical inputs.

---

## 4. Mockup parity

### 4.1 Card chrome **[Changed — rebuild §13.2 "Typography and layout"]**

The mockup wraps every table and panel in one recipe:

```css
background: var(--card); border: 1px solid var(--border); border-radius: 10px;
```

That recipe MUST be applied to: the table scroll container (every table on the site MUST
sit inside one — the What If? standings table and the rules table are bare today), the
What If? standings panel, notices, locked-state notices, per-player `<details>` cards, and
the odds chart wrapper.

Further table rules ported from the mockup:

- Sticky header cells MUST use the card background, not the page background, so they match
  the container they sit in.
- `th` is muted and semi-bold; `th, td` do not wrap.
- `tfoot td` is bold with a 2px top rule and no bottom rule.
- Divider rows (the "outside the top 10" row) are uppercase with `.06em` letter-spacing.

The site's existing alignment convention — left by default, `.num` opts into right with
tabular figures — is kept. The mockup's inverse (`.t` opts into left) is **not** adopted;
it would touch every template for no visible gain.

### 4.2 Headings

Section headings MUST use the mockup's emoji and wording, in full:

| Page | Heading |
|---|---|
| Leaderboard | 🏆 Projected Standings / 🏆 Current Standings (unchanged) |
| Leaderboard | 📋 All Players' Lists |
| Leaderboard | 👤 Per-Player Detail *(was "Players")* |
| Leaderboard | 🎞️ Films |
| What If? | 🎬 What If? (unchanged); sub-panel "If it ends this way…" (unchanged); **h2** "Points by film, for this order" *(was h3 "Points by film")* |
| Winning Scenarios | 🔮 Winning Scenarios (unchanged) |
| Odds Over Time | 📈 Odds Over Time (unchanged) |
| Scoring rules | 📜 Scoring rules |

Nav pill labels (rebuild §11.2) already match the mockup and are unchanged.

### 4.3 Snapshot

`tests/fixtures/snapshot_index.html` is byte-exact and will change. It MUST be regenerated
once, the diff reviewed by eye for the changes above and nothing else, and committed with
the implementation.

---

## 5. What If? reordering **[Changed — rebuild §12.2 drag and touch paragraphs]**

### 5.1 Library

The hand-rolled HTML5 drag/drop and press-and-hold touch code is removed. Reordering uses
**SortableJS 1.15.6** (MIT), the one third-party client dependency rebuild §13.1 permits.

- The minified source MUST be vendored at `smw/render/static/sortable.min.js` and inlined
  into `whatif.html` like the site's own scripts. It MUST NOT be loaded from any remote
  origin.
- The vendored file's licence banner MUST keep the copyright and licence line and MUST
  contain no URL, so the existing no-external-origins test continues to guard the page
  without an exception.

### 5.2 Behaviour

```js
new Sortable(list, {
  animation: 150,                     // rows slide out of the way during the drag
  ghostClass: "dragging",
  delay: 150, delayOnTouchOnly: true, // rebuild §12.2 touch rule, unchanged in intent
  touchStartThreshold: 4,
  filter: "button", preventOnFilter: false,   // ▲ ▼ still click
  onEnd: /* read the new order from the DOM; rescore */
});
```

- While a row is being dragged, the rows it passes MUST visibly move to their new slots
  **before** the pointer is released.
- On drop the standings panel and points grid MUST recompute exactly as they do today.
  Sortable moves the `<li>` itself; slot numbers are CSS counters (rebuild §12.2) and
  renumber for free, so the list MUST NOT be rebuilt on drop.
- The ▲ / ▼ keyboard path, focus return, Reset button, cutoff line, dimming of slots
  11+, live region, and competition ranking are all unchanged (rebuild §12.2).
- The dragged row's ghost is rendered at reduced opacity; list items set
  `touch-action: pan-y` and `user-select: none`.

---

## 6. Acceptance criteria

Each criterion is testable from a build of `data/seasons/` fixtures with the chart fetch
monkeypatched, as the existing build tests do.

1. A season with two groups builds to `<out>/<year>/<group_a>/` and
   `<out>/<year>/<group_b>/`, each containing the five pages and `data.json`, and each
   `index.html` carries its own group's `display_name`.
2. `<out>/index.html` exists and redirects to `<newest year>/<default_group>/index.html`;
   with `default_group` unset it targets the lexically first `group_id`.
3. A `default_group` that names no roster fails season loading with `ValueError`.
4. A season directory whose name differs from `season.yaml`'s `year` fails loading.
5. A production (non-`--local`) run with a live forecast appends to
   `data/seasons/<year>/forecast_history/<group_id>.jsonl` for each group and nothing
   else; a local run appends nothing. `box_office_history.jsonl` is still appended once
   per season, not once per group.
6. Every page's `<h1>` is `🍿 Summer Movie Wager`; `<title>` follows Section 3.1.
7. Every page contains a year `<select>` and a group `<select>`; the group select lists
   every group of that season with the current one selected; option `value`s follow the
   targets in Section 3.2 and are page-relative.
8. Every table on every page is inside a `.table-scroll` container carrying the card
   recipe; sticky header cells use `var(--card)`.
9. The headings in Section 4.2 appear verbatim.
10. `whatif.html` contains `new Sortable(` and does not contain `dragstart`,
    `touchstart`, or `elementFromPoint`.
11. The existing self-containment tests (no external origins, no `fetch(`, no
    `XMLHttpRequest`) pass on every page of every group unchanged, including the page
    carrying the vendored library.
12. Two builds from identical inputs and `--date` produce byte-identical output for every
    file under `<out>/`, including the root redirect.
13. The regenerated `snapshot_index.html` differs from the previous fixture only in
    masthead, selectors, card chrome, and headings — not in any number, ordering, or
    roster content.
14. `AGENTS.md`'s "Persisted data" line and `README.md` are updated to the Section 2.1
    layout, and the data files are moved with `git mv` so history follows them.

---

## 7. Deliberately not done

- **No client-side switching.** Embedding every group's data in one page and swapping
  in JavaScript would duplicate every view model in the browser and violate rebuild
  §11.4. Static directories plus a native `<select>` is the whole mechanism.
- **No per-group theming, ordering, or cross-group comparison** (rebuild §3.6 second
  and third bullets stand).
- **No alignment convention change** (Section 4.1).
- **No hiding of single-option selectors.**
- **No new persisted refresh/run-date record.**
