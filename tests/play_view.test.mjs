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

test("play.js never builds HTML from strings", () => {
  const src = readFileSync(join(STATIC, "play.js"), "utf8");
  for (const banned of ["insertAdjacentHTML", "outerHTML", "document.write"])
    assert.ok(!src.includes(banned), `play.js uses ${banned}`);
  for (const m of src.matchAll(/innerHTML\s*=\s*([^;]+);/g))
    assert.equal(m[1].trim(), '""', `play.js: innerHTML assigned ${m[1]}`);
});
