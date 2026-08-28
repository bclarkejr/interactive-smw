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
  var seen = Object.create(null), out = [], unknown = [];
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
