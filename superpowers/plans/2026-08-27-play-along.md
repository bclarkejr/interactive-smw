# Public Play-Along Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a public play-along mode — a Cloudflare Worker + D1 backend that accepts one-shot roster submissions, and two new static pages (`play.html`, `join.html`) per season that fetch the live roster and score it client-side.

**Architecture:** The Worker (`worker/`, plain JS, no shared code with the pipeline) exposes `GET|POST|OPTIONS /api/players` over one D1 table. The batch build gains one optional config file (`data/seasons/<year>/play.yaml`), one optional network fetch (players → candidate set), one view-model module (`smw/render/play.py`), two templates and two client scripts. Client-side scoring reuses the existing `scoring.js`; view composition and standings are pure functions in `play.js`, unit-tested under `node --test`.

**Tech Stack:** Python ≥3.11, Jinja2, PyYAML, requests, pytest; Node ≥20 (`node --test`) for client tests; Cloudflare Wrangler 4 + `@cloudflare/vitest-pool-workers` + Vitest for the Worker.

**Spec:** `superpowers/specs/2026-08-15-play-along-design.md` (layers on `superpowers/specs/2026-08-15-standalone-rebuild-spec.md`, the "base spec"). Executors read both. The spec's section numbers are cited as §N below; base-spec sections as "base §N".

## Global Constraints

Copied from the spec / AGENTS.md; every task implicitly includes these.

- Reproducible output: identical inputs (including `--date`) produce byte-identical output for every file under `<out>/`, including `play.html` and `join.html`.
- Friends-group pages stay self-contained: no `http://`, `https://`, `//cdn`, `@import`, `url(http`, `fetch(`, `XMLHttpRequest` in `index/whatif/scenarios/history/rules.html`. **[Departure §5.1]** `play.html` and `join.html` may contain the configured `api_base_url` origin and exactly one `fetch(` each; nothing else external (no CDN, fonts, analytics).
- The Worker MUST NOT import from or share code with the pipeline (§3.1). Interface is HTTP + JSON only.
- Worker validation (§3.3), all server-side: body JSON ≤ 4 KB (400/413); `username` matches `^[a-z0-9][a-z0-9-]{1,22}[a-z0-9]$` (400 naming the rule); `ranked` exactly 10 strings, `dark_horses` exactly 3 (400); all 13 distinct by exact string (400); every title 1–120 chars (400); duplicate username for the current year → 409 via INSERT constraint, never check-then-insert. The Worker MUST NOT validate titles against the catalog.
- `GET /api/players` returns `{"year": N, "players": [{username, joined_at, ranked, dark_horses}]}`, `Cache-Control: no-store`. `Access-Control-Allow-Origin: *` on GET, POST, OPTIONS. Any other method/path → 404/405.
- `joined_at` is server-assigned UTC ISO 8601; a client-supplied value is ignored.
- `play.html` view set: `{user} ∪ follow` if `follow` present, else `{user} ∪ default_group` (§4.2). Params lowercased. Unknown `user` → not-found state with join link, never an empty leaderboard. Unknown `follow` names → dropped and listed in one muted notice.
- All client-side rendering of API-derived strings and URL parameters uses `textContent`/`createTextNode` — never `innerHTML` with data, never `insertAdjacentHTML` (§5.4).
- Early state (build ran without a forecast): no "Projected" column anywhere on `play.html` — absent, not dashed (§5.3).
- Footer line on both play pages: `Films & projections as of {build date} · players live.` (§5.1). Two-pill nav `Play Along` · `Join` plus footer link to `rules.html`. Play pages MUST NOT appear in the friends-group nav (§4.1).
- Embedded JSON escapes `<` as `\u003c` (existing `json_embed`).
- No module-level date or threshold constants in render layers. Render layer never sorts/ranks/computes — view models arrive finished (base §11.4); the *client* JS is where play-along scoring happens by design (§5.3).
- Persisted data: existing §5 files **plus** `data/seasons/<year>/play.yaml`. Still no persisted refresh/run-date record.
- Deterministic checks before any review round: `.venv/bin/pytest` and `cd worker && npm test`.
- Commit only this task's files (never `git add -A`); working tree clean before each cross-review. Work on a feature branch (`feat/play-along`).

## Decisions the spec forced (read before executing)

1. **Primary key is `(username, year)`, not `username` alone.** §3.2's SQL literal has `username TEXT PRIMARY KEY`, but §3.2's prose says that when the year is bumped "usernames become available again" and §3.3 says uniqueness is "for the current year". A single-column PK makes both impossible. The prose wins; the composite key is what the 409 path relies on.
2. **Play pages live at `<out>/<year>/play.html` and `<out>/<year>/join.html`** — season-scoped, group-independent (play-along is not a friends group, §1.4). Their footer rules link is `<default_group>/rules.html`, the season's default group's copy of the shared rules page.
3. **`play.yaml` is optional.** A season without it builds exactly as today (no play pages, no players fetch). This keeps every existing test and the 2026 production data valid until the Worker is deployed and its URL is known.
4. **Unknown names in `default_group` are dropped silently**; only unknown names in `follow` are listed in the notice (§4.3 specifies the notice for `follow` only; the default group is operator config, and "not joined yet" is its normal state).
5. **Play-page CSS lives in `smw/render/static/play.css`**, inlined after `site.css` on the two play pages only. `tests/test_site_css.py` locks `site.css` additions to `.series-*`/`.sel`/`.vh`, and that lock is correct — the form styles must not go there.
6. **The hostile-content test (§7) is split in two:** a Python test proves a `</script>` title in the embedded catalog is emitted as `\u003c/script>`, and a Node test proves `composeView`/`standings`/`pickRows` return hostile usernames/titles verbatim (no HTML escaping, because the DOM layer only ever uses `textContent`) plus a static assertion that `play.js`/`join.js` never assign `innerHTML` anything but `""` and never call `insertAdjacentHTML`/`outerHTML`/`document.write`. No DOM emulator is added.
7. **`scoring.js` gains `pointsFor` in its `module.exports`** so the play page is the second consumer of the shared client scoring module (§5.3 SHOULD) rather than a third copy.
8. **Players are fetched on every build, including `--local`** (the chart is too). Tests monkeypatch the seam `smw.render.build.fetch_players`.
9. **Sorting is by current points in every state**, name ascending as the tiebreak for a stable order (§5.3 says "sorted by current points descending"; place uses competition ranking so ties still share a place).

## File Structure

**Worker (new, self-contained):**
- `worker/package.json` — scripts `test`, `deploy`; devDependencies only.
- `worker/wrangler.toml` — name, `main`, `[vars] SEASON_YEAR`, D1 binding `DB`.
- `worker/schema.sql` — the one table (composite PK).
- `worker/vitest.config.js` — `defineWorkersConfig` pointed at `wrangler.toml`.
- `worker/src/index.js` — `validate(body)` + the `fetch` handler. One file.
- `worker/test/api.test.js` — the §7 Worker suite.

**Pipeline (modify / create):**
- Create `smw/config/play.py` — `PlayConfig`, `USERNAME_RE`, `load_play(path) -> PlayConfig | None`.
- Create `smw/ingest/players.py` — `fetch_players(api_base_url) -> list[dict]`, `picked_titles(players) -> set[str]`.
- Modify `smw/catalog/normalize.py:159-176` — `build_films(..., extra_titles=())`.
- Modify `smw/render/build.py` — `fetch_players` seam; load `play.yaml`; union titles; render the two pages.
- Create `smw/render/play.py` — `season_state`, `build_play_data`, `play_context`, `render_play`, `render_join`.
- Create `smw/render/templates/play_base.html.j2`, `play.html.j2`, `join.html.j2`.
- Create `smw/render/static/play.css`, `play.js`, `join.js`.
- Modify `smw/render/static/scoring.js:31-33` — export `pointsFor`.

**Tests:**
- `tests/test_play_config.py`, `tests/test_players_ingest.py`, `tests/test_play_data.py`, `tests/test_play_render.py`, `tests/test_join_render.py`, `tests/test_play_js.py` (drives `node --test`), `tests/play_view.test.mjs`, `tests/join_validate.test.mjs`; modify `tests/test_build_films.py`, `tests/test_build.py`, `tests/test_self_containment.py`; new fixtures `tests/fixtures/snapshot_play.html`, `tests/fixtures/snapshot_join.html`.

**Docs / config:** `AGENTS.md` (checks + persisted-data line + self-containment exception), `.gitignore` (`worker/node_modules/`, `worker/.wrangler/`), `README.md` (operator runbook).

---

### Task 1: Worker scaffold — GET, OPTIONS, CORS, 404/405

**Files:**
- Create: `worker/package.json`, `worker/wrangler.toml`, `worker/schema.sql`, `worker/vitest.config.js`, `worker/src/index.js`, `worker/test/api.test.js`
- Modify: `.gitignore` (append), `AGENTS.md` (deterministic checks)

**Interfaces:**
- Consumes: nothing.
- Produces: `export default { fetch(request, env) }` handling `GET /api/players` and `OPTIONS`; `json(status, body)` helper and `CORS` const reused by Task 2. Env: `env.DB` (D1), `env.SEASON_YEAR` (string in `[vars]`, coerced with `Number`).

- [ ] **Step 1: Scaffold the package**

`worker/package.json`:
```json
{
  "name": "smw-players",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "vitest run",
    "deploy": "wrangler deploy"
  },
  "devDependencies": {
    "@cloudflare/vitest-pool-workers": "^0.8.0",
    "vitest": "~3.2.0",
    "wrangler": "^4.0.0"
  }
}
```
If `npm install` reports a peer-dependency conflict between `vitest` and the pool package, change the `vitest` range to the one named in `@cloudflare/vitest-pool-workers`'s `peerDependencies` (`npm view @cloudflare/vitest-pool-workers peerDependencies`) and commit the resulting `package-lock.json`.

`worker/wrangler.toml`:
```toml
name = "smw-players"
main = "src/index.js"
compatibility_date = "2025-06-01"

[vars]
SEASON_YEAR = "2026"

[[d1_databases]]
binding = "DB"
database_name = "smw-players"
database_id = "replace-with-the-id-printed-by-wrangler-d1-create"
```

`worker/schema.sql` (Decision 1 — composite key):
```sql
CREATE TABLE IF NOT EXISTS players (
  username  TEXT    NOT NULL,
  year      INTEGER NOT NULL,
  joined_at TEXT    NOT NULL,          -- UTC ISO 8601, server-assigned
  picks     TEXT    NOT NULL,          -- JSON: {"ranked": [10 titles], "dark_horses": [3 titles]}
  PRIMARY KEY (username, year)
);
```

`worker/vitest.config.js`:
```js
import { defineWorkersConfig } from "@cloudflare/vitest-pool-workers/config";

export default defineWorkersConfig({
  test: {
    poolOptions: {
      workers: { wrangler: { configPath: "./wrangler.toml" } },
    },
  },
});
```

Append to `.gitignore`:
```
# Cloudflare Worker
worker/node_modules/
worker/.wrangler/
```

Run: `cd worker && npm install`
Expected: `node_modules/` created, `package-lock.json` written (commit the lock file).

- [ ] **Step 2: Write the failing tests**

