# Summer Movie Wager — Tracker & Forecaster

**A complete, self-contained specification for a from-scratch build.**

Version 1.1 · 2026-08-15

---

## 0. How to read this document

This is the whole specification. It assumes no access to any existing codebase, and it
depends on no external service beyond a single public box-office chart. Every rule,
constant, formula, and edge case needed to build the system appears here.

Requirements use RFC-2119 language: **MUST**, **MUST NOT**, **SHOULD**, **MAY**.

Sections 1–3 define what the system is and how it is configured. Sections 4–9 define the
data pipeline. Sections 10–12 define the website. Section 13 defines quality bars.

Where this specification deliberately departs from a predecessor implementation, the
departure is marked **[Changed]** with its rationale, so an implementer can tell an
intentional decision from an oversight.

---

## 1. Purpose and scope

### 1.1 The problem

A group of friends plays a season-long prediction game: before summer begins, each player
submits a ranked list of the ten films they believe will gross the most at the domestic box
office during a fixed window, plus three "dark horse" long shots. At the end of the window
the actual top ten is computed and everyone is scored.

Scoreboards for this game show **current** points — what each player has earned so far.
That is the least interesting number in the game. In mid-July, "carleigh has 53 points"
says almost nothing, because half the slate has not opened and the films that have opened
are still earning. The questions players actually ask are forward-looking:

- If the season ended the way it currently looks like it will end, what would I score?
- What are my odds of winning?
- Which of my picks is carrying me, and which is dead weight?
- What would have to happen for me to win?

### 1.2 What this system does

It answers those four questions and publishes the answers as a small static website.

For every film that could plausibly finish in the top ten, the system estimates a
**median final in-window gross** and an **uncertainty** around it. It then runs a Monte
Carlo simulation over those estimates: ten thousand synthetic seasons, each one ranked and
scored against every player's picks. Aggregating those trials yields per-player win
probabilities, projected final scores with prediction intervals, and — for each player — the
single most representative season in which they win.

### 1.3 Design posture

Four commitments shape every decision below.

**Honest defaults over speculation.** No projection is invented for a film without either
real box-office data or a sourced analyst estimate. Where the system does not know
something, it MUST say so in the interface rather than filling the gap with a plausible
number. Confident wrong numbers erode trust in the parts of the system that are
well-grounded.

**No server, no build step.** A batch process runs on demand, writes static HTML into an
output directory, and exits. There is no database, no API, no accounts, no frontend
toolchain. This is a site for a handful of people that must keep working with zero
maintenance.

**Self-contained pages.** A published page MUST make no network request of any kind. No
CDN scripts, no external stylesheets, no remote fonts, no runtime data fetch. All CSS and
JavaScript are inlined at build time.

**Reproducible output.** Given identical inputs, two builds MUST produce byte-identical
HTML. The simulation is seeded; nothing depends on wall-clock time except the explicitly
passed run date.

### 1.4 Out of scope

- **Play-along for other groups.** Section 3 requires the architecture to *permit* it —
  configuration instead of constants, a clean split between roster-independent and
  roster-dependent work — but no play-along user experience is designed here. No URL
  scheme, no onboarding flow, no pick-entry form.
- **Accounts, authentication, and write paths.** Picks are locked before the season and
  edited by hand in a version-controlled file.
- **Live or intraday refresh.** The source chart updates once daily; the site refreshes
  roughly weekly.
- **Any sport, league, or contest other than this one.**

### 1.5 Relationship to the original scoreboard

The game's rules originate with a public scoreboard site that hosts the canonical version
of this contest and offers a "play-along" mode exposing any group's picks. The system
specified here is **independent of that site**. It does not fetch from it, does not parse
it, and does not require it to be reachable. The scoring rules are reproduced in full in
Section 2 and are restated on the site itself, so no outbound link is needed.

One historical note matters only if seeding a new deployment from an existing data file:
early box-office history rows in such a file may have been captured from that scoreboard
rather than from the chart specified in Section 4, and the two sources disagree by a
fraction of a percent. Section 4.6 explains the consequence.

---

## 2. The game

### 2.1 Roster shape

Each player submits, before the window opens:

- **Ranked picks** — exactly **10** film titles, in predicted finish order, position 1
  through position 10.
- **Dark horses** — exactly **3** film titles, unordered.

All **13** titles MUST be distinct. A roster violating any of these constraints MUST be
rejected at load time with an error naming the player and the violation.

Rosters are locked when the window opens and MUST NOT change during the season.

### 2.2 Determining the actual finish

At any moment, the **actual top ten** is the ten films with the highest cumulative
**domestic gross earned during the wager window**, ranked descending, position 1 through
position 10.

Two qualifiers, both load-bearing:

- **Domestic only.** Worldwide gross is irrelevant.
- **In-window only.** Only money earned between `window_start` and `window_end`
  inclusive counts. A film released before the window contributes nothing; a film still
  in theaters after the window stops accruing at `window_end`.

### 2.3 Scoring a ranked pick

For each of a player's ten ranked picks, let `predicted` be its 1-indexed position on their
list and `actual` be its 1-indexed position in the actual top ten, or absent.

| Condition | Points |
|---|---|
| Not in the top ten | **0** |
| Exact match at position 1 or position 10 | **13** |
| Exact match at positions 2 through 9 | **10** |
| In the top ten, off by exactly 1 position | **7** |
| In the top ten, off by exactly 2 positions | **5** |
| In the top ten, off by 3 or more positions | **3** |

Reference implementation:

```
function ranked_pick_points(predicted, actual):
    if actual is absent:            return 0
    distance = abs(predicted - actual)
    if distance == 0:               return 13 if actual in (1, 10) else 10
    if distance == 1:               return 7
    if distance == 2:               return 5
    return 3
```

The endpoint bonus is the game's signature: calling the summer's biggest film, or correctly
identifying which film scrapes into tenth, is worth more than being right in the crowded
middle.

### 2.4 Scoring a dark horse

Each dark horse that finishes in the top ten scores **1** point. Position within the top
ten is irrelevant — a dark horse at #1 and a dark horse at #10 both score 1. A dark horse
outside the top ten scores 0.

Maximum dark-horse contribution is therefore 3 points.

### 2.5 Total score, and the score breakdown

A player's total is the sum of their ten ranked-pick points and their three dark-horse
points. The theoretical maximum is `13 + 10×8 + 13 + 3 = 109`.

The system MUST also compute a **score breakdown**: an array indexed by *actual finish
position*, where element `i` holds every point that the film finishing at position `i+1`
contributes to that player. This is the inverse of the natural indexing and it is the
right one, because the interface's central question is "what is this film worth to this
player."

```
function score_breakdown(picks, top_titles):
    require len(top_titles) <= 10
    position_of = { title: i+1 for i, title in enumerate(top_titles) }
    breakdown = [0] * len(top_titles)

    for predicted, title in enumerate(picks.ranked, start=1):
        pos = position_of.get(title)
        if pos: breakdown[pos-1] += ranked_pick_points(predicted, pos)

    for title in picks.dark_horses:
        pos = position_of.get(title)
        if pos: breakdown[pos-1] += 1

    return breakdown

function score_player(picks, top_titles):
    return sum(score_breakdown(picks, top_titles))
```

Two invariants the implementation MUST hold:

- `sum(score_breakdown(p, t)) == score_player(p, t)` for all inputs.
- A `top_titles` list longer than 10 MUST raise. A list **shorter** than 10 is legal and
  scores only the positions present — this is the normal case early in a season, when
  fewer than ten films have grossed anything.

### 2.6 Winning, and ties

The player with the highest total wins. **There is no tiebreaker.** Tied players share the
placement.

This has a direct modeling consequence: the system MUST report **P(strict win)** and
**P(tie for first)** as two separate quantities and MUST NOT merge them into a single
"win probability." Collapsing them would silently invent a tiebreaking rule the game does
not have.

---

## 3. Configuration and tenancy

### 3.1 Why this section exists

The system as described could be written with the season dates, the player list, and every
threshold as module-level constants. It MUST NOT be. Two forces argue against it:

1. A season ends. The next one has different dates and a different slate.
2. The plausible next feature is letting other groups play along — many rosters scored
   against one shared set of films.

