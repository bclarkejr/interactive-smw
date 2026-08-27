# Summer Movie Wager — UX Refresh

**Amendment to the standalone rebuild specification: multi-season, multi-group site
layout; mockup-parity presentation; animated What If? reordering.**

Version 1.1 · 2026-08-27

---

## 0. How to read this document

This document amends `superpowers/specs/2026-08-15-standalone-rebuild-spec.md` (the
"rebuild spec"). Everything in the rebuild spec remains in force except where a section
below says **[Changed]** and names the rebuild-spec section it replaces. Section
references of the form "rebuild §N.M" point at that document; unqualified references point
at this one.

Requirements use RFC-2119 language: **MUST**, **MUST NOT**, **SHOULD**, **MAY**.

Section 1 states the problems. Section 2 defines seasons and groups, Section 3 makes the
mockup normative, Section 4 adds the selectors, Section 5 the reordering. Section 6 lists the
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
  and it is what keeps the year selector (Section 4) consistent without a separate
  index step.
- A season whose window is not live on the run date (frozen, or not yet open) is
  rendered but MUST persist nothing: no box-office or forecast rows are appended for
  it, and its odds axis gains no refresh date. Only the live season's files change on
  a production run.
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

## 3. Presentation — the mockup is normative **[Changed — rebuild §12.1–12.4 presentation details, §13.2]**

`brainstorming/mockup.html` is the design. Where this section and the mockup disagree,
the mockup wins; where the mockup and the rebuild spec disagree on presentation, the
mockup wins. The mockup's sample data and its single-file section switcher are not part of
the design; everything else is.

### 3.1 Stylesheet

- `smw/render/static/site.css` MUST be the mockup's `<style>` block (mockup lines 12–144)
  verbatim, with exactly three exclusions:
  1. `.mocknote` (the mockup's own banner);
  2. `.page` / `.page.active` (the single-file section switcher);
  3. the six hard-coded `--s-<username>` custom properties in each of the three token
     blocks.
- Below the verbatim block, `site.css` MAY contain exactly one appended section headed
  `/* ---------- site additions ---------- */` holding only:
  1. the alphabetical `.series-N` binding (rebuild §12.4): `.series-0` … `.series-5`
     take the mockup's six light and six dark colours **in the mockup's order**;
     `.series-6` and `.series-7` keep the shipped site's two extra colours (a group may
     have up to eight players). Defined in the same three places as the other tokens.
  2. the selector styling from Section 4 (`.sel`) and its visually-hidden label rule
     (`.vh`).
  Nothing else may be added, and nothing in the verbatim block may be edited.
- Consequently the site's token vocabulary becomes the mockup's: `--bg --surface --ink
  --ink2 --muted --grid --baseline --border --affirm --neg --accent --pill --hl`, plus
  `color-scheme` on each theme block. The old tokens (`--card --dim --pos --gold`) go
  away; no rule may reference a token the mockup does not define.
- A test MUST assert that `site.css`, after stripping the three exclusions from the
  mockup and normalising whitespace, is identical to the mockup's style block. This is
  the mechanical definition of "match the mockup".

### 3.2 Theme script

`theme.js` MUST be the mockup's head script (line 9) plus its toggle handler (lines
612–619) minus the `renderChart()` call: storage key `smw-theme`, `data-theme` on
`<html>`, resolution before body paint (rebuild §13.2). Series colours are theme-scoped
CSS variables, so nothing needs re-rendering on toggle.

### 3.3 Page skeleton

Every page MUST use the mockup's skeleton and class names:

```
div.wrap
  header.site
    div
      h1                       🍿 Summer Movie Wager
      div.sub                  Wager window: {window} · <span.small>Refreshed {date}</span>
                               + the year and group selectors (Section 4)
    button#themeToggle         ◐ Theme
  nav.pills                    the four pills (rebuild §11.2), aria-current on the active one
  <page content>
  footer.site                  Raw numbers: data.json · Scoring rules ·
                               <span.small>Forecast: {trials} seeded Monte Carlo seasons over {n} projected films.</span>
```

- Dates in `.sub` are formatted as in the mockup: `May 1 – Sep 7, 2026`, `Aug 15, 2026`.
- The footer's forecast sentence MUST reflect the build: `monte_carlo_trials` formatted
  with thousands separators and the count of films with a non-zero projection. When no
  forecast exists the sentence reads `Forecast: unavailable — {reason}.`
- Every `<table>` on the site MUST be wrapped in `div.scroller`; inside a `details.acc`
  the wrapper carries `style="border:none"` as the mockup does.
- Cells are right-aligned by default; text columns opt into `th.t` / `td.t`. The site's
  former `.num` convention is removed.