`worker/test/api.test.js`:
```js
import { env, SELF } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";

// One line: D1's prepare() takes a single statement. Mirrors worker/schema.sql.
const SCHEMA =
  "CREATE TABLE IF NOT EXISTS players (username TEXT NOT NULL, year INTEGER NOT NULL, " +
  "joined_at TEXT NOT NULL, picks TEXT NOT NULL, PRIMARY KEY (username, year))";
const URL_ = "https://smw-players.test/api/players";

beforeEach(async () => {
  await env.DB.prepare("DROP TABLE IF EXISTS players").run();
  await env.DB.prepare(SCHEMA).run();
});

async function insert(username, year, joined_at, ranked, dark) {
  await env.DB.prepare(
    "INSERT INTO players (username, year, joined_at, picks) VALUES (?, ?, ?, ?)")
    .bind(username, year, joined_at, JSON.stringify({ ranked, dark_horses: dark })).run();
}
const TEN = Array.from({ length: 10 }, (_, i) => `Film ${i + 1}`);
const THREE = ["DH1", "DH2", "DH3"];

describe("GET /api/players", () => {
  it("returns only current-year rows in the §3.4 shape", async () => {
    await insert("alice", 2026, "2026-08-15T17:04:00Z", TEN, THREE);
    await insert("bob", 2025, "2025-06-01T00:00:00Z", TEN, THREE);
    const r = await SELF.fetch(URL_);
    expect(r.status).toBe(200);
    expect(r.headers.get("Cache-Control")).toBe("no-store");
    expect(r.headers.get("Access-Control-Allow-Origin")).toBe("*");
    expect(await r.json()).toEqual({
      year: 2026,
      players: [{ username: "alice", joined_at: "2026-08-15T17:04:00Z",
                  ranked: TEN, dark_horses: THREE }],
    });
  });
  it("returns an empty list, not an error, when nobody has joined", async () => {
    const r = await SELF.fetch(URL_);
    expect(await r.json()).toEqual({ year: 2026, players: [] });
  });
});

describe("CORS and routing", () => {
  it("answers OPTIONS preflight with permissive CORS", async () => {
    const r = await SELF.fetch(URL_, { method: "OPTIONS" });
    expect(r.status).toBe(204);
    expect(r.headers.get("Access-Control-Allow-Origin")).toBe("*");
    expect(r.headers.get("Access-Control-Allow-Methods")).toContain("POST");
    expect(r.headers.get("Access-Control-Allow-Headers")).toContain("Content-Type");
  });
  it("404s any other path and 405s any other method", async () => {
    expect((await SELF.fetch("https://smw-players.test/admin")).status).toBe(404);
    expect((await SELF.fetch(URL_, { method: "DELETE" })).status).toBe(405);
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd worker && npm test`
Expected: FAIL — `src/index.js` does not exist / responses undefined.

- [ ] **Step 4: Implement the handler (GET/OPTIONS/routing only)**

`worker/src/index.js`:
```js
// Summer Movie Wager — players API (spec §3). Stores and returns submissions; nothing else.
export const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

async function listPlayers(env, year) {
  const { results } = await env.DB.prepare(
    "SELECT username, joined_at, picks FROM players WHERE year = ? ORDER BY joined_at, username")
    .bind(year).all();
  const players = results.map((r) => {
    const p = JSON.parse(r.picks);
    return { username: r.username, joined_at: r.joined_at,
             ranked: p.ranked, dark_horses: p.dark_horses };
  });
  return json(200, { year, players });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== "/api/players") return json(404, { error: "not found" });
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    const year = Number(env.SEASON_YEAR);
    if (request.method === "GET") return listPlayers(env, year);
    return json(405, { error: "method not allowed" });
  },
};
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd worker && npm test`
Expected: PASS (5 tests).

- [ ] **Step 6: Add the Worker check to AGENTS.md**

In `AGENTS.md` under `## Deterministic checks`, after the `- Test:` line add:
```
- Worker test: `cd worker && npm ci && npm test` (Node ≥20; the players API in `worker/` has its own suite)
```

- [ ] **Step 7: Commit**

```bash
git add worker/package.json worker/package-lock.json worker/wrangler.toml worker/schema.sql \
        worker/vitest.config.js worker/src/index.js worker/test/api.test.js .gitignore AGENTS.md
git commit -m "feat(worker): players API scaffold — GET, OPTIONS, CORS, routing"
```

---

### Task 2: Worker POST — validation table and 409

**Files:**
- Modify: `worker/src/index.js`, `worker/test/api.test.js`

**Interfaces:**
- Consumes: `json`, `CORS`, `env.DB`, `env.SEASON_YEAR` from Task 1.
- Produces: `export function validate(body) -> string | null` (error message or null); `POST /api/players` → 201 `{username, joined_at}`, 400/413/409 `{error}`.

- [ ] **Step 1: Write the failing tests**

Append to `worker/test/api.test.js`:
```js
function good(over = {}) {
  return { username: "popcorn-goblin", ranked: TEN, dark_horses: THREE, ...over };
}
async function post(body, init = {}) {
  return SELF.fetch(URL_, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: typeof body === "string" ? body : JSON.stringify(body),
    ...init,
  });
}
async function count() {
  return (await env.DB.prepare("SELECT COUNT(*) AS n FROM players").first()).n;
}

describe("POST /api/players", () => {
  it("accepts a valid submission with a server-assigned joined_at", async () => {
    const r = await post(good({ joined_at: "1999-01-01T00:00:00Z" }));  // client value ignored
    expect(r.status).toBe(201);
    expect(r.headers.get("Access-Control-Allow-Origin")).toBe("*");
    const body = await r.json();
    expect(body.username).toBe("popcorn-goblin");
    expect(body.joined_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
    expect(body.joined_at).not.toBe("1999-01-01T00:00:00Z");
    const rows = (await SELF.fetch(URL_).then((x) => x.json())).players;
    expect(rows).toHaveLength(1);
    expect(rows[0].joined_at).toBe(body.joined_at);
    expect(rows[0].ranked).toEqual(TEN);
  });

  // One failing case per §3.3 row; each writes nothing.
  const bad = [
    ["non-JSON body", "{not json", 400],
    ["JSON array, not object", "[1,2,3]", 400],
    ["username too short", good({ username: "ab" }), 400],
    ["username uppercase", good({ username: "Popcorn" }), 400],
    ["username leading hyphen", good({ username: "-popcorn" }), 400],
    ["username trailing hyphen", good({ username: "popcorn-" }), 400],
    ["username 25 chars", good({ username: "a".repeat(25) }), 400],
    ["ranked has 9", good({ ranked: TEN.slice(0, 9) }), 400],
    ["ranked has 11", good({ ranked: TEN.concat(["Film 11"]) }), 400],
    ["ranked contains a non-string", good({ ranked: TEN.slice(0, 9).concat([7]) }), 400],
    ["dark_horses has 2", good({ dark_horses: THREE.slice(0, 2) }), 400],
    ["dark_horses missing", (() => { const g = good(); delete g.dark_horses; return g; })(), 400],
    ["duplicate across ranked and dark", good({ dark_horses: ["Film 1", "DH2", "DH3"] }), 400],
    ["duplicate within ranked", good({ ranked: TEN.slice(0, 9).concat(["Film 1"]) }), 400],
    ["empty title", good({ dark_horses: ["", "DH2", "DH3"] }), 400],
    ["title of 121 chars", good({ dark_horses: ["x".repeat(121), "DH2", "DH3"] }), 400],
    ["body over 4 KB", JSON.stringify(good({ dark_horses: ["x".repeat(5000), "DH2", "DH3"] })), 413],
  ];
  for (const [name, body, status] of bad) {
    it(`rejects ${name} with ${status} and writes nothing`, async () => {
      const r = await post(body);
      expect(r.status).toBe(status);
      expect((await r.json()).error).toBeTruthy();
      expect(await count()).toBe(0);
    });
  }

  it("names the username rule on a 400", async () => {
    const r = await post(good({ username: "no spaces" }));
    expect((await r.json()).error).toMatch(/3–24|lowercase/);
  });

  it("does not validate titles against any catalog", async () => {
    const r = await post(good({ dark_horses: ["Not A Real Film", "DH2", "DH3"] }));
    expect(r.status).toBe(201);
  });

  it("409s a duplicate username and leaves the first submission intact", async () => {
    expect((await post(good())).status).toBe(201);
    const r = await post(good({ ranked: TEN.slice().reverse() }));
    expect(r.status).toBe(409);
    expect((await r.json()).error).toMatch(/taken/);
    const rows = (await SELF.fetch(URL_).then((x) => x.json())).players;
    expect(rows).toHaveLength(1);
    expect(rows[0].ranked).toEqual(TEN);  // first submission, not the second
  });

  it("lets a username from a previous year join this year", async () => {
    await insert("popcorn-goblin", 2025, "2025-06-01T00:00:00Z", TEN, THREE);
    expect((await post(good())).status).toBe(201);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd worker && npm test`
Expected: FAIL — POST returns 405.

- [ ] **Step 3: Implement validation and the INSERT**

In `worker/src/index.js`, add above `export default`:
```js
const USERNAME = /^[a-z0-9][a-z0-9-]{1,22}[a-z0-9]$/;
const MAX_BODY_BYTES = 4096;

function titlesOk(list, n) {
  return Array.isArray(list) && list.length === n &&
    list.every((t) => typeof t === "string" && t.length >= 1 && t.length <= 120);
}

/** §3.3 validation table. Returns an error message, or null when the body is acceptable. */
export function validate(body) {
  if (body === null || typeof body !== "object" || Array.isArray(body))
    return "body must be a JSON object";
  if (typeof body.username !== "string" || !USERNAME.test(body.username))
    return "username must be 3–24 characters: lowercase letters, digits, and interior hyphens";
  if (!titlesOk(body.ranked, 10)) return "ranked must be exactly 10 titles of 1–120 characters";
  if (!titlesOk(body.dark_horses, 3)) return "dark_horses must be exactly 3 titles of 1–120 characters";
  if (new Set([...body.ranked, ...body.dark_horses]).size !== 13)
    return "all 13 titles must be distinct";
  return null;
}

async function createPlayer(request, env, year) {
  const raw = await request.arrayBuffer();
  if (raw.byteLength > MAX_BODY_BYTES) return json(413, { error: "body exceeds 4 KB" });
  let body;
  try { body = JSON.parse(new TextDecoder().decode(raw)); }
  catch { return json(400, { error: "body must be JSON" }); }
  const err = validate(body);
  if (err) return json(400, { error: err });
  const joined_at = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");  // server-assigned (§2.2)
  const picks = JSON.stringify({ ranked: body.ranked, dark_horses: body.dark_horses });
  try {
    // INSERT and map the PK violation — never check-then-insert (§3.3).
    await env.DB.prepare(
      "INSERT INTO players (username, year, joined_at, picks) VALUES (?, ?, ?, ?)")
      .bind(body.username, year, joined_at, picks).run();
  } catch (e) {
    if (/UNIQUE constraint failed/i.test(String(e && e.message || e)))
      return json(409, { error: "that username is taken — pick another" });
    throw e;
  }
  return json(201, { username: body.username, joined_at });
}
```
and in `fetch`, replace the final `return json(405, …)` with:
```js
    if (request.method === "POST") return createPlayer(request, env, year);
    return json(405, { error: "method not allowed" });
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd worker && npm test`
Expected: PASS (all). If the 409 test fails with a different message, print `e.message` once in the catch, match on the substring D1 actually produces, and keep the test.

- [ ] **Step 5: Commit**

```bash
git add worker/src/index.js worker/test/api.test.js
git commit -m "feat(worker): POST /api/players with §3.3 validation and 409 on duplicate"
```

---

### Task 3: `play.yaml` config loader

**Files:**
- Create: `smw/config/play.py`, `tests/test_play_config.py`
- Modify: `AGENTS.md` (persisted-data line)

**Interfaces:**
- Consumes: nothing.
- Produces:
  ```python
  USERNAME_RE: re.Pattern  # r"[a-z0-9][a-z0-9-]{1,22}[a-z0-9]" (fullmatch)
  @dataclass(frozen=True)
  class PlayConfig: api_base_url: str; default_group: tuple[str, ...]
  def load_play(path: Path) -> PlayConfig | None   # None when the file is absent
  ```

- [ ] **Step 1: Write the failing tests**

`tests/test_play_config.py`:
```python
import pytest
from smw.config.play import PlayConfig, load_play

def test_absent_file_is_none(tmp_path):
    assert load_play(tmp_path / "play.yaml") is None

def test_loads_url_and_group(tmp_path):
    p = tmp_path / "play.yaml"
    p.write_text("api_base_url: https://smw-players.example.workers.dev\n"
                 "default_group:\n  - popcorn-goblin\n  - matinee-mike\n")
    assert load_play(p) == PlayConfig("https://smw-players.example.workers.dev",
                                      ("popcorn-goblin", "matinee-mike"))

def test_default_group_may_be_empty_or_omitted(tmp_path):
    p = tmp_path / "play.yaml"
    p.write_text("api_base_url: https://x.example\n")
    assert load_play(p).default_group == ()
    p.write_text("api_base_url: https://x.example\ndefault_group: []\n")
    assert load_play(p).default_group == ()

@pytest.mark.parametrize("text, msg", [
    ("default_group: [a]\n", "api_base_url"),
    ("api_base_url: ftp://x.example\n", "https://"),
    ("api_base_url: https://x.example/\n", "trailing slash"),
    ("api_base_url: https://x.example?y=1\n", "query"),
    ("api_base_url: https://x.example\ndefault_group: popcorn\n", "list"),
    ("api_base_url: https://x.example\ndefault_group: [Popcorn]\n", "username"),
    ("api_base_url: https://x.example\ndefault_group: [a, a]\n", "duplicate"),
    ("api_base_url: https://x.example\nextra: 1\n", "unknown key"),
    ("- not a mapping\n", "mapping"),
])
def test_rejects_bad_config(tmp_path, text, msg):
    p = tmp_path / "play.yaml"
    p.write_text(text)
    with pytest.raises(ValueError, match=msg):
        load_play(p)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_play_config.py -v`