Both are cheap to accommodate now and expensive to retrofit, because constants leak into
every module that touches a date and every function signature that takes a roster.

**This section specifies the shape that keeps those doors open. It does not specify
play-along itself.**

### 3.2 `Season`

A single configuration object, loaded from a file, carrying everything that varies between
seasons or that an operator might want to tune.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `year` | int | — | Chart year to fetch |
| `window_start` | date | — | First day of the wager window, inclusive |
| `window_end` | date | — | Last day of the wager window, inclusive |
| `min_projections_for_forecast` | int | `25` | Non-zero projections required before the site forecasts at all (Section 9.5) |
| `chart_contenders` | int | `25` | How many top chart rows are admitted to the film catalog beyond picked titles (Section 6.2) |
| `matrix_rows` | int | `15` | Films shown in the leaderboard matrix and the What If? sandbox |
| `monte_carlo_trials` | int | `10000` | Simulation trials |
| `seed` | int | — | Simulation seed; fixed so builds are reproducible |
| `default_wow` | map | `{wide: 0.55, animated_family: 0.65}` | Category decay defaults (Section 7.2) |
| `preopening_run_weeks` | int | `10` | Assumed theatrical run length for pre-release WoW derivation (Section 7.4) |

Every module that today would hard-code a window boundary or a threshold MUST instead
receive `Season`. There MUST be no module-level date or threshold constant anywhere in the
projection, simulation, or render layers.

For the 2026 season the values are `year=2026`, `window_start=2026-05-01`,
`window_end=2026-09-07`.

**On `window_start`.** It is the first Friday of May, not the last day of April. A film
opening April 30 does not score, and the boundary must be exact — an off-by-one here
silently admits or excludes a wide release and corrupts the entire top ten.

**On `window_end`.** Labor Day. Section 6.4 specifies an operational deadline that follows
from it and that has no recovery path if missed.

### 3.3 `Group`

A roster, separated from everything else.

| Field | Type | Meaning |
|---|---|---|
| `group_id` | string | Stable slug, safe for use as a directory name |
| `display_name` | string | Human-readable name for headings |
| `players` | map of username → `PlayerPicks` | The rosters |

`PlayerPicks` carries `username`, `ranked` (exactly 10 titles), and `dark_horses` (exactly
3 titles), validated per Section 2.1.

### 3.4 `MovieCatalog`

The roster-independent product of the pipeline: resolved grosses, normalized film records,
and projections. Depends on `Season` alone.

### 3.5 Pipeline shape

```
Season ──> ingest ──> normalize ──> project ──> MovieCatalog
                                                     │
                          ┌──────────────────────────┼──────────────────────────┐
                          v                          v                          v
                   Group A: score,            Group B: score,            Group C: …
                   simulate, render           simulate, render
```

Requirements:

- The expensive, network-bound, roster-independent half MUST run **once per build**, not
  once per group. Fetching a chart and fitting decay curves does not depend on who picked
  what.
- `score`, `simulate`, and `render` MUST take `(Season, Group, MovieCatalog)` as
  parameters. They MUST NOT read global state.
- `render()` MUST take an output directory as a parameter.
- **No type may carry film data and roster data together.** A combined
  "snapshot of everything" type is the single change that makes multi-tenancy a rewrite
  rather than a loop, because it threads through every downstream function signature.

**[Changed]** A predecessor implementation carried exactly such a combined type, holding
rosters, grosses, and a third party's reported points in one frozen object passed to the
leaderboard builder, the player-detail builder, and the history writer. It is dissolved.

### 3.6 Explicitly deferred

- **Multi-group URL routing.** With one group configured, output goes to the output root
  exactly as a single-tenant site would. Multi-group output layout is an open question to
  answer when the feature is designed, not now.
- **Any pick-entry mechanism.** Rosters are hand-edited YAML.
- **Cross-group comparison.** Groups are independent; nothing joins them.

---

## 4. Data source and ingest

### 4.1 The one external dependency

Cumulative domestic gross comes from **Box Office Mojo's yearly chart**:

```
https://www.boxofficemojo.com/year/{year}/
```

This is the system's only network dependency. It is fetched once per build over HTTPS
with a 30-second timeout and parsed as HTML.

**Why the yearly chart and not a daily page.** The yearly chart carries roughly 200 rows,
running well down the tail; a daily page carries only films still reporting daily numbers,
which is a few dozen and systematically excludes exactly the films this system needs — a
mid-budget pick that has faded, or a small film someone took a flyer on. The yearly chart
also carries release dates, which the window filter requires, and its totals already run
through yesterday.

### 4.2 Parsing rules

These four rules are load-bearing and each one is easy to get wrong in a way that silently
corrupts every downstream number.

**Rule 1 — Read the in-year gross, not the lifetime gross.** The chart carries multiple
money columns. The correct one is the **first** cell matching the "estimatable money"
class, which is the in-year gross. A "Total Gross" column also exists and is *stale or
wrong for films still in release*. A budget column also carries the money class but lacks
the estimatable marker, so the class pair must be matched, not either class alone.

**Rule 2 — Take the title from the anchor.** The title cell contains a link; the link text
is the title. Falling back to the cell's full text picks up annotation markup.

**Rule 3 — Detect re-releases and drop them.** A re-release (anniversary screenings,
festival bookings, repertory runs) is marked by a note element nested inside the title
cell. Such rows appear in the chart with the current year's release date but are not
eligible films. They MUST be flagged and excluded.

*Known limitation, accepted:* the note element is a structural signal, not a semantic one.
If a genuine new release ever carried such a note, it would be dropped. The failure is
visible — the film simply never appears — and Guard B (Section 4.4) catches the catastrophic
version of it.

**Rule 4 — Parse the release date with the chart's year.** Dates appear abbreviated without
a year; stamp the chart year on. A row missing any of title, gross, or release date is
skipped rather than raising, because the chart's footer and header rows partially match.

### 4.3 Window filter

A parsed row is retained if and only if:

```
season.window_start <= release_date <= season.window_end  AND  NOT is_rerelease
```

### 4.4 Ingest guards

Silent empty results are the dangerous failure here — a layout change upstream produces
zero rows, the pipeline computes a perfectly consistent site out of nothing, and it looks
fine. Two guards MUST fail the build loudly.

**Guard A — empty raw chart.** If parsing yields zero rows, raise. The chart is never
empty; zero rows means the fetch failed or the markup changed.

**Guard B — empty windowed chart.** If parsing yields rows but the window filter retains
none, raise, and say so distinctly from Guard A. This is the specific trap where a markup
change introduces a nested element into every title cell, Rule 3 flags every film as a
re-release, and everything is filtered away. The error message MUST name Rule 3 as the
first thing to check.

### 4.5 Chart coverage limit

The chart is capped at roughly 200 rows, giving it a floor — as of mid-2026, around
$468,000. A film grossing less than the current floor does not appear at all.

This is acceptable and MUST be handled rather than fixed: such a film is carried forward
from recorded history at its last observed value and treated as closed (Section 6.3). It
matters only at the very bottom of the pack, far from anything that could reach the top
ten. Section 6.3 specifies a guard that detects the case where this assumption breaks.

### 4.6 A note on mixed-provenance history

If a deployment is seeded with a box-office history file whose early rows came from a
different source than the chart above, the two sources will disagree slightly — on the
order of a fraction of a percent on a $250M film. The consequence is that **every film has
exactly one anomalous week-over-week delta at the provenance boundary**, some inflated,
some flat.

This affects only the observed-decay blend of Section 7.3, is diluted as later snapshots
accumulate, and self-heals entirely once six same-source snapshots exist. A fresh
deployment never encounters it. It is documented here only so that a future reader finding
one weird week in the data does not go looking for a bug that is not there.

---

## 5. Data model

All persisted data is plain text in a version-controlled directory. There is no database.
Every schema below MUST be validated at the boundary — bad data fails at load, not deep in
the arithmetic.

### 5.1 Season configuration — `season.yaml`

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

### 5.2 Rosters — `groups/<group_id>.yaml`

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