- Semantic cell classes are the mockup's: `.pos` (positive points), `.zero` (rostered, 0
  pts), `.dash` (not picked / no value, glyph `—`), `.up` / `.down` (▲ / ▼ deltas),
  `.badge`, `.hlcol`, `td.mid` (scenario grid zero, glyph `·`), `tr.divider`,
  `tfoot tr.odds`, and `.crown` (CSS-generated ` 👑`).

### 3.4 Leaderboard (`index.html`) **[Changed — rebuild §12.1 presentation]**

In this order, with this copy:

1. `h2` **🏆 Projected Standings** (or **🏆 Current Standings** in current-points mode,
   rebuild §10.3). `div.scroller > table#matrix`: columns `#`, `Movie` (`.t`),
   `Projected (in-window)`, then one column per player ordered by simulated median.
   Rows: top `matrix_rows` films; a `tr.divider` "Outside the top 10" after row 10.
   `tfoot`: `Projected pts` row (arithmetic sum of the column, rebuild §12.1) and a
   `tr.odds` `Win odds` row formatted `64.2%`. Below it, `p.small`: *"Rows: top 15 films
   by projected median in-window gross. Cells are each film's projected points for that
   player; grey 0 = on their roster but outside the projected top ten, — = not picked.
   Columns are ordered by simulated median points."* (15 is `matrix_rows`.)
2. `h2` **📋 All Players' Lists**. `div.scroller > table#lists`: `Slot` column then one
   `.t` column per player; rows `Pick 1` … `Pick 10`, a `tr.divider` "Dark horses", then
   `🐴 1` … `🐴 3`.
3. `h2` **👤 Per-Player Detail**. One `details.acc` per player, summary
   `{username} <span.stats> — {proj} pts projected · {curr} current · {win}% win</span>`,
   containing a borderless `.scroller` table with columns `#`, `Movie` (`.t`),
   `Projected rank`, `Diff`, `Projected gross`, `Pts`; ten ranked rows, a `tr.divider`
   "Dark horses", three `🐴` rows. `Diff` is `▲ n` / `▼ n` / `–`; an unprojected film shows
   `—` and a `no projection` badge.
4. `h2` **🎞️ Films**. A single `details.acc` whose summary is *"Show all tracked films
   <span.stats>({n} films · projections, ranges, provenance)</span>"*, containing a
   borderless `.scroller` table with columns `#`, `Movie` (`.t`), `Released`, `Status`
   (`.t`, as a `.badge`), `Projected median (in-window)`, `80% range`, `Cumulative`,
   `Source` (`.t.small`). Money formats as in the mockup: `$498.0M`, `$1.02B`; the range
   reads `$431.0M – $563.2M` or `$188.0M (final)`; missing values are `—`.

### 3.5 What If? (`whatif.html`) **[Changed — rebuild §12.2 presentation]**

- `h2` **🎬 What If? sandbox**; `p.sub` *"Drag the films into any finish order — or use
  the ▲▼ buttons — and watch every player's score recompute."*
