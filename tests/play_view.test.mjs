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

test("dedup survives Object.prototype-named users (constructor, toString)", () => {
  const ctor = player("constructor");
  const v1 = P.composeView({ user: "constructor", follow: null }, [ctor], []);
  assert.equal(v1.state, "user");
  assert.deepEqual(v1.players.map((p) => p.username), ["constructor"]);

  const ts = player("toString");
  const v2 = P.composeView({ user: null, follow: ["toString"] }, [ts], []);
  assert.equal(v2.state, "spectator");
  assert.deepEqual(v2.players.map((p) => p.username), ["toString"]);
  assert.deepEqual(v2.unknown, []);
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

test("the play-along scripts never build HTML from strings", () => {
  for (const file of ["play.js", "join.js"]) {
    const src = readFileSync(join(STATIC, file), "utf8");
    for (const banned of ["insertAdjacentHTML", "outerHTML", "document.write"])
      assert.ok(!src.includes(banned), `${file} uses ${banned}`);
    for (const m of src.matchAll(/innerHTML\s*=\s*([^;]+);/g))
      assert.equal(m[1].trim(), '""', `${file}: innerHTML assigned ${m[1]}`);
  }
});

// ---------- main(): the DOM half ----------
// No jsdom in this project, so main() runs against a stub with just the surface
// play.js touches. scoring.js + play.js are concatenated and run through
// `new Function`, where `typeof module === "undefined"`, i.e. the browser path.
const SRC = readFileSync(join(STATIC, "scoring.js"), "utf8")
          + readFileSync(join(STATIC, "play.js"), "utf8");
const SECTIONS = ["playLoading", "playError", "playNotFound", "playMissingName", "playExplainer",
                  "playBoard", "playHeading", "playUnknown", "playTable", "playDetail",
                  "playDetailHeading", "playJoined", "playPicks"];

function el(tag) {
  return { tag, children: [], className: "", hidden: false, _text: "",
           get textContent() { return this._text; },
           set textContent(v) { this._text = String(v); },   // the real DOM stringifies
           appendChild(c) { this.children.push(c); return c; } };
}

// Runs main() once against a fresh stub page; resolves with { ids, head, body, calls }.
function run(search, players, opts) {
  opts = opts || {};
  const ids = {}, tbl = {};
  SECTIONS.forEach((id) => { ids[id] = el("section"); ids[id].hidden = id !== "playLoading"; });
  ["#playTable", "#playPicks"].forEach((t) => { tbl[t] = { head: el("tr"), body: el("tbody") }; });
  global.document = {
    createElement: el,
    getElementById: (id) => ids[id],
    querySelector: (sel) => {
      const [table, part] = sel.split(" thead tr");
      return part === "" ? tbl[table].head : tbl[sel.split(" ")[0]].body;
    },
  };
  global.window = {
    location: { search },
    PLAY: { state: opts.state || "live", api_base_url: "https://x.test",
            default_group: opts.defaultGroup || ["alice", "bob"],
            catalog: TEN.concat(["M15", "M16", "M17"]).map((t, i) => ({ title: t, projected_rank: i + 1 })),
            actual_top: TEN, projected_top: TEN },
  };
  const calls = [];
  global.fetch = (u, o) => {
    calls.push([u, o]);
    if (opts.reject) return Promise.reject(new Error("offline"));
    if (opts.notOk) return Promise.resolve({ ok: false, status: 503 });
    return Promise.resolve({ ok: true, json: () => Promise.resolve(opts.body || { players }) });
  };
  new Function(SRC)();                                    // play.js self-starts on window.PLAY
  const cells = (row) => row.children.map((c) => c.textContent);
  return new Promise((r) => setImmediate(() => r({
    ids, calls, cells,
    head: (t) => tbl[t].head.children.map((c) => c.textContent),
    rows: (t) => tbl[t].body.children,
  })));
}

const TEN_PLAYER = player("alice");
const BOB = player("bob", TEN.slice().reverse(), ["M15", "M18", "M14"], "2026-08-01T00:00:00Z");

test("main: live user view fetches the roster and fills both tables", async () => {
  const p = await run("?user=alice", [TEN_PLAYER, BOB]);
  assert.deepEqual(p.calls, [["https://x.test/api/players", { cache: "no-store" }]]);
  assert.equal(p.ids.playLoading.hidden, true);
  assert.equal(p.ids.playError.hidden, true);
  assert.equal(p.ids.playBoard.hidden, false);
  assert.equal(p.ids.playDetail.hidden, false);
  assert.deepEqual(p.head("#playTable"), ["Place", "Player", "Joined", "Current pts", "Projected pts"]);
  assert.deepEqual(p.rows("#playTable").map(p.cells),
                   [["1", "alice", "2026-08-15", "106", "106"],
                    ["2", "bob", "2026-08-01", "38", "38"]]);
  assert.equal(p.rows("#playTable")[0].className, "me");          // the user's own row
  assert.equal(p.rows("#playTable")[0].children[1].className, "t crown");
  assert.equal(p.rows("#playTable")[1].className, "");
  assert.equal(p.ids.playDetailHeading.textContent, "\u{1F464} alice's picks");
  assert.equal(p.ids.playJoined.textContent, "Joined 2026-08-15 (UTC)");
});

test("main: detail table has 13 picks and a spanning dark-horse divider", async () => {
  const p = await run("?user=alice", [TEN_PLAYER]);
  const rows = p.rows("#playPicks");
  assert.equal(rows.length, 14);                                  // 13 picks + 1 divider
  assert.equal(rows[10].className, "divider");
  assert.equal(rows[10].children[0].colSpan, 5);                  // spans the live column count
  assert.equal(rows[10].children[0].textContent, "Dark horses");
  assert.deepEqual(p.cells(rows[0]), ["1", "M01", "#1", "13", "13"]);
  assert.deepEqual(p.cells(rows[11]), ["\u{1F434}", "M15", "#11", "0", "0"]);
});

test("main: the early state has no Projected column in either table", async () => {
  const p = await run("?user=alice", [TEN_PLAYER], { state: "early" });
  assert.deepEqual(p.head("#playTable"), ["Place", "Player", "Joined", "Current pts"]);
  assert.deepEqual(p.head("#playPicks"), ["#", "Movie", "Current pts"]);
  p.rows("#playTable").forEach((r) => assert.equal(r.children.length, 4));
  p.rows("#playPicks").forEach((r) => assert.equal(r.children.length, r.className === "divider" ? 1 : 3));
  assert.equal(p.rows("#playPicks")[10].children[0].colSpan, 3);
  assert.deepEqual(p.cells(p.rows("#playPicks")[0]), ["1", "M01", "13"]);
});

test("main: unknown user shows not-found, never an empty board", async () => {
  const p = await run("?user=ghost", [TEN_PLAYER]);
  assert.equal(p.ids.playNotFound.hidden, false);
  assert.equal(p.ids.playMissingName.textContent, "ghost");
  assert.equal(p.ids.playBoard.hidden, true);
  assert.equal(p.ids.playDetail.hidden, true);
});

test("main: unknown follow names are listed above the board", async () => {
  const p = await run("?follow=alice,ghost,zed", [TEN_PLAYER]);
  assert.equal(p.ids.playUnknown.hidden, false);
  assert.equal(p.ids.playUnknown.textContent, "Unknown players skipped: ghost, zed");
  assert.equal(p.ids.playBoard.hidden, false);
});

test("main: bare URL shows the explainer alongside the default-group board", async () => {
  const p = await run("", [TEN_PLAYER, BOB]);
  assert.equal(p.ids.playExplainer.hidden, false);
  assert.equal(p.ids.playBoard.hidden, false);
  assert.equal(p.rows("#playTable")[0].className, "");            // nobody highlighted
});

test("main: nobody to tabulate falls back to the explainer, not a blank page", async () => {
  const p = await run("?follow=", [TEN_PLAYER], { defaultGroup: [] });
  assert.equal(p.ids.playExplainer.hidden, false);
  assert.equal(p.ids.playBoard.hidden, true);
  assert.equal(p.ids.playLoading.hidden, true);
});

test("main: a dead API shows the error state, not an empty board", async () => {
  for (const opts of [{ reject: true }, { notOk: true }, { body: { oops: 1 } }]) {
    const p = await run("", [TEN_PLAYER], opts);
    assert.equal(p.ids.playError.hidden, false, JSON.stringify(opts));
    assert.equal(p.ids.playLoading.hidden, true, JSON.stringify(opts));
    assert.equal(p.ids.playBoard.hidden, true, JSON.stringify(opts));
    assert.equal(p.ids.playExplainer.hidden, true, JSON.stringify(opts));
  }
});