**[Changed]** A predecessor implementation obtained rosters by scraping a third-party
site and validating the scrape against a locally committed snapshot, failing the build on
any drift. With the scrape removed, the local file **is** the source of truth. The drift
guard, the scraper, and its committed HTML fixture all disappear — roughly three hundred
lines of code and a third of a megabyte of test fixture, replaced by a schema-validated
file read.

Titles here MUST match catalog titles exactly. Section 6.5 specifies the alias mechanism
for when they don't.

### 5.3 Pre-release estimates — `preopening_projections.yaml`

The primary file an operator maintains through a season.

```yaml
"Toy Story 5":
  release_date: 2026-06-19
  opening_weekend_estimate: 168_000_000
  total_domestic_estimate: 559_000_000
  confidence: med            # high | med | low
  source: "Box Office Theory"
  as_of: 2026-04-23
  notes: ""
```

Underscore digit separators as shown are YAML 1.1 syntax; the loader MUST support them
(PyYAML does — YAML 1.2 parsers read them as strings), or the figures must be written as
plain digits.

`confidence` maps to uncertainty per Section 7.4. Guidance: `high` = a tight published
tracking range; `med` = moderate spread or a single source; `low` = no professional
tracking, operator judgment.

An entry is **complete** only if `opening_weekend_estimate`, `total_domestic_estimate`, and
`confidence` are all present and the two dollar figures are positive. A partial entry MUST
be treated as no entry (Section 7.5).

### 5.4 Film corrections — `movies_overrides.yaml`

A patch file for classification and for upstream data problems.

```yaml
"Toy Story 5":
  category: animated_family

"Variant Title As Printed Upstream":
  alias_of: "Canonical Title"

"Film With A Bad Release Date":
  release_date: 2026-07-10
  status: pre_release
```

All four keys are optional per entry: `category`, `alias_of`, `release_date`, `status`.

### 5.5 Box office history — `box_office_history.jsonl`

Append-only, one JSON object per line, one line per film per production run.

```json
{"movie": "The Devil Wears Prada 2", "date": "2026-05-04", "cumulative_gross": 76747075.0}
```

Written for every film in the resolved grosses — every in-window film on the chart plus any
film carried forward. A picked film with no gross yet is never written; there is nothing to
write.

This file has two jobs: it feeds the observed-decay blend of Section 7.3, and it is what
lets a film that has dropped off the chart keep its final gross instead of going dark.

At load, same-date rows for a film MUST be deduplicated, keeping the maximum. A same-day
re-run (Section 6.4) can therefore never inflate a film's snapshot count or skew the
observed-decay weight of Section 7.3.

### 5.6 Forecast history — `forecast_history.jsonl`

Append-only, one line per player per production run. Drives the odds-over-time chart.

```json
{"date": "2026-06-29", "player": "vivrad", "win_prob": 0.0087,
 "median_final_pts": 43.0, "p10": 35.0, "p90": 54.0}
```

Written only when a forecast exists. A degraded run appends nothing, which produces a gap
in the chart's line — the correct rendering, per Section 12.4.

### 5.7 Published state — `data.json`

The full pipeline state, written alongside the HTML so anyone can inspect raw numbers.

```jsonc
{
  "captured_at": "2026-08-15",              // run date
  "current_points":  { "emsullivan": 63, "brettfern": 54, … },
  "forecast_available": true,
  "non_zero_projections": 37,

  "projections": [
    { "movie_title": "Young Washington",
      "median_in_window_gross": 47155963.77,
      "sigma": 0.10,
      "floor": 46951657.0 }
  ],

  "win_prob":         { "emsullivan": 0.9685, "carleigh": 0.0, … },
  "tie_prob":         { "emsullivan": 0.0, … },
  "median_final_pts": { "emsullivan": 63.0, … },
  "p10_final_pts":    { "emsullivan": 56.0, … },
  "p90_final_pts":    { "emsullivan": 63.0, … },

  "winning_scenarios": {
    "emsullivan": {
      "films":   ["Spider-Man: Brand New Day", "The Odyssey", … ],   // exactly 10
      "grid":    { "emsullivan": [5,10,5,0,10,3,10,10,3,7], … },     // 10 ints per player
      "totals":  { "emsullivan": 63, "brettfern": 54, … },
      "win_pct": 96.9,                                               // percent, 0–100
      "margin":  9                                                   // winner minus runner-up
    },
    "carleigh": null                                                 // no winning path
  },

  "forecast_unavailable_reason": "…"        // present only when forecast_available is false
}
```

**Requirement.** When `forecast_available` is false, the six forecast keys MUST still be
present, each as a map of every username to `null`. They MUST NOT be omitted. A consumer
must be able to distinguish "we ran and there is no forecast" from "this key is missing."

**[Changed]** Two keys from a predecessor are gone: `site_reported_points`, which held a
third party's figures, and `computed_current_points`, which is renamed `current_points`
now that there is only one notion of current points.

---

## 6. Resolving grosses

Between the chart and the projection models sits a merge step that is small, entirely
rule-driven, and encodes the whole end-of-season protocol. It gets its own section because
every rule in it exists to prevent a specific, observed failure.

### 6.1 The resolution algorithm

```
cutoff       = min(today, season.window_end + 1 day)
chart_usable = (today - 1 day) <= season.window_end

grosses = {}

# 1. Every title ever recorded, at its best value on or before the cutoff.
for title, observations in history:
    in_range = [gross for (date, gross) in observations if date <= cutoff]
    if in_range:
        grosses[title] = max(in_range)

# 2. The live chart, if it is still meaningful, merged in by max().
if chart_usable:
    for title, row in chart:
        grosses[title] = max(row.cumulative_gross, grosses.get(title, 0))

carried = { title for title in grosses if title not in chart }
```

Four rules, each with a reason:

**Highest, not latest.** Cumulative gross is monotonically non-decreasing in reality. If a
recorded value ever exceeds a later one, the later one is wrong — a bad scrape, a revised
estimate, an upstream correction. Taking the max makes the pipeline robust to a single bad
observation instead of poisoning every subsequent projection.

**Merge by max, never overwrite.** A same-day re-run can therefore only improve a figure,
never regress it. This is what makes re-running safe.

**Cutoff at `window_end + 1 day`.** The chart reports through *yesterday*. A run on
`window_end + 1` is the only run that sees exactly the complete window. Observations dated
later are ignored, because they include post-window earnings that do not score.

**`chart_usable` freezes the chart.** From `window_end + 2` onward the chart's values
include post-window money and MUST NOT be read at all. The final numbers come from history.

### 6.2 The film catalog

Not every film on a 200-row chart belongs in the catalog. The candidate set is the union of:

- every title appearing on any roster in any configured group,
- every key in the pre-release estimates file,
- the top `season.chart_contenders` films on the chart by gross,
- every carried-forward title (Section 6.3).

This keeps the catalog at a few dozen films rather than two hundred, while guaranteeing
that no picked film is ever missing.

**Release date precedence:** override file → chart row → pre-release estimates file →
today (if the film has a positive gross) → `window_end`.

**Status inference:**

| Condition, in order | Status |
|---|---|
| Set explicitly in the override file | as specified |
| `release_date > today` | `pre_release` |
| Gross > 0 and absent from the current chart | `closed` |
| Gross > 0 | `in_theaters` |
| Otherwise | `pre_release` |

### 6.3 Carry-forward, and the guard that protects it

A film that drops off the chart keeps its last observed gross and is treated as `closed`.
This is what allows a completed film's final total to keep scoring for the rest of the
season.

The assumption underneath is: *a film only leaves the chart by falling below its floor.*
That assumption has one other failure mode — the film is still on the chart under a
**different title**, because the upstream source renamed it mid-season. Left undetected,
this scores one film in two of the ten slots and corrupts everything.

**Guard C.** If any carried-forward title has a gross **at or above the current chart's
floor**, raise. Such a film is large enough that it must still be on a 200-row chart, so
its absence is definitionally a title mismatch. The error MUST name the offending titles
and print the exact `alias_of` block to add (Section 6.5).

Guard C applies only to runs where `chart_usable` is true. Once the chart is frozen
(Section 6.1), the chart is not read at all: every title is definitionally carried forward,
there is no current chart floor to compare against, and the guard is skipped.

### 6.4 The end-of-season protocol

