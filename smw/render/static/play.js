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

function main() {
  var D = window.PLAY;
  function $(id) { return document.getElementById(id); }
  function show(id) { $(id).hidden = false; }
  function cell(tr, text, cls, tag) {
    var el = document.createElement(tag || "td");
    if (cls) el.className = cls;
    el.textContent = text;                                   // §5.4: never innerHTML
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
    var cols = ["#", "Movie"];
    if (D.state !== "early") cols.push("Projected rank");   // §5.3: absent, not dashed
    cols.push("Current pts");
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
      if (D.state !== "early")                                         // "not tracked" is base §10.2
        cell(tr, r.missing ? "not tracked" : (r.projected_rank ? "#" + r.projected_rank : "—"),
             r.missing || !r.projected_rank ? "dash" : "");
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
    var anyone = view.players.length || view.unknown.length;
    // The explainer is the bare page's invitation, and the fallback when there is
    // nobody to tabulate (empty default group, or ?follow= with no names).
    if (view.state === "bare" || !anyone) show("playExplainer");
    if (anyone) renderBoard(view);
    if (view.state === "user") renderDetail(view.players[0]);   // composeView puts the user first
  }

  function failed() { $("playLoading").hidden = true; show("playError"); }

  // Two-arg then, not .catch: a bug inside render must not be reported as a
  // failed fetch (§5.3 — an empty roster and a dead API are different facts).
  fetch(D.api_base_url + "/api/players", { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (body) {
      if (!Array.isArray(body.players)) throw new Error("malformed roster payload");
      return body.players;                                   // rejects into `failed` below
    })
    .then(function (players) { render(composeView(params, players, D.default_group)); },
          failed);
}

if (typeof module !== "undefined") {
  module.exports = { parseParams: parseParams, composeView: composeView, columns: columns,
                     standings: standings, pickRows: pickRows };
}
if (typeof window !== "undefined" && window.PLAY) main();