Expected: FAIL — `ModuleNotFoundError: smw.config.play`.

- [ ] **Step 3: Implement the loader**

`smw/config/play.py`:
```python
"""Play-along build configuration (play-along spec §6.1). Optional per season."""
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

USERNAME_RE = re.compile(r"[a-z0-9][a-z0-9-]{1,22}[a-z0-9]")  # §3.3, fullmatch


@dataclass(frozen=True)
class PlayConfig:
    api_base_url: str
    default_group: tuple[str, ...]


def load_play(path: Path) -> PlayConfig | None:
    path = Path(path)
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a mapping")
    unknown = set(raw) - {"api_base_url", "default_group"}
    if unknown:
        raise ValueError(f"{path}: unknown key(s): {', '.join(sorted(unknown))}")
    url = raw.get("api_base_url")
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        raise ValueError(f"{path}: api_base_url must be a string starting with https:// (or http://)")
    if url.endswith("/"):
        raise ValueError(f"{path}: api_base_url must not have a trailing slash")
    if "?" in url or "#" in url:
        raise ValueError(f"{path}: api_base_url must not carry a query or fragment")
    group = raw.get("default_group")
    if group is None:
        group = []
    if not isinstance(group, list):
        raise ValueError(f"{path}: default_group must be a list of usernames")
    for u in group:
        if not isinstance(u, str) or not USERNAME_RE.fullmatch(u):
            raise ValueError(f"{path}: default_group entry {u!r} is not a valid username "
                             "(3–24 chars: lowercase, digits, interior hyphens)")
    if len(set(group)) != len(group):
        raise ValueError(f"{path}: default_group has duplicate usernames")
    return PlayConfig(api_base_url=url, default_group=tuple(group))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_play_config.py -v`
Expected: PASS.

- [ ] **Step 5: Update AGENTS.md persisted-data line**

In `AGENTS.md`, in the `- Persisted data is exactly the files in spec §5 …` bullet, change the file list to read:
```
(`season.yaml`, `play.yaml` [optional, play-along spec §6.1], `groups/*.yaml`, `preopening_projections.yaml`, `movies_overrides.yaml`, `box_office_history.jsonl`, `forecast_history/<group_id>.jsonl`)
```

- [ ] **Step 6: Commit**

```bash
git add smw/config/play.py tests/test_play_config.py AGENTS.md
git commit -m "feat(config): optional play.yaml loader (api_base_url, default_group)"
```

---

### Task 4: Players fetch feeds the catalog (§6.3)

**Files:**
- Create: `smw/ingest/players.py`, `tests/test_players_ingest.py`
- Modify: `smw/catalog/normalize.py:159-176` (`build_films`), `smw/render/build.py` (`_build_season`), `tests/test_build_films.py` (append), `tests/test_build.py` (append)

**Interfaces:**
- Consumes: `PlayConfig`, `load_play` (Task 3); `canonical`, `build_films`, `build_catalog` (existing).
- Produces:
  ```python
  # smw/ingest/players.py
  def fetch_players(api_base_url: str) -> list[dict]   # GET {api_base_url}/api/players, 10 s timeout, raises on any failure
  def picked_titles(players: list[dict]) -> set[str]   # every string in ranked/dark_horses; malformed entries skipped
  # smw/catalog/normalize.py
  def build_films(season, groups, chart_rows, grosses, carried, overrides, preopening, today,
                  extra_titles: Iterable[str] = ()) -> list[Film]
  # smw/render/build.py
  fetch_players = players.fetch_players   # network seam; tests monkeypatch this
  ```

- [ ] **Step 1: Write the failing ingest tests**

`tests/test_players_ingest.py`:
```python
import pytest
import requests
from smw.ingest import players

def test_picked_titles_unions_all_strings_and_skips_junk():
    rows = [
        {"username": "a", "ranked": ["X", "Y"], "dark_horses": ["Z"]},
        {"username": "b", "ranked": "not a list", "dark_horses": ["Z", 7, None]},
        "not a dict",
    ]
    assert players.picked_titles(rows) == {"X", "Y", "Z"}

def test_fetch_players_calls_the_endpoint(monkeypatch):
    seen = {}
    class R:
        def raise_for_status(self): pass
        def json(self): return {"year": 2026, "players": [{"username": "a"}]}
    def get(url, timeout):
        seen["url"], seen["timeout"] = url, timeout
        return R()
    monkeypatch.setattr(players.requests, "get", get)
    assert players.fetch_players("https://x.example") == [{"username": "a"}]
    assert seen == {"url": "https://x.example/api/players", "timeout": 10}

def test_fetch_players_raises_on_http_error(monkeypatch):
    class R:
        def raise_for_status(self): raise requests.HTTPError("500")
    monkeypatch.setattr(players.requests, "get", lambda url, timeout: R())
    with pytest.raises(requests.HTTPError):
        players.fetch_players("https://x.example")

def test_fetch_players_raises_on_wrong_shape(monkeypatch):
    class R:
        def raise_for_status(self): pass
        def json(self): return {"players": "nope"}
    monkeypatch.setattr(players.requests, "get", lambda url, timeout: R())
    with pytest.raises(ValueError, match="players"):
        players.fetch_players("https://x.example")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_players_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: smw.ingest.players`.

- [ ] **Step 3: Implement the ingest module**

`smw/ingest/players.py`:
```python
"""Play-along roster fetch (play-along spec §6.3). Optional network dependency:
the caller warns and continues on any exception."""
import requests


def fetch_players(api_base_url: str) -> list[dict]:
    r = requests.get(f"{api_base_url}/api/players", timeout=10)
    r.raise_for_status()
    body = r.json()
    if not isinstance(body, dict) or not isinstance(body.get("players"), list):
        raise ValueError("players API response has no 'players' list")
    return body["players"]


def picked_titles(players: list[dict]) -> set[str]:
    titles: set[str] = set()
    for p in players:
        if not isinstance(p, dict):
            continue
        for key in ("ranked", "dark_horses"):
            v = p.get(key)
            if isinstance(v, list):
                titles.update(t for t in v if isinstance(t, str) and t.strip())
    return titles
```

- [ ] **Step 4: Run ingest tests to verify they pass**

Run: `.venv/bin/pytest tests/test_players_ingest.py -v`
Expected: PASS.

- [ ] **Step 5: Write the failing `build_films` test**

Append to `tests/test_build_films.py` (reuse whatever season/overrides helpers that file already defines; if it builds films via a helper, call `build_films` directly here):
```python
from datetime import date
from smw.catalog.normalize import build_films
from smw.config.groups import Group

def test_extra_titles_join_the_candidate_set(season):
    films = build_films(season, [Group("g", "G", {})], [], {}, set(), {}, {},
                        date(2026, 8, 15), extra_titles={"Play Pick"})
    assert [f.title for f in films] == ["Play Pick"]
    f = films[0]
    assert f.status == "pre_release" and f.release_date == season.window_end  # no info → defaults
```

- [ ] **Step 6: Run it to verify it fails**

Run: `.venv/bin/pytest tests/test_build_films.py -k extra_titles -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'extra_titles'`.

- [ ] **Step 7: Add the parameter**

In `smw/catalog/normalize.py`, change the `build_films` signature and candidate block:
```python
def build_films(
    season: Season,
    groups: list[Group],
    chart_rows: list[ChartRow],
    grosses: dict[str, float],
    carried: set[str],
    overrides: dict[str, Override],
    preopening: dict[str, PreopeningEstimate],
    today: date,
    extra_titles: Iterable[str] = (),
) -> list[Film]:
    chart_by_title = {r.title: r for r in chart_rows}

    # §6.2 candidate set: rosters ∪ estimate keys ∪ top chart contenders ∪ carried
    # ∪ play-along picks (play-along spec §6.3, already canonical).
    candidates: set[str] = set()
    for g in groups:
        for p in g.players.values():
            candidates.update(canonical(t, overrides) for t in p.ranked + p.dark_horses)
    candidates.update(canonical(t, overrides) for t in preopening)
    top_chart = sorted(chart_rows, key=lambda r: -r.gross)[: season.chart_contenders]
    candidates.update(r.title for r in top_chart)
    candidates.update(carried)
    candidates.update(extra_titles)
```
Add `from typing import Iterable` to the module imports.

- [ ] **Step 8: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_build_films.py -v`
Expected: PASS.

- [ ] **Step 9: Write the failing build-wiring tests**

Append to `tests/test_build.py`:
```python
PLAY_YAML = "api_base_url: https://smw-players.example.workers.dev\ndefault_group: [alice]\n"

def test_play_picks_enter_the_catalog(data_dir, tmp_path, monkeypatch):
    (data_dir / "play.yaml").write_text(PLAY_YAML)
    monkeypatch.setattr(build, "fetch_players", lambda url: [
        {"username": "zed", "joined_at": "2026-08-01T00:00:00Z",
         "ranked": ["Big Summer Film"] + [f"P{i}" for i in range(9)],
         "dark_horses": ["Deep Play Pick", "P9", "P10"]}])
    out = _run(data_dir, tmp_path)
    d = json.loads((out / "data.json").read_text())
    assert "Deep Play Pick" in {p["movie_title"] for p in d["projections"]}

def test_players_api_failure_warns_and_continues(data_dir, tmp_path, monkeypatch, capsys):
    (data_dir / "play.yaml").write_text(PLAY_YAML)
    def boom(url):
        raise ConnectionError("dns")
    monkeypatch.setattr(build, "fetch_players", boom)
    out = _run(data_dir, tmp_path)
    assert (out / "index.html").exists()          # friends site still publishes (§6.3)
    assert "players API unreachable" in capsys.readouterr().out

def test_no_play_yaml_means_no_players_fetch(data_dir, tmp_path, monkeypatch):
    def boom(url):
        raise AssertionError("must not be called")
    monkeypatch.setattr(build, "fetch_players", boom)
    _run(data_dir, tmp_path)
```

- [ ] **Step 10: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_build.py -k "play_picks or players_api or no_play_yaml" -v`
Expected: FAIL — `AttributeError: module 'smw.render.build' has no attribute 'fetch_players'`.

- [ ] **Step 11: Wire the fetch into `_build_season`**

In `smw/render/build.py`:

Imports — add:
```python
from smw.config.play import load_play
from smw.ingest import players as players_api
```
After `fetch = fetch_chart  # network seam; tests monkeypatch this` add:
```python
fetch_players = players_api.fetch_players  # play-along network seam; tests monkeypatch this
```
In `_build_season`, immediately after `history = load_history(history_path)`:
```python
    play_cfg = load_play(season_dir / "play.yaml")
    play_titles: set[str] = set()
    if play_cfg is not None:
        try:
            play_titles = {canonical(t, overrides)
                           for t in players_api.picked_titles(fetch_players(play_cfg.api_base_url))}
        except Exception as e:  # noqa: BLE001 — play-along §6.3: optional dependency, warn and continue
            print(f"warning: {season.year}: players API unreachable ({e}); "
                  "play-along picks are not in this build's catalog")
```
Change the `build_films(...)` call to pass `extra_titles=play_titles`, and after the `picked = {...}` comprehension add `picked |= play_titles`.

- [ ] **Step 12: Run the whole suite**

Run: `.venv/bin/pytest`
Expected: PASS.

- [ ] **Step 13: Commit**

```bash
git add smw/ingest/players.py tests/test_players_ingest.py smw/catalog/normalize.py \
        tests/test_build_films.py smw/render/build.py tests/test_build.py
git commit -m "feat(build): optional players-API fetch unions play-along picks into the catalog"
```

---

### Task 5: Play view model — `smw/render/play.py`

**Files:**
- Create: `smw/render/play.py`, `tests/test_play_data.py`

**Interfaces:**
- Consumes: `MovieCatalog`, `projected_ranks` (`smw/render/views.py`), `PlayConfig`, `STATIC`, `Markup`, `write_page` (`smw/render/page.py`).
- Produces:
  ```python
  def season_state(final: bool, forecastable: bool) -> str        # "final" | "live" | "early"
  def build_play_data(season, catalog, actual_top, forecastable, reason, today, cfg) -> dict
  def play_context(season: Season, today: date, rules_href: str) -> dict
  def render_play(env, out_dir: Path, ctx: dict, data: dict) -> None   # Task 7 fills the template
  def render_join(env, out_dir: Path, ctx: dict, data: dict, season_over: bool) -> None  # Task 8
  ```
  `build_play_data` dict keys: `year:int, state:str, reason:str|None, build_date:"YYYY-MM-DD", api_base_url:str, default_group:list[str], catalog:list[{title, release_date:"YYYY-MM-DD", release_label:"Jun 12", projected_rank:int|None, projected_median:float, status:str}] (sorted by release_date, title), actual_top:list[str], projected_top:list[str]` (empty in early state).

- [ ] **Step 1: Write the failing tests**

`tests/test_play_data.py`:
```python
from datetime import date
from smw.config.play import PlayConfig
from smw.render.play import build_play_data, play_context, season_state
from tests.test_views import _catalog

TODAY = date(2026, 8, 15)
CFG = PlayConfig("https://smw-players.example.workers.dev", ("alice", "bob"))

def _actual(cat):
    return [f.title for f in sorted(cat.films, key=lambda f: -f.cumulative_gross)][:10]

def test_season_state():
    assert season_state(final=True, forecastable=True) == "final"
    assert season_state(final=True, forecastable=False) == "final"
    assert season_state(final=False, forecastable=True) == "live"
    assert season_state(final=False, forecastable=False) == "early"

def test_live_shape(season):
    cat = _catalog()
    d = build_play_data(season, cat, _actual(cat), True, None, TODAY, CFG)
    assert d["year"] == 2026 and d["state"] == "live" and d["reason"] is None
    assert d["build_date"] == "2026-08-15"
    assert d["api_base_url"] == CFG.api_base_url
    assert d["default_group"] == ["alice", "bob"]
    assert d["projected_top"] == [f"M{i:02d}" for i in range(1, 11)]
    assert d["actual_top"] == _actual(cat)
    assert len(d["catalog"]) == 18
    row = next(c for c in d["catalog"] if c["title"] == "M01")
    assert row == {"title": "M01", "release_date": "2026-05-01", "release_label": "May 1",
                   "projected_rank": 1, "projected_median": 400e6, "status": "in_theaters"}

def test_catalog_sorted_by_release_then_title(season):
    cat = _catalog()
    d = build_play_data(season, cat, _actual(cat), True, None, TODAY, CFG)
    keys = [(c["release_date"], c["title"]) for c in d["catalog"]]
    assert keys == sorted(keys)

def test_early_state_has_no_projected_top(season):
    cat = _catalog()
    d = build_play_data(season, cat, _actual(cat), False, "only 3 films", TODAY, CFG)
    assert d["state"] == "early" and d["reason"] == "only 3 films"
    assert d["projected_top"] == []
    assert all(c["projected_rank"] is None for c in d["catalog"])

def test_play_context(season):
    ctx = play_context(season, TODAY, "smw-friends/rules.html")
    assert ctx["year"] == 2026 and ctx["refreshed"] == "Aug 15, 2026"
    assert ctx["rules_href"] == "smw-friends/rules.html"
    assert ctx["window_label"] == "May 1 – Sep 7, 2026"
    assert "css" in ctx and "theme_js" in ctx and "play_css" in ctx
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_play_data.py -v`
Expected: FAIL — `ModuleNotFoundError: smw.render.play`.

- [ ] **Step 3: Implement the module (render functions are stubs until Tasks 7–8 write the templates)**

`smw/render/play.py`:
```python
"""Play-along pages (play-along spec §5–§6): build-time embed + two renderers.
No scoring here — the client scores against the embedded lists (§5.3)."""
from datetime import date, timedelta
from pathlib import Path

from jinja2 import Environment
from markupsafe import Markup

from smw.config.play import PlayConfig
from smw.config.season import Season
from smw.model.project import MovieCatalog
from smw.render.page import STATIC, write_page
from smw.render.views import projected_ranks


def season_state(final: bool, forecastable: bool) -> str:
    """Base §10.1: Final wins, then the forecast gate decides Early vs Live."""
    if final:
        return "final"
    return "live" if forecastable else "early"


def build_play_data(season: Season, catalog: MovieCatalog, actual_top: list[str],
                    forecastable: bool, reason: str | None, today: date,
                    cfg: PlayConfig) -> dict:
    final = today > season.window_end + timedelta(days=1)   # base §10.1 Final
    state = season_state(final, forecastable)
    ranks = projected_ranks(catalog) if state != "early" else {}
    medians = {p.title: p.median for p in catalog.projections}
    projected_top = [t for t, _ in sorted(ranks.items(), key=lambda kv: kv[1])][:10]
    films = sorted(catalog.films, key=lambda f: (f.release_date, f.title))
    return {
        "year": season.year,
        "state": state,
        "reason": reason,
        "build_date": today.isoformat(),
        "api_base_url": cfg.api_base_url,
        "default_group": list(cfg.default_group),
        "catalog": [
            {"title": f.title,
             "release_date": f.release_date.isoformat(),
             "release_label": f.release_date.strftime("%b %-d"),
             "projected_rank": ranks.get(f.title),
             "projected_median": medians[f.title],
             "status": f.status}
            for f in films],
        "actual_top": list(actual_top),
        "projected_top": projected_top,
    }
```
Then append:
```python
def play_context(season: Season, today: date, rules_href: str) -> dict:
    return {
        "css": Markup((STATIC / "site.css").read_text()),
        "play_css": Markup((STATIC / "play.css").read_text()),
        "theme_js": Markup((STATIC / "theme.js").read_text()),
        "year": season.year,
        "window_label": (f"{season.window_start.strftime('%b %-d')} – "
                         f"{season.window_end.strftime('%b %-d, %Y')}"),
        "refreshed": today.strftime("%b %-d, %Y"),
        "rules_href": rules_href,
    }


def render_play(env: Environment, out_dir: Path, ctx: dict, data: dict) -> None:
    write_page(env, "play.html.j2", out_dir, "play.html", {
        **ctx, "active": "play", "title": "Play Along", "data": data,
        "scoring_js": Markup((STATIC / "scoring.js").read_text()),
        "play_js": Markup((STATIC / "play.js").read_text()),
    })


def render_join(env: Environment, out_dir: Path, ctx: dict, data: dict,
                season_over: bool) -> None:
    write_page(env, "join.html.j2", out_dir, "join.html", {
        **ctx, "active": "join", "title": "Join", "data": data,
        "season_over": season_over,
        "join_js": Markup((STATIC / "join.js").read_text()),
    })
```
Create an empty-for-now `smw/render/static/play.css` containing just:
```css
/* Play-along pages only (play-along spec §5); inlined after site.css. */
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_play_data.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add smw/render/play.py smw/render/static/play.css tests/test_play_data.py
git commit -m "feat(render): play-along build-time data and page context"
```

---

### Task 6: Client view composition + standings (`play.js` pure half, Node-tested)

**Files:**
- Create: `smw/render/static/play.js`, `tests/play_view.test.mjs`, `tests/test_play_js.py`
- Modify: `smw/render/static/scoring.js:31-33`

**Interfaces:**
- Consumes: `scorePlayer(ranked, dark, topTitles)`, `pointsFor(ranked, dark, title, topTitles)` from `scoring.js`.
- Produces (all in `play.js`, exported under `module.exports` when `module` exists):
  ```js
  parseParams(search: string) -> { user: string|null, follow: string[]|null }   // lowercased, trimmed, empties dropped
  composeView(params, players: Player[], defaultGroup: string[])
      -> { state: "bare"|"user"|"spectator"|"notfound", user: string|null, players: Player[], unknown: string[] }
      // players ordered: user first, then follow/default order, deduped
  columns(state: "early"|"live"|"final") -> string[]
  standings(players: Player[], actualTop: string[], projectedTop: string[])
      -> [{ username, joined: "YYYY-MM-DD", current: int, projected: int, place: int }]  // current desc, username asc; competition rank
  pickRows(player: Player, catalog: CatalogRow[], actualTop, projectedTop)
      -> [{ label: "1".."10"|"🐴", title, missing: bool, projected_rank: int|null, current: int, projected: int }]
  main()   // DOM; Task 7
  ```
  `Player` = `{username, joined_at, ranked: string[10], dark_horses: string[3]}` (the API shape).

- [ ] **Step 1: Export `pointsFor` from scoring.js**

Replace `smw/render/static/scoring.js` lines 31–33 with:
```js
if (typeof module !== "undefined") {
  module.exports = { rankedPickPoints: rankedPickPoints, scorePlayer: scorePlayer,
                     pointsFor: pointsFor };
}
```
Run: `.venv/bin/pytest tests/test_cross_impl.py -v` → PASS (unchanged behaviour).

- [ ] **Step 2: Write the failing Node tests**

`tests/play_view.test.mjs`:
```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "module";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const STATIC = join(here, "..", "smw", "render", "static");
const P = require(join(STATIC, "play.js"));