This is the one part of the system with a hard, unrecoverable deadline. It MUST be
documented in the operator-facing README of any deployment.

- **The final production run MUST happen on `window_end + 1 day`.** That is the single day
  the chart reports exactly through the window's last day.
- Running on `window_end` is too early — it misses the window's final day, typically a
  holiday with substantial grosses.
- Running on `window_end + 2` or later is too late — `chart_usable` is false and the chart
  is ignored by design, freezing the site at whatever the previous run recorded.
- **Before accepting the final run, verify the top titles actually advanced** versus the
  previous run. Identical figures mean the source has not posted the final weekend yet;
  wait and re-run later the same day. Re-running the same day is safe (Section 6.1).
- **If the deadline is missed there is no recovery path in code.** The final figures would
  have to be appended to the history file by hand.

### 6.5 Title aliases

Titles drift. The override file's `alias_of` key resolves it, and it is applied at **two**
distinct points, keyed in both cases on the *variant being renamed away from*:

1. **At chart ingest**, before grosses are resolved. This is the fix for Guard C: key the
   entry on the source's **current** title and alias it to the title already recorded in
   history, so the live row merges with recorded history under one key.
2. **At catalog normalization**, so a roster's or an analyst file's variant spelling finds
   the gross recorded under the canonical title.

---

## 7. Projection

Every catalog film is reduced to three numbers: a **median** expected in-window gross, a
**sigma** (lognormal uncertainty), and a **floor** (gross already banked, which cannot be
lost). Two models produce them, dispatched by status.

### 7.1 Dispatch

| Status | Model | Floor |
|---|---|---|
| `closed` | Final gross, `sigma = 0` | cumulative |
| `in_theaters` | **Mode A** — decay (7.2, 7.3) | cumulative |
| `pre_release`, complete estimate | **Mode B** — analyst (7.4) | 0 |
| `pre_release`, no complete estimate | `median = 0, sigma = 0` | 0 |

### 7.2 Mode A — the decay model

A film in theaters earns a large opening week and then a geometrically decaying tail.

**Category defaults.** Week-over-week multiplier `0.55` for wide live-action releases,
`0.65` for animated and family films — the latter hold up materially better, especially
across summer weekends.

**Day-of-week weights.** Grosses are not uniform across a week. For partial-week
arithmetic, distribute a week's gross Monday through Sunday as:

```
[0.07, 0.10, 0.07, 0.06, 0.22, 0.26, 0.22]      # sums to 1.00
```

Friday/Saturday/Sunday carry 70% of a week. Without this, a film measured on a Thursday
looks like it collapsed and one measured on a Monday looks like a runaway hit.

**Algorithm.**

1. Reject `today < release_date`.
2. Resolve the week-over-week multiplier (Section 7.3) and compute
   `weeks_observed = (today - release_date) / 7`, floored.
3. If `today >= season.window_end`: the film is finished for wager purposes. Return
   `(cumulative_gross, sigma)`.
4. **Back-calibrate week one.** Solve for the week-1 gross that reproduces the *actual*
   observed cumulative under geometric decay:

   ```
   week_1 = cumulative / ( Σ_{k<full_weeks} wow^k  +  wow^full_weeks × partial_fraction )
   ```

   The partial fraction uses day-of-week weights for week one and a uniform `days/7` for
   later weeks. This anchors the whole projection to money actually earned, rather than to
   a modeled opening.
5. **Project forward** to `season.window_end`: finish the current partial week, add whole
   weeks at `week_1 × wow^k`, then prorate the final partial week.
6. Return `(cumulative + projected_remaining, sigma)`.

**Sigma.**

```
weeks_observed >= 6  ->  0.10
weeks_observed <= 0  ->  0.30
otherwise            ->  0.30 - 0.20 × weeks_observed / 6
```

A film that just opened could still double or halve expectations. A film six weeks in has
almost nothing left to earn and its total is nearly known.

**Degenerate case.** A film with `days_since_release == 0` but a positive gross (a
Thursday-preview or same-day situation) treats the cumulative as its week-1 gross and
projects from week two.

### 7.3 Blending observed decay

Once enough snapshots exist for a film, its *own* observed decay beats the category
default.

```
if len(history) < 2:                        return default
deltas = consecutive differences in cumulative gross, sorted by date
ratios = [ deltas[i+1]/deltas[i] for each adjacent pair where both are > 0 ]
if not ratios:                              return default

observed = geometric_mean(ratios)
weight   = min(1.0, (len(history) - 1) / 5.0)
blended  = weight × observed + (1 - weight) × default

return clamp(blended, lower=0.01, upper=1.00)      # [Changed]
```

The effective threshold is **three snapshots** — two snapshots give one delta and therefore
zero ratios. Full weight on observed data arrives at **six snapshots**.

**[Changed] The clamp is new and it is not cosmetic.** Unclamped, a film whose grosses grew
between two consecutive observations produces a ratio above 1, and a geometric mean above 1
compounds *upward* every week from now to `window_end`. A single anomalous pair of
observations — a wide expansion, an awards re-push, a data correction, or the
provenance boundary of Section 4.6 — can therefore project a film to an absurd total and
distort the entire simulated top ten. A week-over-week multiplier above 1.0 sustained for
months is not a thing that happens; clamping at 1.0 costs nothing real and removes an
unbounded failure mode.

**Known ceiling, accepted:** consecutive ratios telescope, so with evenly spaced
observations only the first and last intervals dominate the geometric mean. This is
tolerable; the weekly-cadence requirement of Section 13.4 keeps it small. (Duplicate
same-day rows cannot occur: history deduplicates same-date rows at load, Section 5.5.)

### 7.4 Mode B — the analyst model

For an unreleased film with a complete estimate.

1. If `release_date > season.window_end`, return `(0, 0)` — the film cannot score.
2. **Derive the implied week-over-week multiplier** from the opening-weekend and
   total-domestic estimates. First convert the weekend to a full first week using the
   day-of-week weights of Section 7.2: Friday through Sunday carry
   `0.22 + 0.26 + 0.22 = 0.70` of a week, so `week_1 = opening / 0.70`. The two constants
   MUST stay tied — if the day-of-week weights ever change, this share changes with them.
   Then solve for `w` in:

   ```
   total = week_1 × (1 - w^N) / (1 - w)         where N = season.preopening_run_weeks
   ```

   The right-hand side is strictly increasing in `w` on `(0, 1)`, so bisection converges in
   about forty iterations. If no root exists in `(0, 1)`, fall back to the category default.

   **[Changed]** A predecessor used `w = 1 - opening/total`, which is the closed-form
   solution for an *infinite* geometric series. Real theatrical runs are eight to twelve
   weeks, and assuming infinity biases the derived multiplier low — the model spreads the
   analyst's total over a longer, flatter tail than the film will actually have, which
   understates in-window earnings for films opening late in the window, precisely the
   films whose in-window total is most sensitive to the shape of the curve.

3. **Sum weekly grosses** `week_1 × w^k` **within the window**, from `release_date`
   through `season.window_end`, then cap the result at `total_domestic_estimate`.
4. **Sigma by confidence:** `high → 0.20`, `med → 0.30`, `low → 0.45`.

**Interpreting the output.** The median a Mode B film reports is its **in-window** gross,
which for a late-window release is legitimately far below the analyst's full-run total. A
film opening three weeks before `window_end` might carry a $400M total estimate and a $180M
projection, and both numbers are correct.

**[Changed]** The interface MUST label this column **in-window** gross. A predecessor
labeled it "projected median" without qualification, which made every late-window film look
like a modeling error. The number was right; the label was missing.

### 7.5 No fallback, by design

A pre-release film that is picked but has **no complete estimate** projects to zero and is
badged **"no projection"** in the interface.

There MUST NOT be a comparable-titles model, a genre-average model, or any other heuristic
that manufactures a number from weak signal. A visible "we don't know" is strictly better
than a confident-looking guess, because a guess contaminates the simulation — a fabricated
$300M projection changes every player's win probability — while a zero is honest about what
it is and is plainly visible in the interface.

The build MUST warn, listing every picked film lacking a projection. That warning is the
operator's to-do list.

### 7.6 Display bands

The films table shows an 80% range. It is computed in closed form, not sampled:

```
remaining = max(0, median - floor)
p10 = floor + remaining × exp(-1.2816 × sigma)
p90 = floor + remaining × exp(+1.2816 × sigma)
```

`1.2816` is the standard normal 90th percentile. Applying uncertainty only to `remaining`
mirrors the sampler of Section 9.2, so the displayed band and the simulated distribution
agree.

---

## 8. Category classification

`category` is the single switch selecting between the wide and animated-family parameters
in both projection modes. It comes from the override file, defaulting to `wide`.

**[Changed] The build MUST warn for every picked film with no explicit category.**

In a predecessor deployment the override file contained only its comment header — zero
entries. Consequently every film was `wide`, the `0.65` animated-family branch was
unreachable in production, and a slate whose top ranks included a Pixar sequel and an
animated franchise entry was modeled with a live-action decay curve throughout. The code
was correct; the data was empty; nothing said so.

This is the recurring hazard of a defaulted enum: it fails silently and looks like it is
working. Making the default *visible* costs one warning and turns a silent modeling error
into an obvious data-entry task. The warning MUST list the unclassified titles by name so
an operator can classify them in one pass.

Deployments SHOULD classify every picked film explicitly, including films that genuinely
are `wide`.

---

## 9. Simulation

### 9.1 What it computes

Given `(median, sigma, floor)` per film, the simulator produces per player: **P(strict
win)**, **P(tie for first)**, **median final points**, an **80% prediction interval**, and a
**representative winning scenario**.

### 9.2 Sampling, with a floor

A film in theaters has already banked money that cannot be lost. Uncertainty applies only
to what it has yet to earn.

```
remaining = max(0, median - floor)
sample    = floor + remaining × exp(sigma × Z)          where Z ~ Normal(0, 1)
```

Because `exp()` is strictly positive, **a sample can never fall below the banked floor.**
Pre-release films have `floor = 0` and recover a plain `LogNormal(ln(median), sigma)` draw.

Without the floor, a film sitting on $950M of actual gross would occasionally sample to
$400M, producing nonsense top tens and materially wrong win probabilities late in a season
— exactly when the numbers matter most. This MUST be enforced by a test asserting
`min(samples) >= floor` over a full trial run.

The sampling step MUST be vectorized: one array of shape `(trials, films)`, no per-trial
loop.

### 9.3 Trials

For each of `season.monte_carlo_trials` trials: sample every film, rank descending, take
the top ten, and score every player against that finish order using Section 2.5.

The run MUST be seeded from `season.seed` so that two builds on identical inputs produce
identical output.

### 9.4 Aggregation

```
score_matrix     = (players × trials) integer matrix
max_per_trial    = column-wise maximum
is_top           = score_matrix == max_per_trial          (broadcast)
winners_per_trial = column sums of is_top

for each player i:
    strict_wins  = count( is_top[i] AND winners_per_trial == 1 )
    ties         = count( is_top[i] AND winners_per_trial >  1 )
    win_prob[i]  = strict_wins / trials
    tie_prob[i]  = ties / trials
    median[i], p10[i], p90[i] = percentiles of score_matrix[i] at 50, 10, 90
```

Strict wins and ties are counted separately, per Section 2.6.

### 9.5 Two thresholds, and why they are not the same thing

**[Changed]** A predecessor carried both of the numbers below and they read as redundant
duplication. They are not; they answer different questions and this specification names
them distinctly.

**`MIN_FILMS_FOR_TOP_TEN = 10` — structural.** You cannot rank a top ten out of nine films.
If the catalog has fewer than ten films with any projection, the simulator MUST **raise**.
This is an impossibility, not a policy.

**`season.min_projections_for_forecast = 25` — policy.** With, say, twelve films projected,
a top ten *can* be computed — it is just nearly all of the candidates, so the ranking is
mostly arbitrary and the resulting win probabilities are confident nonsense. Below this
threshold the system MUST **degrade gracefully** (Section 10), not fail.

`25` is a judgment call: enough films that the top ten is a genuine selection rather than
a near-total ordering. It is configurable precisely because it is a judgment call.

When the threshold is not met, the build MUST record a human-readable reason —
`"only 12 films have non-zero projections (25 required for a meaningful top-ten ranking)"`
— and surface it in the interface.

### 9.6 Representative winning scenarios

"You win 4% of the time" invites the obvious follow-up: *what does one of those look like?*

For each player, take their strict-win trials and select the **medoid** — the trial whose
finish order is most similar, on average, to all their other winning finish orders. This
is a real trial, not a synthesized average, so it is always internally consistent.

**Distance metric: Spearman footrule.** Build a rank vector over all catalog films where a
film's value is its 1-based top-ten position, or `11` if it missed. Distance between two
trials is the L1 distance between their rank vectors. Assigning `11` to all absentees means
a film missing from both trials contributes zero, so the metric measures disagreement about
the top ten rather than being dominated by the long tail.

The medoid search is O(W²) in the number of winning trials. It MUST be capped — sample at
most 1500 winning trials, uniformly, before searching. The result is still a genuine
winning trial. Sampling MUST use a per-player derived seed so scenarios remain
reproducible.

For the selected trial, publish: the ten films in finish order; a per-player array of the
points each finishing position contributes; per-player totals; the player's overall win
percentage; and the **margin** — winner total minus runner-up total, always at least 1
since strict wins only.

A player who never wins in any trial MUST get `null`, and the interface MUST show them as
having no path rather than fabricating one.

---

## 10. Season lifecycle

The system MUST work correctly at every point in a season, including before it starts.
This is the requirement that most shapes the interface, and the one an implementation is
most likely to get wrong by building for the mid-season state and treating everything else
as an error path.

### 10.1 States

| State | Condition | Behavior |
|---|---|---|
| **Early** | `non_zero_projections < min_projections_for_forecast` | **Current-points mode** (10.3); forecast pages locked |
| **Live** | `non_zero_projections >= min_projections_for_forecast` | Full forecast; all pages active |
| **Final** | `today > window_end + 1 day` | Grosses frozen; projections collapse to actuals |

**Final takes precedence** — its condition is evaluated first; otherwise the projection
count decides between Early and Live. Transitions are computed per build. A season may move
from Early to Live and, in principle, back; nothing depends on the transition being one-way.

**Pre-season is not a distinct state.** Before opening day there are no grosses and no
history file, but analyst estimates (Mode B, Section 7.4) still produce projections. A
pre-season build with enough complete estimates is simply Live — the forecast runs on
analyst numbers alone — and one without them is Early, showing all-zero actuals. The
day-zero requirements of Section 10.2 apply throughout.

### 10.2 Day-zero requirements

Each of these follows from "must work before the season starts," and each MUST hold:

- A **missing history file** is a warning, not an error. The first run has no history.
- An **empty roster list** renders an empty section, not a crash. Any template computing a
  row count from the maximum length across players MUST supply a default for the empty
  case.
- **Fewer than ten films** in the catalog suppresses the "outside the top ten" divider
  rather than emitting a divider with nothing after it.
- **A picked film absent from the catalog** renders a muted placeholder cell rather than
  trusting an invariant and throwing. Normalization guarantees this cannot happen; the
  interface MUST NOT depend on that guarantee.
- **Zero films with any gross** produces an empty actual top ten, which Section 2.5 already
  supports — every player scores 0.

### 10.3 Current-points mode

This is the specification's central interface requirement.

When there is no forecast, the leaderboard MUST NOT show projections. It MUST show the same
table, in the same shape, populated entirely with **actuals**. The reader's mental model
carries over unchanged; only the provenance of the numbers changes, and every number on the
page is real.

| Element | Live mode | Current-points mode |
|---|---|---|
| Section heading | 🏆 Projected Standings | **🏆 Current Standings** |
| Row order | Projected median gross, descending | **Current cumulative gross, descending** |
| Numeric column | Projected median (in-window) | **Cumulative gross to date** |
| Cell values | Projected points contribution | **Current points contribution** |
| Cell rendering | positive / grey `0` / muted `—` | *unchanged* |
| Top-ten divider | Shown after row 10 | *unchanged* |
| Footer row 1 | Projected pts | **Current pts** |
| Footer row 2 | Win odds | **Omitted entirely** |
| Player stats line | `N projected · N current · N% win` | **`N pts current`** |
| Player detail columns | `#`, Movie, Projected rank, Diff, Projected gross, Pts | **`#`, Movie, Pts** |
| All Players' Lists | Shown | *unchanged* — rosters are locked and forecast-independent |
| Films table | Full, with projections and badges | *unchanged* — including "no projection" badges |

