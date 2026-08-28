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
  var all = r.concat(d), seen = Object.create(null);   // null proto: a film named "constructor" is not a dupe
  for (var i = 0; i < all.length; i++) {
    var t = all[i];
    if (!t) return { ok: false, error: "Choose a film for " + labels[i] + "." };
    if (!has(t)) return { ok: false, error: "“" + t + "” (" + labels[i] + ") isn't on the list — pick a film from the list." };
    if (seen[t] !== undefined)
      return { ok: false, error: "“" + t + "” is picked twice (" + labels[seen[t]] + " and " + labels[i] + ") — all 13 must be distinct." };
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
        if (r.status === 201) return done(body.username || v.body.username);
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
