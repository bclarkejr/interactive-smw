import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "module";
import { readFileSync } from "fs";
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

test("distinctness survives Object.prototype-named titles", () => {
  const ten = ["constructor", "toString", "__proto__", "valueOf", "hasOwnProperty"]
    .concat(TEN.slice(0, 5));
  const titles = new Set(ten.concat(["DH1", "DH2", "DH3"]));
  const r = J.validateSubmission("abc", ten, ["DH1", "DH2", "DH3"], titles);
  assert.equal(r.ok, true, r.error);
  const dup = J.validateSubmission("abc", ten, ["constructor", "DH2", "DH3"], titles);
  assert.equal(dup.ok, false);
  assert.match(dup.error, /twice/);
});

test("a titles array works as well as a Set", () => {
  const r = J.validateSubmission("abc", TEN, ["DH1", "DH2", "DH3"], Array.from(TITLES));
  assert.equal(r.ok, true, r.error);
});

// ---------- main(): the DOM half ----------
// No jsdom in this project, so main() runs against a stub with just the surface
// join.js touches, run through `new Function` (the browser path, where
// `typeof module === "undefined"`).
const SRC = readFileSync(join(here, "..", "smw", "render", "static", "join.js"), "utf8");
const IDS = ["joinError", "joinDone", "joinName", "joinLink", "joinCopy"];

function el(tag) {
  return { tag, hidden: false, value: "", href: "", disabled: false, focused: false,
           handlers: {}, _text: "",
           get textContent() { return this._text; },
           set textContent(v) { this._text = String(v); },
           focus() { this.focused = true; },
           addEventListener(type, fn) { (this.handlers[type] = this.handlers[type] || []).push(fn); },
           fire(type, ev) { (this.handlers[type] || []).forEach((fn) => fn(ev || {})); } };
}

// Builds the join page stub and runs join.js. `opts.respond` is the fetch reply.
function page(opts) {
  opts = opts || {};
  const ids = {};
  IDS.forEach((id) => { ids[id] = el("div"); });
  ids.joinError.hidden = true;
  ids.joinDone.hidden = true;
  ids.username = el("input");
  ids.username.value = opts.username === undefined ? "popcorn-goblin" : opts.username;
  const inputs = { ranked: (opts.ranked || TEN).map((v) => { const i = el("input"); i.value = v; return i; }),
                   dark: (opts.dark || ["DH1", "DH2", "DH3"]).map((v) => { const i = el("input"); i.value = v; return i; }) };
  const btn = el("button");
  const form = el("form");
  form.querySelectorAll = (sel) => inputs[sel.slice('input[name="'.length, -2)];
  form.querySelector = () => btn;
  ids.joinForm = opts.seasonOver ? null : form;

  global.document = { getElementById: (id) => ids[id] || null };
  global.window = {
    location: { href: "https://smw.test/2026/play/join.html" },
    PLAY: { api_base_url: "https://api.test",
            catalog: Array.from(TITLES).map((t) => ({ title: t, release_label: "May 1" })) },
  };
  const calls = [];
  global.fetch = (u, o) => {
    calls.push([u, o]);
    if (opts.offline) return Promise.reject(new TypeError("failed to fetch"));
    return Promise.resolve(opts.respond || { status: 201, json: () => Promise.resolve({ username: "popcorn-goblin" }) });
  };
  new Function(SRC)();                       // join.js self-starts on window.PLAY
  return { ids, btn, calls, form,
           submit() {
             let prevented = false;
             form.fire("submit", { preventDefault() { prevented = true; } });
             assert.equal(prevented, true, "submit must be prevented");
             return new Promise((r) => setImmediate(r));
           } };
}

test("main: a valid submission POSTs the §3.3 body once", async () => {
  const p = page();
  await p.submit();
  assert.equal(p.calls.length, 1);
  assert.equal(p.calls[0][0], "https://api.test/api/players");
  assert.equal(p.calls[0][1].method, "POST");
  assert.deepEqual(JSON.parse(p.calls[0][1].body),
                   { username: "popcorn-goblin", ranked: TEN, dark_horses: ["DH1", "DH2", "DH3"] });
});

test("main: 201 hides the form and shows the play link", async () => {
  const p = page();
  await p.submit();
  assert.equal(p.form.hidden, true);
  assert.equal(p.ids.joinDone.hidden, false);
  assert.equal(p.ids.joinName.textContent, "popcorn-goblin");
  assert.equal(p.ids.joinLink.textContent, "https://smw.test/2026/play/play.html?user=popcorn-goblin");
  assert.equal(p.ids.joinLink.href, p.ids.joinLink.textContent);
  assert.equal(p.ids.joinError.hidden, true);
  p.ids.joinCopy.fire("click");            // no clipboard in Node: must not throw
});

test("main: 409 says the name is taken, keeps the form and the picks", async () => {
  const p = page({ respond: { status: 409, json: () => Promise.resolve({ error: "username taken" }) } });
  await p.submit();
  assert.equal(p.ids.joinError.hidden, false);
  assert.match(p.ids.joinError.textContent, /taken/);
  assert.equal(p.ids.joinDone.hidden, true);
  assert.equal(p.form.hidden, false);
  assert.equal(p.ids.username.focused, true);
  assert.equal(p.btn.disabled, false);      // re-armed for another try
});

test("main: 400 surfaces the API's reason without clearing anything", async () => {
  const p = page({ respond: { status: 400, json: () => Promise.resolve({ error: "ranked must have 10 titles" }) } });
  await p.submit();
  assert.equal(p.ids.joinError.hidden, false);
  assert.match(p.ids.joinError.textContent, /400/);
  assert.match(p.ids.joinError.textContent, /ranked must have 10 titles/);
  assert.match(p.ids.joinError.textContent, /Nothing was cleared/);
  assert.equal(p.form.hidden, false);
  assert.equal(p.btn.disabled, false);
});

test("main: an unparseable error body still reports the status", async () => {
  const p = page({ respond: { status: 500, json: () => Promise.reject(new SyntaxError("nope")) } });
  await p.submit();
  assert.match(p.ids.joinError.textContent, /500/);
  assert.equal(p.ids.joinDone.hidden, true);
});

test("main: a dead API says so and keeps the picks", async () => {
  const p = page({ offline: true });
  await p.submit();
  assert.equal(p.ids.joinError.hidden, false);
  assert.match(p.ids.joinError.textContent, /connection/);
  assert.match(p.ids.joinError.textContent, /still here/);
  assert.equal(p.form.hidden, false);
  assert.equal(p.btn.disabled, false);
});

test("main: invalid picks never reach the network", async () => {
  const dupe = page({ dark: [TEN[0], "DH2", "DH3"] });
  await dupe.submit();
  assert.deepEqual(dupe.calls, []);
  assert.match(dupe.ids.joinError.textContent, /twice/);
  assert.equal(dupe.btn.disabled, false);

  const bad = page({ username: "-nope-" });
  await bad.submit();
  assert.deepEqual(bad.calls, []);
  assert.match(bad.ids.joinError.textContent, /3–24/);
});

test("main: a stale error is cleared when the next submission succeeds", async () => {
  const p = page({ username: "ab" });
  await p.submit();
  assert.equal(p.ids.joinError.hidden, false);
  p.ids.username.value = "popcorn-goblin";
  await p.submit();
  assert.equal(p.ids.joinError.hidden, true);
  assert.equal(p.ids.joinDone.hidden, false);
});

test("main: season over (no form) is inert — no listeners, no fetch", async () => {
  const p = page({ seasonOver: true });
  assert.deepEqual(p.calls, []);
  assert.deepEqual(p.form.handlers, {});
});