There MUST be **no projected final points and no win percentage anywhere on the page** in
this mode. Not greyed out, not shown as `—` in a column that still exists: absent.

A notice MUST explain why, carrying the reason string from Section 9.5.

**[Changed]** A predecessor kept the matrix populated with *projected* values in this state
and blanked only the win-odds footer row. That is the wrong trade. If the projections are
too sparse to rank a top ten, they are too sparse to headline a table — and putting
unreliable projections in the position of the page's primary numbers, one row above a
notice saying the forecast is unavailable, is contradictory. Actuals are always
trustworthy; the season simply starts by having very few of them.

---

## 11. Site structure

### 11.1 Output

Five HTML files plus `data.json`, written to an output directory served as static files.
No server-side logic, no client-side routing, no build toolchain.

| File | Page |
|---|---|
| `index.html` | Leaderboard |
| `whatif.html` | What If? sandbox |
| `scenarios.html` | Winning Scenarios |
| `history.html` | Odds Over Time |
| `rules.html` | Scoring rules (Section 13.1) |
| `data.json` | Published state (Section 5.7) |

### 11.2 Navigation

A shared pill-style nav appears on every page, in this fixed order:

`🏆 Leaderboard` · `🎬 What If?` · `🔮 Winning Scenarios` · `📈 Odds Over Time`

The scoring rules page (`rules.html`) is footer-linked reference material (Section 12.1)
and does not appear in the nav.

Requirements:

- The current page's pill MUST carry `aria-current="page"` and a distinct visual state.
- **All four pills MUST be real links at all times, in every season state.** A page that
  cannot show content shows its own locked state (Section 11.3).
- The nav MUST wrap rather than scroll on narrow viewports.

**[Changed]** A predecessor rendered the three forecast pages as disabled, non-clickable
elements when no forecast existed. Disabled navigation is a dead end: it tells a reader
that something exists and refuses to explain it. A live link to a page that explains its
own empty state is strictly more useful and removes a conditional from the nav.

### 11.3 Locked states

A forecast page with nothing to show renders a single centered notice in place of its
content, and nothing else.

- **What If?** and **Winning Scenarios** gate on `forecast_available`. Notice: *"Not enough
  films have projections yet to simulate win probabilities — {reason}. This view unlocks
  once the forecast is live."*
- **Odds Over Time** gates on **its own data being empty**, not on `forecast_available`.
  Notice: *"No forecast history yet — this chart fills in after the first production
  refresh."*

**On that asymmetry.** It is deliberate and MUST be preserved. Odds Over Time is the only
page whose content is *historical*. A build that cannot produce a forecast today can still
have a rich chart of forecasts from previous weeks, and blanking it would discard real
information. The other two pages describe the *current* simulation and have genuinely
nothing to show without one. A predecessor implemented this correctly but documented
nothing, so the difference read as an inconsistency for months.

### 11.4 Rendering model

Server-side templating, HTML out. Two rules:

- **The render layer MUST NOT sort, rank, or compute.** Every ordering decision is made in
  the pipeline and passed in. Rendering is a pure function of its input. This is what makes
  a byte-exact snapshot test meaningful.
- **Autoescaping MUST be forced on unconditionally.** It MUST NOT rely on
  extension-based auto-detection, which commonly misses template file suffixes. Film titles
  and source strings come from an external HTML document and are untrusted.

Data embedded into pages as JSON MUST escape `<` as `\u003c` to prevent a title containing
`</script>` from breaking out of its block.

---

## 12. The four pages

### 12.1 Leaderboard (`index.html`)

The primary page. A header carrying the season name, the window dates, and the refresh
timestamp; then four sections.

#### Section 1 — Projected Standings (the matrix)

A **film × player matrix**. This is the page's reason to exist: it answers "which film is
earning whom what" in one glance, which no arrangement of per-player lists can.

- **Rows:** the top `season.matrix_rows` (default 15) films by projected median.
- **Leading columns:** rank `#`, film title, projected median (in-window) gross.
- **Player columns:** one per player, ordered by simulated median points, descending.
- **Cells,** three states:
  - **positive** — the film scores for this player; shown in the affirmative color
  - **grey `0`** — the film is on their roster but projects outside the top ten
  - **muted `—`** — they did not pick it
- **Divider:** after row 10, if any rows follow, a dashed full-width row reading
  *"Outside the top 10"*. This makes the scoring boundary visible and is why the table
  shows fifteen rows rather than ten — a boundary needs content on both sides to mean
  anything, and five rows of "just missed" is useful context.
- **Footer, two rows:** *Projected pts* and *Win odds*. *Win odds* shows **P(strict
  win)**; P(tie for first) is not shown on the page but is published in `data.json`,
  which is how Section 2.6's requirement to report the two separately is satisfied.

**Why 15 rows, fixed.** Showing every film any player picked would exceed twenty-two rows
and make the table's height wobble week to week as rosters' deep picks move. Deep picks
remain visible in that player's own detail table. This is also the slice the What If?
sandbox uses, so the two pages agree on what "in contention" means.

**The footer total rule — do not re-litigate this.** The *Projected pts* footer MUST be the
**arithmetic sum of the cells above it**, NOT the simulated median final points. The two
genuinely differ — a distribution's median is not the median scenario's score, and a gap of
one or two points is normal.

The reason the sum wins: with the components sitting directly above the total, a column
that does not add up reads as a bug to every reader, every time. Column *order* still
follows the simulated median, because that is the ranking the win odds derive from and the
ordering the other two pages use.

The accepted consequence: a column can occasionally display a total one point higher than
the column to its left. Re-sorting columns by the displayed total would desynchronize this
page from the other two — a worse and more frequent inconsistency for a rarer payoff. This
decision MUST be documented as a comment at the point the total is computed.

The same total MUST appear in each player's stats line, so a player's projected score never
differs between two places on one page.

#### Section 2 — All Players' Lists

A **pick-position × player grid**: rows `Pick 1` through `Pick 10`, a `Dark Horses` divider,
then `🐴 Dark Horse 1` through `3`. Every roster side by side, no interaction required.

Rosters are locked and public within the group, so there is nothing to hide behind a click.
Aligned columns make cross-player comparison possible; stacked per-player lists do not.

Row counts MUST be computed defensively so an empty roster set renders an empty section
rather than raising.

#### Section 3 — Per-player detail

A collapsed accordion, one entry per player. Each carries a stats line —
`N pts projected · N pts current · N% win` — and a table:

| Column | Content |
|---|---|
| `#` | Pick position, or 🐴 for dark horses |
| Movie | Title |
| Projected rank | `#N` — position across the **whole catalog**, or `—` |
| Diff | Pick position minus projected rank |
| Projected gross | In-window median |
| Pts | Projected points |

Dark horses follow a `Dark Horses` divider row inside the same table.

**Diff** is the column that turns a static list into a read on how a bet is moving:
`▲ 2` (affirmative) when the projection has the film *above* where the player ranked it,
`▼ 2` (negative) below, `–` when exact. It MUST render a muted `—` rather than doing
arithmetic when the projected rank is unavailable.

**Rank semantics.** *Projected rank* is the film's position across the entire projected
catalog — the same integer the films table prints — not its position within the top ten.
There MUST be exactly one notion of "projected rank" in the system. Scoring is unaffected;
points still come from the top-ten position map.

#### Section 4 — Films

Collapsed behind a toggle. It is reference data, not the headline; expanded, its several
dozen rows bury Section 3.

Columns: `#`, Movie, Released, Status, Projected median (in-window), 80% range, Cumulative,
Source.

**Status badges:** `pre-release`, `in theaters`, `closed`, `won't score`, `no projection`.

**Source strings**, naming each number's provenance: `final gross`, `decay model`,
`analyst estimate`, `release after window`, `no analyst entry`, `—`.

#### Footer

Links to `data.json` and to the scoring rules page (Section 13.1). It MUST NOT link to any
external site.