const TEN = Array.from({ length: 10 }, (_, i) => `M${String(i + 1).padStart(2, "0")}`);
function player(username, ranked = TEN, dark = ["M15", "M16", "M17"], joined = "2026-08-15T17:04:00Z") {
  return { username, joined_at: joined, ranked, dark_horses: dark };
}
const alice = player("alice");
const bob = player("bob", TEN.slice().reverse(), ["M15", "M18", "M14"]);
const carol = player("carol", ["M02", "M01", "M03", "M05", "M04", "M06", "M08", "M07", "M10", "M09"], ["M11", "M12", "M13"]);
const ALL = [alice, bob, carol];

test("parseParams lowercases, trims, drops empties", () => {
  assert.deepEqual(P.parseParams("?user=Alice&follow=Bob,%20carol,,"),
                   { user: "alice", follow: ["bob", "carol"] });
  assert.deepEqual(P.parseParams(""), { user: null, follow: null });
  assert.deepEqual(P.parseParams("?user=&follow="), { user: null, follow: [] });
});

test("bare URL: default group, nobody highlighted", () => {
  const v = P.composeView({ user: null, follow: null }, ALL, ["bob", "carol"]);
  assert.equal(v.state, "bare");
  assert.deepEqual(v.players.map((p) => p.username), ["bob", "carol"]);
  assert.deepEqual(v.unknown, []);
});

test("user view: user first, then default group, deduped", () => {
  const v = P.composeView({ user: "carol", follow: null }, ALL, ["bob", "carol"]);
  assert.equal(v.state, "user");
  assert.equal(v.user, "carol");
  assert.deepEqual(v.players.map((p) => p.username), ["carol", "bob"]);
});

test("follow replaces the default group", () => {
  const v = P.composeView({ user: "alice", follow: ["bob"] }, ALL, ["carol"]);
  assert.deepEqual(v.players.map((p) => p.username), ["alice", "bob"]);
});

test("spectator view: follow only, no user", () => {
  const v = P.composeView({ user: null, follow: ["bob", "carol"] }, ALL, ["alice"]);
  assert.equal(v.state, "spectator");
  assert.equal(v.user, null);
  assert.deepEqual(v.players.map((p) => p.username), ["bob", "carol"]);
});

test("unknown user is notfound, never an empty leaderboard", () => {
  const v = P.composeView({ user: "nobody", follow: ["bob"] }, ALL, ["alice"]);
  assert.equal(v.state, "notfound");
  assert.equal(v.user, "nobody");
  assert.deepEqual(v.players, []);
});

test("unknown follow names are skipped and listed; known ones still render", () => {
  const v = P.composeView({ user: null, follow: ["bob", "ghost", "zed"] }, ALL, []);
  assert.deepEqual(v.players.map((p) => p.username), ["bob"]);
  assert.deepEqual(v.unknown, ["ghost", "zed"]);
});

