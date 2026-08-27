# Summer Movie Wager — Public Play-Along

**A layered specification: public signups and personal standings on top of the base system.**

Version 1.0 · 2026-08-15

---

## 0. How to read this document

This specification layers on top of the base specification,
`2026-08-15-standalone-rebuild-spec.md` ("the base spec"). It does not restate the base
spec; it references it by section. Where a rule here conflicts with the base spec, this
document wins, but only for the play-along pages and the new backend — the friends-group
site is untouched.

Requirements use RFC-2119 language: **MUST**, **MUST NOT**, **SHOULD**, **MAY**.

Deliberate departures from the base spec's posture are marked **[Departure]** with their
rationale, mirroring the base spec's **[Changed]** convention.

---

## 1. Purpose and scope

### 1.1 What this adds

The base spec builds a site for one fixed friends group whose rosters are hand-edited
YAML. This specification adds a **public play-along mode**: anyone can visit a page,
choose a username, submit a top-ten list plus three dark horses, and from then on follow
their own standings by putting their username in the URL.

Base spec §1.4 explicitly deferred this feature; base spec §3 required the architecture
to permit it. This document is the design §3 left open.

### 1.2 Posture

Play-along is **casual**. There is no lock date, no prize, no tiebreaker drama. People
join whenever they find the site — including mid-season, when half the answers are
already known. The system records when each player joined (§2.2) so the display is honest
about it, and so a future rule change (a lock, a late-joiner bracket) has the data it
needs, but v1 imposes no handicap and no eligibility rule.

### 1.3 The one new moving part

The base system has no server. Play-along needs exactly one write path — accepting a
submission — so this specification introduces the system's first backend: a **Cloudflare
Worker with a D1 database**, exposing two endpoints (§3). Everything else remains static
HTML produced by the existing batch build.

The backend MUST stay this small. It stores and returns submissions. It does not score,
does not project, does not render, and knows nothing about box office data.

### 1.4 Out of scope

- **Editing or deleting a submission.** Submissions are one-shot and final (§2.3). No
  edit tokens, no accounts, no email, no password reset.
- **Win odds for play-along players.** Standings show current and projected points only
  (§5.3). Monte Carlo simulation over arbitrary ad-hoc groups is not designed here.
- **Moderation tooling.** An operator with database access can delete an offensive
  username by hand; no UI is built for it.
- **Rate limiting and bot defense** beyond payload validation (§3.5). Cloudflare
  Turnstile is the obvious retrofit if abuse appears.
- **Cross-pollination with the friends group.** Play-along players and the friends group
  are separate pools. Nothing joins them, compares them, or shares a namespace.

---

## 2. Game rules for play-along

### 2.1 What carries over unchanged

Roster shape (10 ranked + 3 dark horses, all 13 distinct — base §2.1), the actual-finish
definition (base §2.2), and every scoring rule (base §2.3–2.5) apply verbatim. There is
exactly one rule set in this system; play-along reuses it, it does not fork it.

### 2.2 What differs: no lock, and a join date

- Submissions are accepted at any time during (or before) the season. There is no lock
  at `window_start`.
- Every submission carries a server-assigned **`joined_at`** timestamp (UTC, ISO 8601).
  The interface MUST display it on the player's standings view, so a mid-August signup
  with a suspiciously perfect list is self-explaining. No other consequence attaches to
  it in v1.

### 2.3 One-shot submissions

A submission is final. A username, once taken, is taken; its picks never change. A player
who mistypes a pick lives with it or joins again under a new name. This is the entire
account model, and it is what makes the backend two endpoints instead of ten.

### 2.4 Winning

Play-along standings rank players by points within whatever view is being looked at
(§4.3). Ties share a placement using competition ranking (1, 1, 3), matching base §12.2.
There is no season-end ceremony in v1; the leaderboard on the final build is the result.

---

## 3. The players API

### 3.1 Platform