### 12.2 What If? (`whatif.html`)

An interactive sandbox: drag the top `matrix_rows` films into any finish order and watch
every player's score recompute live.

- **Left column:** an ordered, drag-reorderable list of the top 15 projected films, slots
  numbered by CSS counter.
- **The cutoff line** after slot 10 MUST be pure CSS — a dashed bottom border on the tenth
  item plus a generated label, with items 11 and beyond dimmed. Nothing about the cutoff
  requires JavaScript.
- **Right column:** a sticky standings panel headed *"If it ends this way…"*, one row per
  player with place, name (crowned at first), points, and a movement delta against the
  projected baseline. It MUST carry a polite live region so the recomputation is announced.
- **Below:** the film × player points grid for the current hypothetical order.
- **Reset** restores the projected order.
- **Footnote:** *"Films outside the projected top 15 can't be dragged in and score 0."*

**Keyboard parity is mandatory.** Every list item MUST carry ▲ and ▼ buttons with
descriptive labels that swap it with its neighbor, re-score, and return focus to the button
so repeated presses keep walking the film. Drag-and-drop MUST NOT be the only way to
reorder.

**Touch behavior:** a short press-and-hold delay before a drag begins, applied on touch
only, so vertical page scrolling still works on a phone.

**Ties** in the standings use competition ranking — tied players share a place and the next
place skips accordingly (1, 1, 3) — matching the game's no-tiebreaker rule.

**On the duplicated scoring logic.** This page necessarily reimplements Section 2's scoring
in client-side script. That is a genuine maintenance liability: two implementations of one
rule set will drift. It MUST be mitigated by a **shared test vector** — a small set of
`(roster, finish order) → expected points` cases asserted against both implementations, so
a change to one that is not mirrored in the other fails a test rather than silently
producing two different answers on two pages of the same site.

### 12.3 Winning Scenarios (`scenarios.html`)

For each player, the single most representative season in which they win (Section 9.6).

- **Tabs**, one per player, ordered by win probability descending. Each shows the player's
  name and win percentage. A player with no winning path renders a genuinely disabled
  button showing `0%` and explaining itself on hover.
- **Caption:** *"Most likely finish in which **X** wins the wager 🏆 — X edges the field by
  just N pt; they win ~P% of all sims."*
- **Grid:** rows are the ten films in finish order; columns are players **re-sorted by that
  scenario's totals**, so the winner sits leftmost. Zero cells render as a muted middle dot
  rather than `0`, keeping the eye on what scores. The selected player's column is
  highlighted. The footer prints totals, crowning the leader.

Subtitle: *"Pick a player to see the single most-likely top-10 box-office finish order that
crowns them champion — and exactly how everyone's predictions score against it. Grayed-out
players have no realistic path to winning."*

### 12.4 Odds Over Time (`history.html`)

Each player's win probability at every production refresh.

- **A hand-rolled SVG line chart.** No charting library. The requirement is a few hundred
  lines of path arithmetic; a library would be the page's largest dependency by an order of
  magnitude.
- **Y axis:** zero to the next decile above the maximum observed value, gridlines every
  10%, labeled as percentages.
- **X axis:** refresh dates, thinned to at most eight labels, always including the most
  recent.
- **Lines:** one path per player, round joins and caps, with a marker at each observation.
  **A missing value MUST break the line, not interpolate across it.** A gap means no
  forecast was produced that week; drawing through it would assert a number that was never
  computed.
- **Direct labels** for the top four players by latest value, nudged apart to avoid
  collision, each with a small colored swatch. Label text uses the body ink color; color
  carries identity only, never meaning.
- **Legend** listing every player by latest odds.
- **Table fallback** inside a collapsed disclosure, dates as rows and players as columns,
  with a middle dot for gaps. This is not decoration — it is how a player in a crowded
  bottom cluster reads their own number, and how the page works with a screen reader.
- **Crosshair tooltip** on hover, snapping to the nearest date. *Known gap: this is
  pointer-only. The table fallback is the accessible path; a keyboard-navigable equivalent
  is a worthwhile future addition.*

**Color assignment MUST be stable.** Series colors are bound to players **alphabetically by
username**, never by current rank. A palette that reorders as the standings change makes
the chart unreadable across refreshes — a reader tracking "the green line" would find it
becomes a different person week to week.

The palette provides **eight** distinguishable hues, validated for contrast against both
the light and dark page backgrounds, with separate values for each theme. *Known ceiling:
a group larger than eight would exhaust it and require a documented extension.*

**Data shape:** a sorted list of unique dates, plus one series per player holding a
value-or-null per date, **sorted by username** so the color binding above holds. Where two
runs share a date, the later one supersedes.

---

## 13. Non-functional requirements

### 13.1 Self-containment

A published page MUST issue **zero network requests**. Specifically:

- All CSS inlined at build time. No external stylesheet, no CDN.
- All JavaScript inlined, including any vendored third-party library.
- **No remote fonts.** Either self-host the font as a build-time asset, or use a system font
  stack. A remote font request is still a request, still fails behind a restrictive network,
  and still leaks a referrer.
- No runtime data fetch. Pages carry their data embedded as JSON literals. `data.json` is
  published for humans and downstream tools; **no page fetches it**.
- **The scoring rules MUST be reproduced on the site**, on their own small page
  (`rules.html`, Section 11.1). A deployment MUST NOT link out to a third party for its
  own rules.

There MUST be a test asserting no external-origin references appear in the output.

Third-party client-side dependencies SHOULD number zero or one. A drag-and-drop library is
the only justified case; it MUST be vendored into the repository, never loaded remotely.

### 13.2 Presentation

**Theming.** A token-based light and dark theme, with tokens defined in three places:

1. `:root` — the light palette,
2. an explicit dark attribute selector — set by the toggle,
3. a `prefers-color-scheme: dark` block scoped so it does not override an explicit light
   choice.

This ordering means the OS preference applies before any script runs, and an explicit user
choice always wins over the OS. The choice persists in local storage.

**[Changed] A theme-resolution script MUST run in the document head**, before body content
renders. A predecessor placed it after the toggle button in body order, producing a visible
flash of the wrong theme on every page load for every dark-mode user.

**Typography and layout.** A single family throughout, with tabular figures on every
numeric cell so columns align. The leaderboard needs a wider shell than the other three to
fit the matrix. Wide tables MUST scroll inside their own container; the page body MUST NOT
scroll horizontally. Grid headers SHOULD stick on scroll.

**Responsive behavior.** One breakpoint around 700px, reducing base size and cell padding
and collapsing the What If? two-column layout to one. There is no mobile-specific table
transform; wide tables scroll, which is honest and predictable.

### 13.3 Accessibility

Required:

- `aria-current="page"` on the active nav pill.
- Pressed state on scenario tabs; genuinely disabled buttons for players with no path.
- A polite live region on the What If? standings panel.
- Keyboard reordering on What If? as a full alternative to dragging (Section 12.2).
- The table fallback on the odds chart.
- Descriptive labels on the chart, the theme toggle, and every icon-only control.

Known gaps, to be closed rather than tolerated indefinitely: the chart tooltip is
pointer-only, and some grid state — a highlighted winner column, a zeroed cell — is carried
by color with insufficient redundant encoding.

### 13.4 Operations

- **Manual trigger, no schedule.** A season refresh is an operator action, so that a bad
  upstream day can be noticed rather than committed automatically.
- **Tests run before the build.** A refresh that would publish broken output MUST fail
  first.
- **Weekly cadence, consistent weekday.** The observed-decay estimator of Section 7.3
  assumes roughly weekly spacing; irregular runs skew it. Monday is the natural choice —
  the weekend is fully reported.
- **A local mode** MUST exist that runs the full pipeline and writes the site **without**
  appending to either history file. Every exploratory or development run uses it. A
  development run on an off-cadence day would otherwise append rows that break the roughly
  weekly spacing the decay blend assumes.
- **The end-of-season protocol of Section 6.4 MUST be in the operator README.** It is the
  only irrecoverable failure in the system.
- Generated output is committed, since static hosting serves it directly. Templates and
  stylesheets are the sources; generated files MUST NOT be hand-edited.

### 13.5 Testing