test("unknown default-group names are dropped silently", () => {
  const v = P.composeView({ user: null, follow: null }, ALL, ["ghost", "alice"]);
  assert.deepEqual(v.players.map((p) => p.username), ["alice"]);
  assert.deepEqual(v.unknown, []);
});

test("bare URL with empty default group shows nobody", () => {
  const v = P.composeView({ user: null, follow: null }, ALL, []);
  assert.equal(v.state, "bare");
  assert.deepEqual(v.players, []);
});

test("standings: current desc, competition rank, joined date only", () => {
  const actual = TEN;                       // alice perfect
  const rows = P.standings([bob, alice, carol], actual, actual);
  assert.deepEqual(rows.map((r) => [r.username, r.place]), [["alice", 1], ["carol", 2], ["bob", 3]]);
  assert.equal(rows[0].current, 106);
  assert.equal(rows[0].joined, "2026-08-15");
  const tie = P.standings([player("x"), player("y")], actual, actual);
  assert.deepEqual(tie.map((r) => [r.username, r.place]), [["x", 1], ["y", 1]]);
  const three = P.standings([player("x"), player("y"), bob], actual, actual);
  assert.deepEqual(three.map((r) => r.place), [1, 1, 3]);
});

test("standings scores projected against the projected list", () => {
  const rows = P.standings([alice], TEN.slice().reverse(), TEN);
  assert.equal(rows[0].projected, 106);
  assert.notEqual(rows[0].current, 106);
});

test("columns omit Projected in the early state only", () => {
  assert.deepEqual(P.columns("early"), ["Place", "Player", "Joined", "Current pts"]);
  assert.deepEqual(P.columns("live"), ["Place", "Player", "Joined", "Current pts", "Projected pts"]);
  assert.deepEqual(P.columns("final"), P.columns("live"));
});

test("pickRows: 13 rows, dark horses labelled, missing picks inert", () => {
  const catalog = TEN.concat(["M15"]).map((t, i) => ({ title: t, projected_rank: i + 1 }));
  const p = player("z", TEN, ["M15", "Not In Catalog", "M17"]);
  const rows = P.pickRows(p, catalog, TEN, TEN);
  assert.equal(rows.length, 13);
  assert.deepEqual(rows.slice(10).map((r) => r.label), ["🐴", "🐴", "🐴"]);
  assert.equal(rows[0].label, "1");
  assert.equal(rows[0].current, 13);
  assert.equal(rows[0].projected_rank, 1);
  const missing = rows.find((r) => r.title === "Not In Catalog");
  assert.deepEqual([missing.missing, missing.projected_rank, missing.current, missing.projected],
                   [true, null, 0, 0]);
  const m17 = rows.find((r) => r.title === "M17");   // absent from catalog too
  assert.equal(m17.missing, true);
});

test("hostile strings pass through composition verbatim (DOM layer uses textContent)", () => {
  const evil = "</script><img src=x onerror=alert(1)>";
  const p = player(evil, [evil].concat(TEN.slice(1)), ["M15", "M16", "M17"]);
  const v = P.composeView({ user: evil.toLowerCase(), follow: ["<b>x</b>"] }, [p], []);
  // composeView compares normalised param to the stored username; evil has uppercase-free chars so it matches
  assert.equal(v.state, "user");
  assert.equal(v.players[0].username, evil);
  assert.deepEqual(v.unknown, ["<b>x</b>"]);
  const rows = P.pickRows(p, [{ title: evil, projected_rank: 1 }], [evil], [evil]);
  assert.equal(rows[0].title, evil);
});

test("play.js and join.js never build HTML from strings", () => {
  for (const f of ["play.js", "join.js"]) {
    const src = readFileSync(join(STATIC, f), "utf8");
    for (const banned of ["insertAdjacentHTML", "outerHTML", "document.write"])
      assert.ok(!src.includes(banned), `${f} uses ${banned}`);
    for (const m of src.matchAll(/innerHTML\s*=\s*([^;]+);/g))
      assert.equal(m[1].trim(), '""', `${f}: innerHTML assigned ${m[1]}`);
  }
});
```
(The last test reads `join.js`, created in Task 8. Until then it fails on that file only — that is expected; Task 8 turns it green.)

`tests/test_play_js.py`:
```python
import shutil
import subprocess
import pytest
from tests.conftest import FIXTURES

@pytest.mark.skipif(shutil.which("node") is None,
                    reason="node required for the client-side play-along tests — "
                           "install node; do not delete this test")