A **Cloudflare Worker** bound to a **D1** (SQLite) database. Rationale: the write volume
is tiny (a handful of rows, ever), the read is one `SELECT`, the free tier covers it by
orders of magnitude, and — decisive for this project — there is no server to keep alive,
patch, or pay for during the ten months a year the game is dormant. This matches the base
spec's "must keep working with zero maintenance" posture better than any hosted process.

The Worker is a separate small codebase from the pipeline. It MUST NOT import from or
share code with the pipeline; the interface between them is HTTP and JSON only.

### 3.2 Storage schema

```sql
CREATE TABLE players (
  username  TEXT PRIMARY KEY,
  year      INTEGER NOT NULL,
  joined_at TEXT NOT NULL,          -- UTC ISO 8601, server-assigned
  picks     TEXT NOT NULL           -- JSON: {"ranked": [10 titles], "dark_horses": [3 titles]}
);
```

One table, one row per player, picks as a JSON column. No migrations framework, no ORM.

`year` scopes a submission to a season. The Worker reads the current year from a
configuration variable in `wrangler.toml`; both endpoints operate only on rows matching
it. When a new season starts, the operator bumps the variable — old rows remain as
history, usernames become available again, and nothing is deleted.

### 3.3 `POST /api/players`

Accepts a submission.

**Request body** (JSON):

```json
{
  "username": "popcorn-goblin",
  "ranked": ["Toy Story 5", "…9 more…"],
  "dark_horses": ["Backrooms", "Scary Movie", "Evil Dead Burn"]
}
```

**Validation — all server-side, all MUST:**

| Rule | Failure |
|---|---|
| Body is JSON and at most 4 KB | 400 / 413 |
| `username` matches `^[a-z0-9][a-z0-9-]{1,22}[a-z0-9]$` (3–24 chars, lowercase, digits, interior hyphens) | 400, naming the rule |
| `ranked` is exactly 10 strings; `dark_horses` exactly 3 | 400 |
| All 13 titles distinct (exact string comparison) | 400 |
| Every title is 1–120 characters | 400 |
| Username not already present for the current year | **409** |

Uniqueness is enforced by the primary key: the Worker attempts the `INSERT` and maps the
constraint violation to 409. It MUST NOT check-then-insert; that is a race.

The Worker MUST NOT validate that titles exist in the film catalog. The signup form
guarantees canonical titles (§5.2); a title smuggled in by a direct POST simply renders
as unscoreable on that player's own page, which base §10.2 already requires every view to
survive. Keeping the Worker ignorant of the catalog is what keeps it deploy-and-forget —
otherwise every catalog change would require a Worker redeploy.

**Response:** `201` with `{"username": "...", "joined_at": "..."}`. The page uses the
echoed username to build the player's follow-along link.

### 3.4 `GET /api/players`

Returns every current-year submission:

```json
{
  "year": 2026,
  "players": [
    { "username": "popcorn-goblin",
      "joined_at": "2026-08-15T17:04:00Z",
      "ranked": ["…10…"],
      "dark_horses": ["…3…"] }
  ]
}
```

All of this data is public by design — the game only works if everyone's picks are
visible. No caching in v1 (`Cache-Control: no-store`): a player who just submitted must
see themselves on their very next page load, and a D1 read per view is nothing at this
scale. <!-- ponytail: no-store; add short max-age if D1 reads ever matter -->

### 3.5 Cross-origin and abuse posture

- The Worker MUST answer `OPTIONS` preflights and send `Access-Control-Allow-Origin: *`
  on both endpoints. Everything served is public and nothing is credentialed, so
  permissive CORS costs nothing and frees the static site to live on any host.
- Abuse defense in v1 is exactly the validation table above plus the body-size cap. A
  determined script can fill the table with junk usernames; the blast radius is a noisy
  leaderboard nobody is forced to look at (ad-hoc views show only usernames you asked
  for). If it happens, add Cloudflare Turnstile to the form and the Worker — deferred
  until needed, per §1.4.