**Principles.**

- **No network in tests.** The chart's HTML is committed as a fixture; every parsing test
  runs against it offline.
- **The rendered leaderboard gets a byte-exact snapshot test.** Regenerating it is a
  deliberate ritual, not a formality: delete the fixture, run once to rewrite it, **open the
  result in a browser and look at it**, then re-run to lock. A snapshot regenerated without
  human inspection tests nothing.
- Data crossing a module boundary is a validated typed model. Bad data fails at the
  boundary.

**Required coverage.**

| Area | Must cover |
|---|---|
| Scoring | Every rung of the ladder, both endpoints, dark horse hit and miss, over-length input raises, partial and empty finish lists, breakdown sums to total |
| Chart parsing | Correct money column, abbreviated dates, header rows skipped, window boundaries on both sides, re-release excluded, genuine release not flagged |
| Gross resolution | Chart preferred, carry-forward, never decreases, out-of-order history, highest-not-latest, same-date duplicate rows collapse to the max at load, the freeze boundary on each side, impossible-carry raises |
| Decay | Category defaults, sigma taper, back-calibration round-trips the observed cumulative, observed blending pulls toward observed, freeze past window end, pre-release date raises, day-of-week fractions |
| Pre-release | After-window scores zero, opening weekend converts to week one via the day-of-week share, long run caps at the analyst total, sigma by confidence, degenerate input falls back to category default |
| Simulation | Determinism under a seed, percentile ordering, per-player `win_prob + tie_prob <= 1`, strict-win probabilities across players plus the fraction of tied trials sum to one, **floor is never breached**, scenario structure, null scenario when a player never wins |
| Rendering | Byte-exact snapshot, top-N cap, divider omitted when nothing follows, diff arrows, escaping of hostile titles, no external references, keyboard controls present, locked states |

**Gaps a from-scratch build MUST NOT reproduce.** These were absent from a predecessor's
otherwise thorough suite, and each guards a rule this document treats as load-bearing:

- **The forecast-gate boundary.** Assert both sides of `min_projections_for_forecast`:
  one below (degrades, no forecast keys populated) and one at the threshold (forecasts).
- **The history writers.** Assert that a production run appends the expected rows and a
  local run appends none.
- **The decay clamp of Section 7.3.** Assert that a history whose grosses grew between
  observations produces a multiplier of at most 1.0 — this is precisely the unbounded case
  the clamp exists for.
- **The cross-implementation test vector of Section 12.2**, asserting the server-side and
  client-side scoring implementations agree.
- **Current-points mode.** Render the leaderboard below the threshold and assert the page
  contains no win percentage and no projected total.

---

## 14. Summary of deliberate departures

Every **[Changed]** marker above, collected for review. Each is a decision, not an
oversight; an implementer who disagrees should disagree explicitly rather than
accidentally.

| § | Change | Reason |
|---|---|---|
| 3.5 | Dissolve the combined film-plus-roster type | It is the single thing that makes multi-tenancy a rewrite instead of a loop |
| 5.2 | Rosters loaded from local YAML; scraper and drift guard deleted | Removes the last live dependency on a third-party site; ~300 lines and a 337 KB fixture go with it |
| 5.7 | Drop third-party reported points; rename computed points | Only one notion of current points survives |
| 7.3 | Clamp blended week-over-week decay to ≤ 1.0 | Unclamped, one anomalous pair of observations compounds upward to window end and distorts the whole top ten |
| 7.4 | Derive pre-release decay over a finite run, not an infinite series | The infinite-series form biases the multiplier low, worst for late-window releases |
| 7.4 | Label the projected column as **in-window** gross | The number was right; the missing qualifier made every late-window film look like a bug |
| 8 | Warn on unclassified films | A defaulted enum failed silently for a whole season, modeling animated films with a live-action decay curve |
| 9.5 | Name the structural and policy thresholds distinctly | They answer different questions and read as redundant when unnamed |
| 10.3 | Current-points mode shows actuals, not projections | Projections too sparse to rank a top ten are too sparse to headline a table |
| 11.2 | All nav links live in every state | Disabled navigation is a dead end; a page explaining its own empty state is more useful |
| 11.3 | Document why the history page gates differently | Correct behavior that read as an inconsistency because nothing explained it |
| 13.1 | No remote font; rules reproduced on-site | Completes self-containment; removes the last outbound reference |
| 13.2 | Theme resolution moves to the document head | Eliminates a flash of the wrong theme on every load for dark-mode users |
| 13.5 | Five named test gaps closed | Each guards a rule this document treats as load-bearing |

---

## Appendix A — Constants

| Constant | Value | § |
|---|---|---|
| Ranked pick, exact at #1 or #10 | 13 pts | 2.3 |
| Ranked pick, exact at #2–#9 | 10 pts | 2.3 |
| Ranked pick, off by 1 / 2 / 3+ | 7 / 5 / 3 pts | 2.3 |
| Dark horse in top ten | 1 pt | 2.4 |
| Roster shape | 10 ranked + 3 dark horses, all distinct | 2.1 |
| Maximum possible score | 109 | 2.5 |
| Default week-over-week, wide | 0.55 | 7.2 |
| Default week-over-week, animated/family | 0.65 | 7.2 |
| Day-of-week weights, Mon–Sun | 0.07, 0.10, 0.07, 0.06, 0.22, 0.26, 0.22 | 7.2 |
| Sigma, just opened → ≥6 weeks | 0.30 → 0.10, linear | 7.2 |
| Observed-decay effective threshold | 3 snapshots | 7.3 |
| Observed-decay full weight | 6 snapshots | 7.3 |
| Observed-decay clamp | [0.01, 1.00] | 7.3 |
| Assumed theatrical run, pre-release | 10 weeks | 7.4 |
| Opening-weekend share of week one (Fri+Sat+Sun weights) | 0.70 | 7.4 |
| Sigma by confidence (high / med / low) | 0.20 / 0.30 / 0.45 | 7.4 |
| 80% band z-score | 1.2816 | 7.6 |
| Films required to rank a top ten | 10 (raises) | 9.5 |
| Projections required to forecast | 25 (degrades) | 9.5 |
| Monte Carlo trials | 10 000 | 9.3 |
| Medoid search cap | 1 500 winning trials | 9.6 |
| Chart contenders admitted to catalog | top 25 | 6.2 |
| Matrix and sandbox rows | 15 | 12.1 |
| Chart size / approximate floor | ~200 rows / ~$468K | 4.5 |
| Series palette size | 8 | 12.4 |
| Responsive breakpoint | ~700px | 13.2 |

## Appendix B — Suggested module layout

Not normative. Offered because the boundaries below fall where this document's sections
already fall, which keeps each unit small enough to reason about whole.

```
config/
  season.py          Season; loads season.yaml
  groups.py          Group, PlayerPicks; loads groups/*.yaml, validates rosters

ingest/
  boxoffice.py       Chart fetch and parse; window filter; ingest guards (§4)

catalog/
  resolve.py         Gross resolution, carry-forward, impossible-carry guard (§6.1–6.3)
  normalize.py       Candidate set, status inference, aliases, overrides (§6.2, 6.5)

model/
  decay.py           Mode A; observed blending and clamp (§7.2–7.3)
  preopening.py      Mode B; finite-run WoW derivation (§7.4)
  project.py         Dispatch; display bands; missing-projection warnings (§7.1, 7.5–7.6)
  simulate.py        Sampling with floor, aggregation, medoid scenarios (§9)

score/
  rules.py           The whole of §2. Small, pure, heavily tested.

render/
  build.py           Pipeline glue; the only place that knows the order of operations
  page.py            Render dataclasses; template invocation; data.json
  templates/         index, whatif, scenarios, history, shared nav and theme partials
  static/            Stylesheets and the one vendored library, inlined at build time

data/
  season.yaml, groups/, preopening_projections.yaml, movies_overrides.yaml,
  box_office_history.jsonl, forecast_history.jsonl
```

One boundary is worth stating as a rule rather than a suggestion: **`score/rules.py` MUST
depend on nothing but the roster type.** It is the only module encoding the game itself,
every other module is machinery around it, and it should stay small enough to read in one
sitting and verify by eye.

---

*End of specification.*