def test_play_view_composition_and_join_validation():
    result = subprocess.run(
        ["node", "--test", str(FIXTURES.parent / "play_view.test.mjs"),
         str(FIXTURES.parent / "join_validate.test.mjs")],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
```
(`join_validate.test.mjs` arrives in Task 8; until then run the `.mjs` file directly as below.)

- [ ] **Step 3: Run to verify it fails**

Run: `node --test tests/play_view.test.mjs`
Expected: FAIL — cannot find module `play.js`.

- [ ] **Step 4: Implement the pure half of `play.js`**

`smw/render/static/play.js`:
```js
"use strict";
// Play-along standings (play-along spec §4–§5). Pure functions first (Node-tested),
// DOM last. Every API-derived string reaches the page via textContent only (§5.4).
var S = (typeof module !== "undefined")
  ? require("./scoring.js")
  : { scorePlayer: scorePlayer, pointsFor: pointsFor };

function norm(s) { return String(s).trim().toLowerCase(); }

function parseParams(search) {
  var q = new URLSearchParams(search);
  var user = q.has("user") ? norm(q.get("user")) : "";
  var follow = null;
  if (q.has("follow")) follow = q.get("follow").split(",").map(norm).filter(Boolean);
  return { user: user || null, follow: follow };
}

// §4.2: view_set = {user} ∪ (follow if present, else default group)
function composeView(params, players, defaultGroup) {
  var byName = {};
  players.forEach(function (p) { byName[p.username] = p; });
  if (params.user && !Object.prototype.hasOwnProperty.call(byName, params.user))
    return { state: "notfound", user: params.user, players: [], unknown: [] };
  var wanted = params.follow !== null ? params.follow : defaultGroup;
  var names = (params.user ? [params.user] : []).concat(wanted);
  var seen = {}, out = [], unknown = [];
  names.forEach(function (n) {
    if (seen[n]) return;
    seen[n] = true;
    if (Object.prototype.hasOwnProperty.call(byName, n)) out.push(byName[n]);
    else if (params.follow !== null) unknown.push(n);   // default-group misses are silent
  });
  var state = params.user ? "user" : (params.follow !== null ? "spectator" : "bare");
  return { state: state, user: params.user, players: out, unknown: unknown };
}

function columns(state) {
  var cols = ["Place", "Player", "Joined", "Current pts"];
  if (state !== "early") cols.push("Projected pts");
  return cols;
}

function standings(players, actualTop, projectedTop) {
  var rows = players.map(function (p) {
    return { username: p.username, joined: String(p.joined_at).slice(0, 10),
             current: S.scorePlayer(p.ranked, p.dark_horses, actualTop),
             projected: S.scorePlayer(p.ranked, p.dark_horses, projectedTop) };
  });
  rows.sort(function (a, b) { return b.current - a.current || (a.username < b.username ? -1 : 1); });
  var place = 0, prev = null;
  rows.forEach(function (r, i) {
    if (r.current !== prev) { place = i + 1; prev = r.current; }   // competition ranking 1,1,3
    r.place = place;
  });
  return rows;
}

function pickRows(p, catalog, actualTop, projectedTop) {
  var rank = {};
  catalog.forEach(function (f) { rank[f.title] = f.projected_rank; });
  var rows = [];
  function add(label, t) {
    var known = Object.prototype.hasOwnProperty.call(rank, t);
    rows.push({
      label: label, title: t, missing: !known,
      projected_rank: known ? rank[t] : null,
      current: known ? S.pointsFor(p.ranked, p.dark_horses, t, actualTop) : 0,
      projected: known ? S.pointsFor(p.ranked, p.dark_horses, t, projectedTop) : 0,
    });
  }
  p.ranked.forEach(function (t, i) { add(String(i + 1), t); });
  p.dark_horses.forEach(function (t) { add("🐴", t); });
  return rows;
}

function main() { /* Task 7 */ }

if (typeof module !== "undefined") {
  module.exports = { parseParams: parseParams, composeView: composeView, columns: columns,
                     standings: standings, pickRows: pickRows };
}
if (typeof window !== "undefined" && window.PLAY) main();
```

- [ ] **Step 5: Run to verify the pure tests pass**

Run: `node --test tests/play_view.test.mjs`
Expected: all PASS except `play.js and join.js never build HTML from strings` (ENOENT on `join.js` — Task 8).

- [ ] **Step 6: Commit**

```bash
git add smw/render/static/scoring.js smw/render/static/play.js tests/play_view.test.mjs tests/test_play_js.py
git commit -m "feat(play): client view composition, standings and pick rows (pure, node-tested)"
```

---

### Task 7: `play.html` — templates, DOM rendering, render tests

**Files:**
- Create: `smw/render/templates/play_base.html.j2`, `smw/render/templates/play.html.j2`, `tests/test_play_render.py`, `tests/fixtures/snapshot_play.html` (generated by the ritual)
- Modify: `smw/render/static/play.js` (`main`), `smw/render/static/play.css`

**Interfaces:**
- Consumes: `build_play_data`, `play_context`, `render_play` (Task 5); `parseParams`, `composeView`, `columns`, `standings`, `pickRows` (Task 6).
- Produces: `play.html` with `window.PLAY = {…}`, ids `playLoading playError playNotFound playMissingName playExplainer playBoard playHeading playUnknown playTable playDetail playDetailHeading playJoined playPicks`.

- [ ] **Step 1: Write the failing render tests**

`tests/test_play_render.py`:
```python
from datetime import date
from smw.config.play import PlayConfig
from smw.model.project import MovieCatalog
from smw.render.page import make_env
from smw.render.play import build_play_data, play_context, render_play
from tests.conftest import FIXTURES
from tests.test_views import _catalog, _film, _proj

TODAY = date(2026, 8, 15)
CFG = PlayConfig("https://smw-players.example.workers.dev", ("alice",))

def _actual(cat):
    return [f.title for f in sorted(cat.films, key=lambda f: -f.cumulative_gross)][:10]

def _render(tmp_path, season, cat=None, forecastable=True, reason=None, today=TODAY):
    cat = cat or _catalog()
    env = make_env()
    data = build_play_data(season, cat, _actual(cat), forecastable, reason, today, CFG)
    render_play(env, tmp_path, play_context(season, today, "g/rules.html"), data)
    return (tmp_path / "play.html").read_text()

def test_skeleton_and_states(tmp_path, season):
    html = _render(tmp_path, season)
    for s in ('window.PLAY=', '"api_base_url":"https://smw-players.example.workers.dev"',
              'id="playLoading"', "Loading players…",
              'id="playError"', "Couldn't load players — try again in a minute.",
              'id="playNotFound"', "No player named", 'href="join.html"',
              'id="playExplainer"', 'id="playBoard"', 'id="playTable"', 'id="playDetail"',
              "rankedPickPoints", "function composeView", 'fetch(D.api_base_url'):
        assert s in html, s
    assert html.count("fetch(") == 1

def test_own_nav_and_footer(tmp_path, season):
    html = _render(tmp_path, season)
    nav = html.split('<nav class="pills"', 1)[1].split("</nav>", 1)[0]
    assert 'href="play.html" aria-current="page"' in nav and 'href="join.html"' in nav
    for gone in ("index.html", "whatif.html", "scenarios.html", "history.html"):
        assert gone not in nav, gone
    assert 'href="g/rules.html"' in html
    assert "Films &amp; projections as of Aug 15, 2026 · players live." in html
    assert "<title>Play Along · Summer Movie Wager 2026 · Play Along</title>" in html
    assert "yearSelect" not in html and "groupSelect" not in html   # not a friends page

def test_early_state_has_no_projected_anywhere_outside_js(tmp_path, season):
    html = _render(tmp_path, season, forecastable=False, reason="only 3 films have projections")
    assert '"state":"early"' in html and '"projected_top":[]' in html
    assert "only 3 films have projections" in html
    markup = html.split("<script>window.PLAY=", 1)[0]
    assert "Projected" not in markup

def test_hostile_title_is_escaped_in_embed(tmp_path, season):
    evil = "</script><img src=x onerror=alert(1)>"
    projs = [_proj(evil, 5e8)] + [_proj(f"M{i:02d}", 400e6 / i, floor=100e6 / i) for i in range(1, 12)]
    cat = MovieCatalog([_film(p.title, gross=p.floor or 1.0) for p in projs], projs, [])
    html = _render(tmp_path, season, cat=cat)
    assert "\\u003c/script>\\u003cimg" in html
    assert evil not in html

def test_no_external_reference_but_the_api(tmp_path, season):
    html = _render(tmp_path, season).replace(CFG.api_base_url, "")
    for marker in ("http://", "https://", "//cdn", "@import", "url(http", "XMLHttpRequest"):
        assert marker not in html, marker

def test_play_snapshot(tmp_path, season):
    """Byte-exact snapshot. REGENERATION RITUAL: delete tests/fixtures/snapshot_play.html,
    run this test once (it rewrites the fixture and fails), OPEN THE FILE IN A BROWSER
    AND LOOK AT IT (it will show the 'Couldn't load players' state — that is correct
    offline), then re-run to lock."""
    html = _render(tmp_path, season)
    fixture = FIXTURES / "snapshot_play.html"
    if not fixture.exists():
        fixture.write_text(html)
        raise AssertionError("Snapshot fixture created; inspect it in a browser, then re-run.")
    assert html == fixture.read_text()
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_play_render.py -v`
Expected: FAIL — `TemplateNotFound: play.html.j2`.

- [ ] **Step 3: Write the templates**

`smw/render/templates/play_base.html.j2`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} · Summer Movie Wager {{ year }} · Play Along</title>
<script>{{ theme_js }}</script>
<style>{{ css }}
{{ play_css }}</style>
</head>
<body>
<div class="wrap">

<header class="site">
  <div>
    <h1>🍿 Summer Movie Wager</h1>
    <div class="sub">Play along &nbsp;·&nbsp; Wager window: {{ window_label }}</div>
  </div>
  <button id="themeToggle" type="button" aria-label="Toggle color theme">◐ Theme</button>
</header>

<nav class="pills" aria-label="Play along">
  <a href="play.html"{% if active == "play" %} aria-current="page"{% endif %}>🎟 Play Along</a>
  <a href="join.html"{% if active == "join" %} aria-current="page"{% endif %}>✍️ Join</a>
</nav>

{% block content %}{% endblock %}

<footer class="site">
  <a href="{{ rules_href }}">Scoring rules</a> &nbsp;·&nbsp;
  <span class="small">Films &amp; projections as of {{ refreshed }} · players live.</span>
</footer>

</div>
</body>
</html>
```

`smw/render/templates/play.html.j2`:
```html
{% extends "play_base.html.j2" %}
{% block content %}
{% if data.state == "early" -%}
<p class="small">No projections yet — {{ data.reason }}. Standings show current points only until the forecast is live.</p>
{% endif -%}
<section id="playLoading"><p class="small">Loading players…</p></section>
<section id="playError" hidden><div class="locked">Couldn't load players — try again in a minute.</div></section>
<section id="playNotFound" hidden><div class="locked">No player named <strong id="playMissingName"></strong> — check the spelling, or <a href="join.html">join below</a>.</div></section>
<section id="playExplainer" hidden>
  <h2>🎟 Play along</h2>
  <p>Pick the summer's top ten grossing films in order, plus three dark horses, and follow your
  standings all season. Anyone can play, any time — <a href="join.html">join here</a>. Your picks
  are final once submitted; your personal page lives at <code>play.html?user=your-name</code>, and
  <code>play.html?follow=a,b,c</code> shows any group of players you name.</p>
</section>
<section id="playBoard" hidden>
  <h2 id="playHeading">🏆 Standings</h2>
  <p id="playUnknown" class="small" hidden></p>
  <div class="scroller"><table id="playTable"><thead><tr></tr></thead><tbody></tbody></table></div>
</section>
<section id="playDetail" hidden>
  <h2 id="playDetailHeading"></h2>
  <p id="playJoined" class="small"></p>
  <div class="scroller"><table id="playPicks"><thead><tr></tr></thead><tbody></tbody></table></div>
</section>
<script>window.PLAY={{ data | json_embed }};</script>
<script>{{ scoring_js }}</script>
<script>{{ play_js }}</script>
{% endblock %}
```

`smw/render/static/play.css` (replace the file):
```css
/* Play-along pages only (play-along spec §5); inlined after site.css. */
section[hidden]{display:none}
tr.me td{background:var(--hl)}
code{background:var(--pill);border-radius:4px;padding:1px 5px;font-size:.9em}
.join-grid{display:grid;grid-template-columns:auto 1fr;gap:8px 12px;align-items:center;max-width:640px}
.join-grid label{text-align:right;color:var(--ink2)}
.join-grid input{background:var(--surface);color:var(--ink);border:1px solid var(--border);
  border-radius:8px;padding:8px 10px;font:inherit;width:100%}
.join-grid .div{grid-column:1/-1;border-bottom:2px dashed var(--baseline);color:var(--muted);
  padding:8px 0 4px;font-size:.85rem}
.join-actions{margin:16px 0}
.join-actions button,#joinCopy{background:var(--accent);color:#fff;border:0;border-radius:999px;
  padding:8px 18px;font:inherit;cursor:pointer}
.join-error{color:var(--neg);margin:8px 0}
```

- [ ] **Step 4: Write `main()` in `play.js`**

Replace `function main() { /* Task 7 */ }` with:
```js
function main() {
  var D = window.PLAY;
  function $(id) { return document.getElementById(id); }
  function show(id) { $(id).hidden = false; }
  function cell(tr, text, cls, tag) {
    var el = document.createElement(tag || "td");
    if (cls) el.className = cls;
    el.textContent = text;
    tr.appendChild(el);
  }
  var params = parseParams(window.location.search);

  function renderBoard(view) {
    var head = document.querySelector("#playTable thead tr");
    columns(D.state).forEach(function (c, i) { cell(head, c, i === 1 ? "t" : "", "th"); });
    var tbody = document.querySelector("#playTable tbody");
    standings(view.players, D.actual_top, D.projected_top).forEach(function (r) {
      var tr = document.createElement("tr");
      if (r.username === view.user) tr.className = "me";
      cell(tr, r.place);
      cell(tr, r.username, r.place === 1 ? "t crown" : "t");
      cell(tr, r.joined);
      cell(tr, r.current, r.current > 0 ? "pos" : "zero");
      if (D.state !== "early") cell(tr, r.projected, r.projected > 0 ? "pos" : "zero");
      tbody.appendChild(tr);
    });
    if (view.unknown.length) {
      $("playUnknown").textContent = "Unknown players skipped: " + view.unknown.join(", ");
      $("playUnknown").hidden = false;
    }
    show("playBoard");
  }

  function renderDetail(p) {
    $("playDetailHeading").textContent = "👤 " + p.username + "'s picks";
    $("playJoined").textContent = "Joined " + String(p.joined_at).slice(0, 10) + " (UTC)";
    var head = document.querySelector("#playPicks thead tr");
    var cols = ["#", "Movie", "Projected rank", "Current pts"];
    if (D.state !== "early") cols.push("Projected pts");
    cols.forEach(function (c, i) { cell(head, c, i === 1 ? "t" : "", "th"); });
    var tbody = document.querySelector("#playPicks tbody");
    pickRows(p, D.catalog, D.actual_top, D.projected_top).forEach(function (r, i) {
      if (i === 10) {
        var div = document.createElement("tr");
        div.className = "divider";
        var td = document.createElement("td");
        td.colSpan = cols.length;
        td.textContent = "Dark horses";
        div.appendChild(td);
        tbody.appendChild(div);
      }
      var tr = document.createElement("tr");
      cell(tr, r.label);
      cell(tr, r.title, "t");
      if (r.missing) cell(tr, "not tracked", "dash");                    // base §10.2 placeholder
      else cell(tr, r.projected_rank ? "#" + r.projected_rank : "—", r.projected_rank ? "" : "dash");
      cell(tr, r.current, r.current > 0 ? "pos" : "zero");
      if (D.state !== "early") cell(tr, r.projected, r.projected > 0 ? "pos" : "zero");
      tbody.appendChild(tr);
    });
    show("playDetail");
  }

  function render(view) {
    $("playLoading").hidden = true;
    if (view.state === "notfound") {
      $("playMissingName").textContent = view.user;
      show("playNotFound");
      return;
    }
    if (view.state === "bare") show("playExplainer");
    if (view.players.length || view.unknown.length) renderBoard(view);
    if (view.state === "user") renderDetail(view.players[0]);   // composeView puts the user first
  }

  fetch(D.api_base_url + "/api/players", { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (body) { render(composeView(params, body.players, D.default_group)); })
    .catch(function () { $("playLoading").hidden = true; show("playError"); });
}
```

- [ ] **Step 5: Run the render tests; do the snapshot ritual**

Run: `.venv/bin/pytest tests/test_play_render.py -v`
Expected: all PASS except `test_play_snapshot`, which writes `tests/fixtures/snapshot_play.html` and fails once. Open that file in a browser, confirm the masthead, two-pill nav, "Couldn't load players" state (offline) and footer look right, then re-run → PASS.

Run: `node --test tests/play_view.test.mjs` → still only the `join.js` ENOENT failure.

- [ ] **Step 6: Commit**

```bash
git add smw/render/templates/play_base.html.j2 smw/render/templates/play.html.j2 \
        smw/render/static/play.js smw/render/static/play.css \
        tests/test_play_render.py tests/fixtures/snapshot_play.html
git commit -m "feat(play): play.html standings page with live roster fetch"
```

---

### Task 8: `join.html` — signup form

**Files:**
- Create: `smw/render/templates/join.html.j2`, `smw/render/static/join.js`, `tests/join_validate.test.mjs`, `tests/test_join_render.py`, `tests/fixtures/snapshot_join.html` (ritual)

**Interfaces:**
- Consumes: `render_join`, `build_play_data`, `play_context` (Task 5); `window.PLAY.catalog[].title/.release_label`, `window.PLAY.api_base_url`.
- Produces (`join.js`, exported under `module.exports`):
  ```js
  USERNAME_RE: RegExp   // /^[a-z0-9][a-z0-9-]{1,22}[a-z0-9]$/
  validateSubmission(username: string, ranked: string[], dark: string[], titles: Set<string>|string[])
      -> { ok: true, body: {username, ranked, dark_horses} } | { ok: false, error: string }
  ```
  Form ids: `joinForm username joinError joinDone joinName joinLink joinCopy`; inputs `name="ranked"` ×10 and `name="dark"` ×3, each `list="films"`.

- [ ] **Step 1: Write the failing Node tests**

`tests/join_validate.test.mjs`:
```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "module";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const J = require(join(here, "..", "smw", "render", "static", "join.js"));

const TEN = Array.from({ length: 10 }, (_, i) => `Film ${i + 1}`);
const TITLES = new Set(TEN.concat(["DH1", "DH2", "DH3", "Spare"]));

test("valid submission builds the §3.3 body", () => {
  const r = J.validateSubmission("popcorn-goblin", TEN, ["DH1", "DH2", "DH3"], TITLES);
  assert.deepEqual(r, { ok: true, body: { username: "popcorn-goblin", ranked: TEN, dark_horses: ["DH1", "DH2", "DH3"] } });
});

test("username is lowercased and trimmed before the rule", () => {
  const r = J.validateSubmission("  Popcorn-Goblin ", TEN, ["DH1", "DH2", "DH3"], TITLES);
  assert.equal(r.ok, true);
  assert.equal(r.body.username, "popcorn-goblin");
});

test("bad username names the rule", () => {
  for (const u of ["ab", "-abc", "abc-", "a b", "a".repeat(25)]) {
    const r = J.validateSubmission(u, TEN, ["DH1", "DH2", "DH3"], TITLES);
    assert.equal(r.ok, false);
    assert.match(r.error, /3–24/);
  }
});

test("empty slot is reported by position", () => {
  const r = J.validateSubmission("abc", TEN.slice(0, 9).concat([""]), ["DH1", "DH2", "DH3"], TITLES);
  assert.equal(r.ok, false);
  assert.match(r.error, /pick 10/i);
  const d = J.validateSubmission("abc", TEN, ["DH1", "", "DH3"], TITLES);
  assert.match(d.error, /dark horse 2/i);
});

test("free-text titles are not submittable", () => {
  const r = J.validateSubmission("abc", TEN, ["DH1", "DH2", "Made Up Film"], TITLES);
  assert.equal(r.ok, false);
  assert.match(r.error, /Made Up Film/);
  assert.match(r.error, /list/i);
});

test("duplicates are rejected with both slots named", () => {
  const r = J.validateSubmission("abc", TEN, ["Film 1", "DH2", "DH3"], TITLES);
  assert.equal(r.ok, false);
  assert.match(r.error, /Film 1/);
  assert.match(r.error, /twice|distinct/i);
});

test("titles are trimmed but otherwise exact", () => {
  const r = J.validateSubmission("abc", TEN, [" DH1 ", "DH2", "DH3"], TITLES);
  assert.equal(r.ok, true);
  assert.equal(r.body.dark_horses[0], "DH1");
  const c = J.validateSubmission("abc", TEN, ["dh1", "DH2", "DH3"], TITLES);
  assert.equal(c.ok, false);
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `node --test tests/join_validate.test.mjs`
Expected: FAIL — cannot find module `join.js`.

- [ ] **Step 3: Write `join.js`**

`smw/render/static/join.js`:
```js
"use strict";
// Play-along signup (play-along spec §5.2). Pure validation first (Node-tested), DOM last.
var USERNAME_RE = /^[a-z0-9][a-z0-9-]{1,22}[a-z0-9]$/;
var USERNAME_RULE = "3–24 characters: lowercase letters, digits, and hyphens (not at the ends)";

function validateSubmission(username, ranked, dark, titles) {
  var has = titles instanceof Set ? function (t) { return titles.has(t); }
                                  : function (t) { return titles.indexOf(t) >= 0; };
  var u = String(username).trim().toLowerCase();
  if (!USERNAME_RE.test(u)) return { ok: false, error: "Username must be " + USERNAME_RULE + "." };
  var r = ranked.map(function (t) { return String(t).trim(); });
  var d = dark.map(function (t) { return String(t).trim(); });
  var labels = r.map(function (_, i) { return "pick " + (i + 1); })
    .concat(d.map(function (_, i) { return "dark horse " + (i + 1); }));
  var all = r.concat(d), seen = {};
  for (var i = 0; i < all.length; i++) {
    var t = all[i];
    if (!t) return { ok: false, error: "Choose a film for " + labels[i] + "." };
    if (!has(t)) return { ok: false, error: "\u201C" + t + "\u201D (" + labels[i] + ") isn't on the list — pick a film from the list." };
    if (seen[t] !== undefined)
      return { ok: false, error: "\u201C" + t + "\u201D is picked twice (" + labels[seen[t]] + " and " + labels[i] + ") — all 13 must be distinct." };
    seen[t] = i;
  }
  return { ok: true, body: { username: u, ranked: r, dark_horses: d } };
}

function main() {
  var D = window.PLAY;
  var form = document.getElementById("joinForm");
  if (!form) return;   // season over: no form rendered
  var titles = new Set(D.catalog.map(function (f) { return f.title; }));
  var err = document.getElementById("joinError");
  var user = document.getElementById("username");
  function fail(msg) { err.textContent = msg; err.hidden = false; }
  function values(name) {
    return Array.prototype.map.call(form.querySelectorAll('input[name="' + name + '"]'),
                                    function (el) { return el.value; });
  }
  user.addEventListener("input", function () {            // §5.2: rule shown before they trip over it
    var u = user.value.trim().toLowerCase();
    user.setCustomValidity(u && !USERNAME_RE.test(u) ? USERNAME_RULE : "");
  });
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    err.hidden = true;
    var v = validateSubmission(user.value, values("ranked"), values("dark"), titles);
    if (!v.ok) { fail(v.error); return; }
    var btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    fetch(D.api_base_url + "/api/players", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(v.body),
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (body) {
        if (r.status === 201) return done(body.username);
        if (r.status === 409) { fail("That username is taken — pick another."); user.focus(); return; }
        fail("Couldn't submit (" + r.status + "): " + (body.error || "unknown error") + ". Nothing was cleared — fix and try again.");
      });
    }).catch(function () {
      fail("Couldn't reach the players API — check your connection and try again. Your picks are still here.");
    }).then(function () { btn.disabled = false; });
  });
  function done(username) {
    var link = new URL("play.html?user=" + encodeURIComponent(username), window.location.href).href;
    document.getElementById("joinName").textContent = username;
    var a = document.getElementById("joinLink");
    a.textContent = link;
    a.href = link;
    document.getElementById("joinCopy").addEventListener("click", function () {
      if (navigator.clipboard) navigator.clipboard.writeText(link);
    });
    form.hidden = true;
    document.getElementById("joinDone").hidden = false;
  }
}