- Any other method or path returns 404/405. There is no admin endpoint; the admin
  interface is `wrangler d1 execute`.

---

## 4. URLs and view composition

### 4.1 The two pages

| File | Page |
|---|---|
| `play.html` | Play-along standings (§5.3) |
| `join.html` | Signup form (§5.2) |

Both are produced by the existing batch build alongside the base spec's pages. They share
the site's theme and styling but carry their **own** two-pill nav (`Play Along` ·
`Join`), plus a footer link to the shared `rules.html`. They MUST NOT appear in the
friends-group nav of base §11.2, and the friends-group pages MUST NOT link to them except
optionally in the footer — the two audiences are different, and the friends leaderboard's
nav order is specified as fixed.

### 4.2 URL parameters

`play.html` reads two query parameters:

- **`user`** — a single username. This is "logging in": the page becomes that player's
  standings view, with their row highlighted and their pick detail shown.
- **`follow`** — a comma-separated list of usernames defining an ad-hoc group.

The **view set** — which players appear in the leaderboard — is composed as:

```
view_set = {user, if present}
         ∪ (follow list, if present)
         ∪ (default group, ONLY IF follow is absent)
```

`follow` **replaces** the default group rather than extending it: the parameter exists so
a handful of coworkers can share one link that shows exactly them, and a default group
mixed in would defeat that. A player who wants the default group plus a friend can name
them all in `follow`.

The **default group** is a list of usernames from build configuration (§6.1). It MAY be
empty, in which case a bare `?user=` view shows just that player.

### 4.3 View states

| URL | View |
|---|---|
| `play.html?user=alice` | Alice's view: leaderboard of {alice} ∪ default group, alice highlighted, alice's pick detail below |
| `play.html?user=alice&follow=bob,carol` | Leaderboard of {alice, bob, carol}, alice highlighted, alice's detail |
| `play.html?follow=bob,carol` | Spectator view: leaderboard of {bob, carol}, nobody highlighted, no detail section |
| `play.html` (bare) | Explainer: what play-along is, a link to `join.html`, and the default-group leaderboard if one is configured |

Rules:

- A `user` that matches no submission renders a friendly not-found state — *"No player
  named **x** — check the spelling, or join below"* — with a join link. It MUST NOT
  render an empty leaderboard as though the player existed.
- Usernames in `follow` that match no submission are dropped from the leaderboard and
  listed in one muted notice (*"Unknown players skipped: x, y"*). Known players still
  render; one typo MUST NOT blank the whole view.
- Parameters are normalized to lowercase before matching, so pasted links survive
  autocapitalize.

---

## 5. The pages

### 5.1 The static/dynamic split

Both pages are built by the batch pipeline and carry **embedded at build time**: the film
catalog slice they need, the season state, the default group, and the API base URL. At
**runtime**, `play.html` fetches the roster from `GET /api/players` and composes the view
client-side; `join.html` POSTs the form to the API.

**[Departure]** Base §13.1 requires published pages to make zero network requests. The
two play-along pages are exempt from the *runtime data fetch* clause only — each makes
exactly one `fetch()` to the players API, and no other external request of any kind (no
CDN, no fonts, no analytics; all CSS and JS still inlined). The exemption is forced by
the feature itself: ad-hoc groups from URL parameters mean the set of possible views is
unbounded and cannot be pre-rendered, and one-shot signups must be visible to their owner
immediately rather than after the next weekly build. The friends-group pages remain
zero-request; the test from base §13.1 asserting no external references MUST be updated
to allow exactly the configured API origin, on exactly these two pages.

The consequence, stated honestly on the page: **roster is live, film numbers are weekly.**
A footer line MUST give both provenances — *"Films & projections as of {build date} ·
players live."*

### 5.2 `join.html` — the signup form

- **Username field**, validated client-side against the same pattern as §3.3, with the
  rule shown inline before the user trips over it.
