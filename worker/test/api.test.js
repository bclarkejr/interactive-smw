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