if (typeof module !== "undefined") {
  module.exports = { USERNAME_RE: USERNAME_RE, validateSubmission: validateSubmission };
}
if (typeof window !== "undefined" && window.PLAY) main();
```

- [ ] **Step 4: Run the Node tests**

Run: `node --test tests/play_view.test.mjs tests/join_validate.test.mjs`
Expected: all PASS (including the `innerHTML` static check, now that `join.js` exists).

- [ ] **Step 5: Write the failing Python render tests**

`tests/test_join_render.py`:
```python
from datetime import date
from smw.config.play import PlayConfig
from smw.render.page import make_env
from smw.render.play import build_play_data, play_context, render_join
from tests.conftest import FIXTURES
from tests.test_views import _catalog

TODAY = date(2026, 8, 15)
CFG = PlayConfig("https://smw-players.example.workers.dev", ())

def _render(tmp_path, season, season_over=False, today=TODAY):
    cat = _catalog()
    actual = [f.title for f in sorted(cat.films, key=lambda f: -f.cumulative_gross)][:10]
    env = make_env()
    data = build_play_data(season, cat, actual, True, None, today, CFG)
    render_join(env, tmp_path, play_context(season, today, "g/rules.html"), data, season_over)
    return (tmp_path / "join.html").read_text()

def test_form_shape(tmp_path, season):
    html = _render(tmp_path, season)
    assert 'id="joinForm"' in html and 'id="username"' in html
    assert 'pattern="[a-z0-9][a-z0-9-]{1,22}[a-z0-9]"' in html
    assert "3–24 characters: lowercase letters, digits, and hyphens (not at the ends)" in html
    assert html.count('name="ranked"') == 10 and html.count('name="dark"') == 3
    assert html.count('list="films"') == 13
    assert '<datalist id="films">' in html
    assert '<option value="M01">May 1</option>' in html     # title + release date (§5.2)
    assert html.count("<option value=") == 18
    for s in ('id="joinError"', 'id="joinDone"', 'id="joinName"', 'id="joinLink"', 'id="joinCopy"',
              "Picks are final", "updates weekly", "function validateSubmission",
              'href="join.html" aria-current="page"'):
        assert s in html, s
    assert html.count("fetch(") == 1

def test_season_over_replaces_form(tmp_path, season):
    html = _render(tmp_path, season, season_over=True)
    assert "Season's over" in html and 'href="play.html"' in html
    assert 'id="joinForm"' not in html
    assert "window.PLAY=" in html          # join.js still inlined; main() no-ops without the form

def test_hostile_title_in_datalist_is_escaped(tmp_path, season):
    from smw.model.project import MovieCatalog
    from tests.test_views import _film, _proj
    evil = '"><script>alert(1)</script>'
    projs = [_proj(evil, 5e8)] + [_proj(f"M{i:02d}", 400e6 / i, floor=100e6 / i) for i in range(1, 12)]
    cat = MovieCatalog([_film(p.title, gross=p.floor or 1.0) for p in projs], projs, [])
    actual = [f.title for f in sorted(cat.films, key=lambda f: -f.cumulative_gross)][:10]
    env = make_env()
    data = build_play_data(season, cat, actual, True, None, TODAY, CFG)
    render_join(env, tmp_path, play_context(season, TODAY, "g/rules.html"), data, False)
    html = (tmp_path / "join.html").read_text()
    assert "<script>alert(1)</script>" not in html
    assert "&#34;&gt;&lt;script&gt;" in html or "&quot;&gt;&lt;script&gt;" in html

def test_no_external_reference_but_the_api(tmp_path, season):
    html = _render(tmp_path, season).replace(CFG.api_base_url, "")
    for marker in ("http://", "https://", "//cdn", "@import", "url(http", "XMLHttpRequest"):
        assert marker not in html, marker

def test_join_snapshot(tmp_path, season):
    """Byte-exact snapshot. REGENERATION RITUAL: delete tests/fixtures/snapshot_join.html,
    run once (writes the fixture and fails), OPEN IT IN A BROWSER AND LOOK AT IT, re-run to lock."""
    html = _render(tmp_path, season)
    fixture = FIXTURES / "snapshot_join.html"
    if not fixture.exists():
        fixture.write_text(html)
        raise AssertionError("Snapshot fixture created; inspect it in a browser, then re-run.")
    assert html == fixture.read_text()
```

- [ ] **Step 6: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_join_render.py -v`
Expected: FAIL — `TemplateNotFound: join.html.j2`.

- [ ] **Step 7: Write the template**

`smw/render/templates/join.html.j2`:
```html
{% extends "play_base.html.j2" %}
{% block content %}
{% if season_over -%}
<div class="locked">Season's over — <a href="play.html">see the final standings</a>.</div>
{% else -%}
<h2>✍️ Join the play-along</h2>
<p class="sub">Rank the ten films you think will gross the most this summer, add three dark horses,
pick a username, and you're in. Picks are final — no edits — so read them twice.</p>
<form id="joinForm" novalidate>
  <div class="join-grid">
    <label for="username">Username</label>
    <div>
      <input id="username" name="username" required autocapitalize="none" autocomplete="off"
             spellcheck="false" pattern="[a-z0-9][a-z0-9-]{1,22}[a-z0-9]" maxlength="24">
      <div class="small">3–24 characters: lowercase letters, digits, and hyphens (not at the ends)</div>
    </div>
    {% for i in range(1, 11) -%}
    <label for="ranked{{ i }}">#{{ i }}</label>
    <input id="ranked{{ i }}" name="ranked" list="films" autocomplete="off" required>
    {% endfor -%}
    <div class="div">Dark horses — three films you think will sneak into the top ten (1 pt each, any position)</div>
    {% for i in range(1, 4) -%}
    <label for="dark{{ i }}">🐴 {{ i }}</label>
    <input id="dark{{ i }}" name="dark" list="films" autocomplete="off" required>
    {% endfor -%}
  </div>
  <datalist id="films">{% for f in data.catalog %}<option value="{{ f.title }}">{{ f.release_label }}</option>{% endfor %}</datalist>
  <p class="small">Type to search; every slot must be a film from the list, and all 13 must be different.</p>
  <p id="joinError" class="join-error" role="alert" hidden></p>
  <div class="join-actions"><button type="submit">Submit my picks</button></div>
</form>
<section id="joinDone" hidden>
  <h2>🎉 You're in, <span id="joinName"></span>!</h2>
  <p>Your standings live at <a id="joinLink"></a> <button id="joinCopy" type="button">Copy link</button></p>
  <p class="small">Picks are final. Film numbers on the leaderboard update weekly; the player list is live.</p>
</section>
{% endif -%}
<script>window.PLAY={{ data | json_embed }};</script>
<script>{{ join_js }}</script>
{% endblock %}
```

- [ ] **Step 8: Run the render tests; do the snapshot ritual**

Run: `.venv/bin/pytest tests/test_join_render.py -v`
Expected: PASS except `test_join_snapshot` on its first run — inspect `tests/fixtures/snapshot_join.html` in a browser (type in a slot to see the datalist with dates; submit empty to see the inline error), then re-run → PASS.

Run: `.venv/bin/pytest tests/test_play_js.py -v` → PASS.

- [ ] **Step 9: Commit**

```bash
git add smw/render/templates/join.html.j2 smw/render/static/join.js \
        tests/join_validate.test.mjs tests/test_join_render.py tests/fixtures/snapshot_join.html
git commit -m "feat(play): join.html signup form with datalist candidates and one-shot POST"
```

---

### Task 9: Build wiring, self-containment tests, operator runbook