- **Thirteen pick slots** — ranked 1–10, then three dark-horse slots after a divider,
  echoing the All Players' Lists layout of base §12.1. Each slot is filled from a
  **searchable candidate list** (a filter-as-you-type list over the embedded candidates;
  a plain `<datalist>` restricted on submit is an acceptable v1). Free-text titles MUST
  NOT be submittable. A film already used in another slot MUST be unselectable or
  rejected inline — the 13-distinct rule enforced before the API ever sees it.
- The **candidate list** is embedded at build time (§6.2). Each candidate shows its title
  and release date so "which Scary Movie" is answerable in place.
- **On success** (201): the form is replaced by a confirmation showing the player's
  follow-along link — `play.html?user={username}` — with a copy button, and a plain
  statement that picks are final and the leaderboard updates weekly.
- **On 409:** *"That username is taken — pick another."* The picks the user has already
  chosen MUST survive the round-trip; only the username needs changing.
- **On 400 / network failure:** the error is shown and nothing is cleared. The page MUST
  NOT pretend success on any non-201.
- If the season is over (build ran with `today > window_end + 1`, base §10.1 Final
  state), the build renders the form replaced by a *"Season's over — see the final
  standings"* notice linking to `play.html`. The API stays up regardless; gating is a
  courtesy, not security.

### 5.3 `play.html` — the standings view

After resolving the view set (§4.2) against the fetched roster:

**Leaderboard table.** One row per view-set player, sorted by current points descending,
competition-ranked. Columns:

| Column | Content |
|---|---|
| Place | 1, 1, 3 … |
| Player | Username; the `user` player highlighted |
| Joined | `joined_at`, date only |
| Current pts | Scored against the embedded actual top ten |
| Projected pts | Scored against the embedded projected finish order |

**Pick detail** (only when `user` resolves): the player's 13 picks in a table mirroring
the base per-player detail (base §12.1 §3) as far as the embedded data allows: pick
position (🐴 for dark horses), title, projected rank across the catalog, current points,
projected points. A pick absent from the embedded catalog renders the muted placeholder
of base §10.2, never an error.

