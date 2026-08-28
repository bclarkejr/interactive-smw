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