- `div.wi` with `ol.wi-list#wiList` on the left (each `li` = `span.film` + `span.mv`
  with ▲ ▼ buttons, first/last disabled at the ends, `aria-label` "Move {title} up/down
  one slot") followed by `p.small` *"Films outside the projected top 15 can't be dragged
  in and score 0."*; `div.wi-panel` on the right with `h3` **If it ends this way…**, a
  `div[aria-live=polite] > table#wiStandings` (`Place`, `Player` `.t` with `.crown` on
  first, `Pts` `.pos`, `vs proj.`), and `button#wiReset` **↺ Reset to projected order**.
- `h2` **Points by film, for this order**; `div.scroller > table#wiGrid` with `#`,
  `Movie` (`.t`), one column per player, and a `tr.divider` after row 10.
- The cutoff line is the mockup's: 3px dashed bottom border on the tenth item with the
  absolutely-positioned generated label `— top-10 cutoff —` and 22px of reserved margin;
  items 11+ at 55% opacity. Reordering behaviour is Section 5.
- Locked state: `div.locked` with rebuild §11.3's notice.

### 3.6 Winning Scenarios (`scenarios.html`) **[Changed — rebuild §12.3 presentation]**

`h2` **🔮 Winning Scenarios**; `p.sub` *"Pick a player to see the single most-likely
top-10 box-office finish order that crowns them champion — and exactly how everyone's
predictions score against it. Grayed-out players have no realistic path to winning."*;
`div.tabs` of buttons `{username} · {win}%` with `aria-pressed`, disabled with the
mockup's `title` when the player never wins; `div.caption` with rebuild §12.3's caption;
`div.scroller > table` with `#`, `Movie` (`.t`), one column per player ordered by this
scenario's totals (winner leftmost, `.hlcol` on the selected player), zero cells as
`td.mid` `·`, and a `tfoot` `Total` row with `.crown` on the winner.

### 3.7 Odds Over Time (`history.html`) **[Changed — rebuild §12.4 presentation]**

- `h2` **📈 Odds Over Time**; `p.sub` *"Each player's win probability at every
  production refresh. A break in a line means no forecast was produced that week."*
- `div.chartbox` containing the SVG and `div.legend` of `<span><span.sw></span>{name} —
  {v}%</span>` entries in alphabetical player order.
- The SVG MUST use the mockup's geometry and rendering: `viewBox="0 0 920 360"`,
  margins L=52 R=110 T=16 B=34, `width="100%"`, `role="img"` with an `aria-label`
  naming the player count; y gridlines every 10% up to the next decile above the maximum
  observed value with `{n}%` labels; x labels thinned to at most 8, always including the
  most recent date; a baseline at 0%; one path per player, alphabetical, with a gap
  wherever a value is missing, and a 3px-radius marker at every value; direct labels for
  the top four players by latest value, nudged apart by 15px, drawn as a 10×10 swatch
  plus `text.dl`. All geometry and label positions are computed in `chart.py`; the
  template only emits them (rebuild §11.4).
- `div#tipbox` and the mockup's crosshair tooltip script (`history.js`), pointer-only.
- `details.acc` with summary *"Data table <span.stats>(accessible fallback)</span>"*
  wrapping a borderless `.scroller` table: `Refresh` (`.t`) then one column per player,
  cells `64.2%` or `td.dash` `·` for a gap.
- Locked state: `div.locked` with rebuild §11.3's notice.

### 3.8 Scoring rules (`rules.html`)

`h2` **📜 Scoring rules**; the mockup's intro paragraph with the season's window dates
substituted; `div.scroller > table` with header `Ranked pick, vs. the actual top ten`
(`.t`) / `Points` and the mockup's seven rows including `🐴 Dark horse anywhere in the
top ten`; then `p.small` *"Maximum possible score: 13 + 10×8 + 13 + 3 = **109**. Highest
total wins; there is no tiebreaker — tied players share the placement."*

### 3.9 Snapshot

`tests/fixtures/snapshot_index.html` is byte-exact and will change wholesale. It MUST be
regenerated once from the new templates, reviewed by eye against the mockup's leaderboard
section, and committed with the implementation.

---

## 4. Masthead selectors

The one intentional addition to the mockup's header. Two native `<select>` elements sit
at the end of the `.sub` line inside `header.site`'s left `<div>`, year first, each with a
visually-hidden `<label>`, styled with the `#themeToggle` recipe (surface background,
`--border` border, pill radius). They navigate with `onchange="location.href=this.value"`
— no fetch, no state, no library.