**Scoring is client-side.** Current points score the player's roster against the
embedded actual top ten; projected points against the embedded projected top ten (the
catalog's top ten films by projected median). Both use the base §2 rules. This makes the
play page the **third consumer of the shared scoring test vector** of base §12.2 — or the
second consumer of a shared client-side scoring module also used by What If?, which the
implementation SHOULD prefer over a third copy.

**Season-state behavior** mirrors base §10.3: when the build ran without a forecast
(Early state), the *Projected pts* column and the detail's projected columns are absent
entirely — not dashed out — and the current-points column headlines. The embedded season
state flag decides this at build time.

**Page states**, each explicit:

- **Loading:** skeleton or "loading players…" — brief, but present, since the roster
  fetch is on the critical path.
- **API unreachable:** a visible error — *"Couldn't load players — try again in a
  minute."* The page MUST NOT fabricate an empty leaderboard; an empty state and a
  failed fetch are different facts and must look different.
- **Not-found / unknown-follow states** per §4.3.

### 5.4 Untrusted content

This feature introduces the system's first genuinely untrusted strings: usernames and
pick titles arrive from anonymous submitters and are rendered into **other** people's
browsers via shared `follow` links. All client-side rendering of API-derived strings
MUST use text-node insertion (`textContent` / `createTextNode`) — never HTML string
interpolation, never `innerHTML`. URL parameters get the same treatment. This is the
play-along counterpart of base §11.4's autoescaping rule, and it is the one place a lazy
implementation would create a stored-XSS hole shareable as a link.

---

## 6. Pipeline integration

### 6.1 Configuration — `play.yaml`

One new config file, loaded alongside `season.yaml`:

```yaml
api_base_url: https://smw-players.example.workers.dev
default_group:            # usernames; may be empty
  - popcorn-goblin
  - matinee-mike
```

Both values are embedded into the play pages at build time. `default_group` is
operator-curated — the "default group we can add to later" is an edit to this file and a
rebuild, no code change.

### 6.2 The candidate list

The signup form's candidate list is the **film catalog** of base §6.2 — which already
unions every chart contender with every pre-release analyst entry — serialized as
`(title, release_date)` pairs, sorted by release date. No separate candidates file: if a
film worth picking is missing, the operator adds it where the base system already wants
it (a `preopening_projections.yaml` entry), and it appears on the form at the next build.

### 6.3 Play-along picks feed the catalog

The build SHOULD fetch `GET /api/players` and union all play-along picked titles into the
base §6.2 candidate set, exactly as configured groups' rosters already are. This keeps a
play-along pick from going dark if it falls out of the chart's top-`chart_contenders`
slice.

**[Departure]** Base §4.1 declares the box-office chart the system's only network
dependency; the build now has a second, **optional** one. If the players API is
unreachable the build MUST warn and continue — the friends site must never fail to
publish because the play-along backend is down. A failed fetch degrades play-along only,
and only marginally (a deep pick might lose its projection until the next successful
build).

### 6.4 What the build embeds in the play pages

From the existing `MovieCatalog` and simulation outputs, no new computation:

- The catalog as `(title, release_date, projected_rank, projected_median, status)`.
- The **actual top ten** (titles in order) and the **projected top ten** (titles in
  order, top ten by projected median) — the two lists client-side scoring runs against.
- The season state flag (Early / Live / Final) and reason string, driving §5.3's
  column behavior.
- Build date, `api_base_url`, `default_group`.

Embedded JSON MUST escape `<` as `\u003c` per base §11.4.

### 6.5 What does not change

The friends-group pipeline path — ingest, projection, simulation, the four pages, both
history files — is untouched. Play-along players are never scored server-side, never
appear in `data.json`, never enter the Monte Carlo, and never affect the friends
leaderboard. The pipeline's only new work is §6.3's optional fetch and rendering two more
templates.

---

## 7. Testing

**Worker** (its own small suite, runnable locally against a local D1):

- Every row of the §3.3 validation table: one passing case, one failing case per rule,
  asserting status code and that a failing POST writes nothing.
- Duplicate username → 409, first submission intact.
- `joined_at` is server-assigned (a client-supplied value is ignored).
- `GET` returns only current-year rows, in the §3.4 shape.
- CORS headers present on `GET`, `POST`, and `OPTIONS`.

**Client-side scoring:** the shared test vector of base §12.2 runs against the play
page's scoring path. If the implementation shares one scoring module with What If?, the
existing vector suffices; a third implementation requires wiring the vector to it.

**Rendered pages** (extending the base §13.5 suite):

- `join.html` and `play.html` snapshot tests, matching the base snapshot ritual.
- The no-external-references test allows exactly the configured API origin on exactly
  these two pages, and still fails on any other origin anywhere.
- Early-state build → play page contains no "Projected" column.
- A hostile username and a hostile title (`</script>`, `<img onerror=…>`) round-tripped
  through the view-composition code render inert. This is the §5.4 rule under test.

**View composition** (pure function, unit-tested): the §4.2 composition rules and each
§4.3 state — follow replaces default group, unknown `user`, partial-unknown `follow`,
bare URL, lowercase normalization.

---

## 8. Summary of departures

| § | Departure from base spec | Reason |
|---|---|---|
| 5.1 | Play pages make one runtime fetch each | Ad-hoc URL-parameter groups are unbounded and can't be pre-rendered; one-shot signups must be visible immediately |
| 6.3 | The build gains a second, optional network dependency | Play-along picks must stay in the catalog; optional so the friends site never fails on the backend's account |

Everything else — scoring rules, projection, season lifecycle, self-containment of the
friends pages, theming, accessibility posture — is inherited unchanged.

---

*End of specification.*