**Files:**
- Modify: `smw/render/build.py` (`_build_season`), `tests/test_self_containment.py`, `tests/test_build.py` (append), `AGENTS.md` (self-contained-pages bullet), `README.md` (append)

**Interfaces:**
- Consumes: `build_play_data`, `play_context`, `render_play`, `render_join` (Task 5); `play_cfg` local from Task 4.
- Produces: `<out>/<year>/play.html`, `<out>/<year>/join.html` whenever `play.yaml` exists.

- [ ] **Step 1: Write the failing build tests**

Append to `tests/test_build.py`:
```python
def test_play_pages_built_only_with_play_yaml(data_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(build, "fetch_players", lambda url: [])
    out = _run(data_dir, tmp_path).parent
    assert not (out / "play.html").exists() and not (out / "join.html").exists()
    (data_dir / "play.yaml").write_text(PLAY_YAML)
    out = _run(data_dir, tmp_path).parent
    assert (out / "play.html").exists() and (out / "join.html").exists()
    html = (out / "play.html").read_text()
    assert 'href="g/rules.html"' in html                     # season's default group's rules
    assert '"default_group":["alice"]' in html
    assert '"build_date":"2026-08-15"' in html

def test_play_page_state_follows_the_forecast_gate(data_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(build, "fetch_players", lambda url: [])
    (data_dir / "play.yaml").write_text(PLAY_YAML)
    out = _run(data_dir, tmp_path).parent                    # 3 projections < 25 → early
    assert '"state":"early"' in (out / "play.html").read_text()

def test_join_page_locks_after_the_season(data_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(build, "fetch_players", lambda url: [])
    (data_dir / "play.yaml").write_text(PLAY_YAML)
    out = _run(data_dir, tmp_path, today=date(2026, 9, 9)).parent   # window_end + 2 → Final
    html = (out / "join.html").read_text()
    assert "Season's over" in html and 'id="joinForm"' not in html
    assert '"state":"final"' in (out / "play.html").read_text()
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_build.py -k "play_pages or play_page_state or join_page_locks" -v`
Expected: FAIL — `play.html` not written.

- [ ] **Step 3: Wire the renderers into `_build_season`**

In `smw/render/build.py` imports add:
```python
from smw.render.play import build_play_data, play_context, render_join, render_play
```
At the end of `_build_season`, after the `for group in groups:` loop and before `if persist:` (box-office append), add:
```python
    if play_cfg is not None:
        # Play-along pages are season-scoped (play-along spec §4.1, decision 2): one pair per
        # year, next to the group directories. Never scored server-side (§6.5).
        play_data = build_play_data(season, catalog, actual_top, forecastable, reason,
                                    today, play_cfg)
        pctx = play_context(season, today, f"{season.default_group}/rules.html")
        render_play(env, out_dir, pctx, play_data)
        render_join(env, out_dir, pctx, play_data, season_over=final)
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/pytest tests/test_build.py -v`
Expected: PASS.

- [ ] **Step 5: Extend the self-containment suite**

Replace `tests/test_self_containment.py` with:
```python
import json
from datetime import date
import pytest
import smw.render.build as build
from tests.conftest import FIXTURES

PAGES = ("index.html", "whatif.html", "scenarios.html", "history.html", "rules.html")
PLAY_PAGES = ("play.html", "join.html")
API = "https://smw-players.example.workers.dev"
MARKERS = ("http://", "https://", "//cdn", "@import", "url(http")

def _write_data(tmp_path):
    d = tmp_path / "data" / "seasons" / "2026"
    (d / "groups").mkdir(parents=True)
    (d / "season.yaml").write_text(
        "year: 2026\nwindow_start: 2026-05-01\nwindow_end: 2026-09-07\n"
        "seed: 42\nmonte_carlo_trials: 500\nmin_projections_for_forecast: 3\n")
    (d / "groups" / "g.yaml").write_text(
        "group_id: g\ndisplay_name: G\nplayers:\n"
        "  alice:\n"
        "    ranked: [Big Summer Film, Mid June Comedy, Labor Day Opener,"
        " F4, F5, F6, F7, F8, F9, F10]\n"
        "    dark_horses: [D1, D2, Tiny Tail Film]\n")
    (d / "play.yaml").write_text(f"api_base_url: {API}\ndefault_group: [alice]\n")

@pytest.fixture
def built_site(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "fetch",
                        lambda year: (FIXTURES / "synthetic_chart.html").read_text())
    monkeypatch.setattr(build, "fetch_players", lambda url: [])
    _write_data(tmp_path)
    out = tmp_path / "out"
    build.run_build(tmp_path / "data", out, date(2026, 8, 15), local=True)
    return out / "2026" / "g"

def test_no_external_origin_references(built_site):
    for page in PAGES:
        html = (built_site / page).read_text()
        for marker in MARKERS:
            assert marker not in html, f"{page} contains {marker}"

def test_no_page_fetches_data_json(built_site):
    # data.json is published for humans and tools; no friends page fetches anything (§13.1).
    for page in PAGES:
        html = (built_site / page).read_text()
        assert "fetch(" not in html
        assert "XMLHttpRequest" not in html

def test_friends_pages_do_not_link_to_play_along(built_site):
    # Play-along spec §4.1: separate audience, fixed friends nav.
    for page in PAGES:
        html = (built_site / page).read_text()
        assert 'href="play.html"' not in html and 'href="join.html"' not in html
        assert "../play.html" not in html and "../join.html" not in html

def test_play_pages_reference_exactly_the_api_origin(built_site):
    # Play-along spec §5.1 departure: one fetch each to the configured origin, nothing else.
    for page in PLAY_PAGES:
        html = (built_site.parent / page).read_text()
        assert API in html, page
        stripped = html.replace(API, "")
        for marker in MARKERS:
            assert marker not in stripped, f"{page} contains {marker} beyond the API origin"
        assert html.count("fetch(") == 1, page
        assert "XMLHttpRequest" not in html

def test_play_pages_fail_on_any_other_origin(tmp_path, monkeypatch):
    # The allowance is for the configured origin only; a build against a different
    # origin must not smuggle the old one through a template or script.
    monkeypatch.setattr(build, "fetch",
                        lambda year: (FIXTURES / "synthetic_chart.html").read_text())
    monkeypatch.setattr(build, "fetch_players", lambda url: [])
    _write_data(tmp_path)
    other = "https://other.example"
    (tmp_path / "data" / "seasons" / "2026" / "play.yaml").write_text(
        f"api_base_url: {other}\n")
    out = tmp_path / "out"
    build.run_build(tmp_path / "data", out, date(2026, 8, 15), local=True)
    for page in PLAY_PAGES:
        html = (out / "2026" / page).read_text()
        assert API not in html
        assert "https://" not in html.replace(other, "")

def test_reproducible_build(built_site, tmp_path, monkeypatch):
    # Byte-identical output for identical inputs (§1.3): rebuild into a second
    # directory from the same inputs and diff every page, play pages included.
    monkeypatch.setattr(build, "fetch",
                        lambda year: (FIXTURES / "synthetic_chart.html").read_text())
    monkeypatch.setattr(build, "fetch_players", lambda url: [])
    out2 = tmp_path / "out2"
    build.run_build(tmp_path / "data", out2, date(2026, 8, 15), local=True)
    for page in PAGES + ("data.json",):
        assert (built_site / page).read_bytes() == (out2 / "2026" / "g" / page).read_bytes(), page
    for page in PLAY_PAGES:
        assert (built_site.parent / page).read_bytes() == (out2 / "2026" / page).read_bytes(), page
    assert (built_site.parent.parent / "index.html").read_bytes() == \
        (out2 / "index.html").read_bytes()
```

Run: `.venv/bin/pytest tests/test_self_containment.py -v`
Expected: PASS. If `test_friends_pages_do_not_link_to_play_along` fails, a template leaked a link — remove it; friends pages MAY only link in the footer, and this plan chooses not to (§4.1 "optionally").

- [ ] **Step 6: Update AGENTS.md self-containment bullet**

Change the `- Self-contained pages:` bullet in `AGENTS.md` to:
```
- Self-contained pages: zero network requests from published friends-group pages — all CSS/JS inlined, no remote fonts (system font stack), no runtime fetch, no external links in output. Exception (play-along spec §5.1): `play.html` and `join.html` make exactly one `fetch()` each to the `api_base_url` configured in `play.yaml` and reference no other origin.
```

- [ ] **Step 7: Operator runbook in README.md**

Append to `README.md`:
```markdown
## Play-along (public signups)

The play-along backend is a Cloudflare Worker + D1 database in `worker/`; the pipeline only
reads it. One-time setup:

1. `cd worker && npm ci`
2. `npx wrangler login`
3. `npx wrangler d1 create smw-players` → paste the printed `database_id` into `wrangler.toml`.
4. `npx wrangler d1 execute smw-players --remote --file=schema.sql`
5. `npm run deploy` → note the `*.workers.dev` URL.
6. Create `data/seasons/<year>/play.yaml`:
   ```yaml
   api_base_url: https://smw-players.<account>.workers.dev
   default_group: []        # usernames to show on the bare play.html; edit + rebuild any time
   ```
7. Rebuild. `out/<year>/play.html` and `out/<year>/join.html` now exist.

Each new season: bump `SEASON_YEAR` in `wrangler.toml`, `npm run deploy`, add that season's
`play.yaml`. Old rows stay as history; usernames are free again.

Moderation is `npx wrangler d1 execute smw-players --remote --command "DELETE FROM players WHERE username='x' AND year=2026"`.
If the players API is down at build time the build warns and continues; the friends site never
depends on it. Tests: `.venv/bin/pytest` (pipeline + client JS via node) and `cd worker && npm test`.
```

- [ ] **Step 8: Run every check**

Run: `.venv/bin/pytest && (cd worker && npm test)`
Expected: both PASS.

- [ ] **Step 9: Commit**

```bash
git add smw/render/build.py tests/test_build.py tests/test_self_containment.py AGENTS.md README.md
git commit -m "feat(build): render play-along pages per season; self-containment allows only the API origin"
```

- [ ] **Step 10: Cross-review**

Working tree clean (`git status --porcelain` empty), then run `/cross-review superpowers/specs/2026-08-15-play-along-design.md` per CONTRIBUTING.md. Fix blocking findings, checkpoint-commit, repeat.

---

## Self-review (done while writing)

**Spec coverage:** §2 rules → reuse of `scoring.js` (T6) and `rules.py` untouched. §2.2 `joined_at` displayed → T7 detail + Joined column. §3.1–3.5 → T1/T2 (composite PK per Decision 1). §4.1 pages/nav → T7 base template, self-containment nav test (T9). §4.2–4.3 composition and states → T6 pure functions + tests, T7 DOM. §5.1 departure + footer line → T7 template, T9 tests, AGENTS.md. §5.2 form → T8 (datalist, inline rule, distinctness before POST, 201/409/400/network states, season-over notice). §5.3 columns, detail, client scoring, Early behaviour, page states → T5/T6/T7. §5.4 textContent-only → T6 static test + all DOM code. §6.1 `play.yaml` → T3. §6.2 candidate list = catalog sorted by release date → T5. §6.3 optional fetch, warn-and-continue → T4. §6.4 embed contents → T5. §6.5 friends path untouched → T9 tests. §7 Worker suite → T1/T2; client scoring vector → existing `test_cross_impl` (shared module); rendered-page tests, Early-state, hostile strings → T7/T8/T9; view composition → T6.

**Not built, deliberately:** friends-page footer link to play-along (§4.1 "optionally") — add one `<a>` in `base.html.j2`'s footer and relax `test_friends_pages_do_not_link_to_play_along` if wanted. Turnstile, rate limiting, editing — out of scope per §1.4.

**Type consistency:** `PlayConfig(api_base_url, default_group: tuple)` used identically in T3/T4/T5/T9; `build_play_data(season, catalog, actual_top, forecastable, reason, today, cfg)` identical in T5/T7/T8/T9; `fetch_players(url) -> list[dict]` seam name identical in T4/T9 tests; JS `composeView/standings/pickRows/columns` signatures identical in T6 tests, T6 code, T7 `main`; `validateSubmission(username, ranked, dark, titles)` identical in T8 tests and code; ids in T7/T8 templates match the `$()` lookups in the scripts.