| Selector | Options | Selected | Target on change |
|---|---|---|---|
| Year | every season under `data/seasons/`, newest first | the page's season | `../../<year>/<that season's default_group>/index.html` |
| Group | every group in the page's season, by `display_name` | the page's group | `../<group_id>/<current page filename>` |

- The `<h1>` is **🍿 Summer Movie Wager** without the year: the year is in the selector
  beside it. `<title>` MUST be `{page} · Summer Movie Wager {year} · {display_name}`.
- Switching group MUST stay on the same page; switching year MUST land on that year's
  default group's leaderboard.
- A selector with a single option still renders.
- Option values are computed in the pipeline and passed in finished (rebuild §11.4) and
  MUST be deterministic for identical inputs.

---

## 5. What If? reordering **[Changed — rebuild §12.2 drag and touch paragraphs]**

### 5.1 Library

The mockup's HTML5 drag/drop listeners and the shipped site's press-and-hold touch code
are both replaced by **SortableJS 1.15.6** (MIT), the one third-party client dependency
rebuild §13.1 permits.

- The **minified** build MUST be vendored at `smw/render/static/sortable.min.js` and
  inlined into `whatif.html` like the site's own scripts. It MUST NOT be loaded from any
  remote origin, and the page MUST make zero network requests (rebuild §13.1).
- The vendored file's licence banner MUST keep the copyright and licence line and MUST
  contain no URL, so the existing no-external-origins test continues to guard the page
  without an exception.

### 5.2 Behaviour

```js
new Sortable(document.getElementById("wiList"), {
  animation: 150,                       // rows slide out of the way during the drag
  ghostClass: "dragging",               // the mockup's class: 40% opacity
  delay: 150, delayOnTouchOnly: true,   // rebuild §12.2 touch rule, unchanged in intent
  touchStartThreshold: 4,
  filter: ".mv button", preventOnFilter: false,   // ▲ ▼ still click
  onEnd: /* read the new order from the DOM; rescore */
});
```

- While a row is being dragged, every row it passes MUST visibly slide to its new slot
  **before** the pointer is released. This is the whole reason for the library.
- On drop the standings panel and points grid MUST recompute exactly as they do today.
  Sortable moves the `<li>` itself; slot numbers are CSS counters and renumber for free,
  so the list MUST NOT be rebuilt on drop.
- The ▲ / ▼ path (disabled at the ends, focus returned so repeated presses keep walking
  the film), Reset, the cutoff line, dimming of slots 11+, the live region, competition
  ranking, and the shared scoring test vector are all unchanged (rebuild §12.2).

---

## 6. Acceptance criteria

Each criterion is testable from a build of `data/seasons/` fixtures with the chart fetch
monkeypatched, as the existing build tests do.

1. A season with two groups builds to `<out>/<year>/<group_a>/` and
   `<out>/<year>/<group_b>/`, each containing the five pages and `data.json`, and each
   `<title>` carries its own group's `display_name`.
2. `<out>/index.html` exists and redirects to `<newest year>/<default_group>/index.html`;
   with `default_group` unset it targets the lexically first `group_id`.
3. A `default_group` that names no roster fails season loading with `ValueError`.
4. A season directory whose name differs from `season.yaml`'s `year` fails loading.
5. A production (non-`--local`) run with a live forecast appends to
   `data/seasons/<year>/forecast_history/<group_id>.jsonl` for each group and nothing
   else; a local run appends nothing. `box_office_history.jsonl` is still appended once
   per season, not once per group. A production run appends nothing to any other
   season.
6. `site.css` up to the `site additions` marker equals the mockup's `<style>` block
   after removing `.mocknote`, `.page`/`.page.active`, and the `--s-<username>`
   declarations and normalising whitespace; the additions section contains only
   `.series-N` rules and the selector styling from Section 4 (`.sel`) and its
   visually-hidden label rule (`.vh`); `.series-0…5` colours equal the mockup's six,
   in order, in all three token blocks.
7. Every page's `<h1>` is `🍿 Summer Movie Wager`; every page contains a year `<select>`
   and a group `<select>` whose option values follow Section 4 and are page-relative,
   with the current season and group selected.
8. Every `<table>` on every page is inside `div.scroller`; no page uses a class or token
   name that the mockup does not define (`.num`, `.table-scroll`, `--card`, `--dim`,
   `--pos`, `--gold`, `.cell-*`, `.divider-row`, `.stats-line`, `.standings`,
   `#film-list`, `.two-col`, `.tab-row`, `.tab`, `.highlight-col`, `.chart-wrap`,
   `.odds-chart`, `.legend-swatch` are all gone).
9. Every heading, `.sub` / `.small` intro, summary, button, and footer string quoted in
   Sections 3.3–3.8 appears verbatim on its page (with the season's values substituted
   where the text names them), and column headers match the mockup's per table.
10. The odds chart SVG has `viewBox="0 0 920 360"`, the mockup's margins, at most 8 x
    labels including the latest date, a broken path at every gap, and direct labels for
    the top four players.
11. `whatif.html` contains `new Sortable(` and does not contain `dragstart`, `dragover`,
    `touchstart`, or `elementFromPoint`; the vendored library is the minified 1.15.6
    build.
12. The existing self-containment tests (no external origins, no `fetch(`, no
    `XMLHttpRequest`) pass on every page of every group unchanged, including the page
    carrying the vendored library.
13. Two builds from identical inputs and `--date` produce byte-identical output for every
    file under `<out>/`, including the root redirect.
14. `snapshot_index.html` is regenerated once and the leaderboard matches Section 3.4
    structure for structure.
15. `AGENTS.md`'s "Persisted data" line and `README.md` are updated to the Section 2.1
    layout, and the data files are moved with `git mv` so history follows them.

---

## 7. Deliberately not done

- **No client-side switching.** Embedding every group's data in one page and swapping
  in JavaScript would duplicate every view model in the browser and violate rebuild
  §11.4. Static directories plus a native `<select>` is the whole mechanism.
- **No per-group theming, ordering, or cross-group comparison** (rebuild §3.6 second
  and third bullets stand).
- **No hiding of single-option selectors.**
- **No new persisted refresh/run-date record.**
- **No changes to scoring, projection, simulation, or data schemas** beyond the file
  locations in Section 2.1. This amendment is presentation and tenancy only.
- **No deviation from the mockup for taste.** If something in the mockup looks wrong
  during implementation, the fix is a change to `brainstorming/mockup.html` first, then
  to this spec, then to the site.
