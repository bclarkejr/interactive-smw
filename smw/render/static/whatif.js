"use strict";
(function () {
  var D = window.WHATIF;
  var list = document.getElementById("wiList");

  function order() {
    return Array.prototype.map.call(list.children, function (li) { return li.dataset.title; });
  }
  function cell(tr, text, cls) {
    var td = document.createElement("td");
    if (cls) td.className = cls;
    td.textContent = text;
    tr.appendChild(td);
  }
  function th(tr, text, cls) {
    var el = document.createElement("th");
    if (cls) el.className = cls;
    el.textContent = text;
    tr.appendChild(el);
  }
  function item(title) {
    var li = document.createElement("li");
    li.dataset.title = title;
    var film = document.createElement("span");
    film.className = "film";
    film.textContent = title;
    li.appendChild(film);
    var mv = document.createElement("span");
    mv.className = "mv";
    [["▲", -1], ["▼", 1]].forEach(function (pair) {
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = pair[0];
      b.setAttribute("aria-label",
        "Move " + title + (pair[1] < 0 ? " up" : " down") + " one slot");
      b.addEventListener("click", function () {
        var sib = pair[1] < 0 ? li.previousElementSibling : li.nextElementSibling;
        if (!sib) return;
        list.insertBefore(li, pair[1] < 0 ? sib : sib.nextElementSibling);
        rescore();
        // keep focus on the film: this arrow if still enabled, else its sibling
        (b.disabled ? (pair[1] < 0 ? mv.lastElementChild : mv.firstElementChild) : b).focus();
      });
      mv.appendChild(b);
    });
    li.appendChild(mv);
    return li;
  }
  function fill() {
    list.innerHTML = "";
    D.films.forEach(function (t) { list.appendChild(item(t)); });
    rescore();
  }

  function rescore() {
    var ord = order(), finish = ord.slice(0, 10);
    Array.prototype.forEach.call(list.children, function (li, i) {
      var bs = li.querySelectorAll("button");
      bs[0].disabled = i === 0;
      bs[1].disabled = i === ord.length - 1;
    });
    var rows = D.players.map(function (p) {
      return { name: p.name, pts: scorePlayer(p.ranked, p.dark, finish),
               base: D.baseline[p.name], picks: p };
    });
    rows.sort(function (a, b) { return b.pts - a.pts || (a.name < b.name ? -1 : 1); });

    var tbody = document.querySelector("#wiStandings tbody");
    tbody.innerHTML = "";
    var place = 0, prev = null;
    rows.forEach(function (r, i) {
      if (r.pts !== prev) { place = i + 1; prev = r.pts; }  // competition ranking 1,1,3
      var tr = document.createElement("tr");
      var d = r.pts - r.base;
      cell(tr, place);
      cell(tr, r.name, place === 1 ? "t crown" : "t");
      cell(tr, r.pts, "pos");
      cell(tr, d === 0 ? "–" : d > 0 ? "▲" + d : "▼" + (-d),
           d === 0 ? "dash" : d > 0 ? "up" : "down");
      tbody.appendChild(tr);
    });

    var head = document.querySelector("#wiGrid thead tr");
    head.innerHTML = "";
    th(head, "#"); th(head, "Movie", "t");
    rows.forEach(function (r) { th(head, r.name); });
    var grid = document.querySelector("#wiGrid tbody");
    grid.innerHTML = "";
    ord.forEach(function (title, i) {
      var tr = document.createElement("tr");
      cell(tr, i + 1); cell(tr, title, "t");
      rows.forEach(function (r) {
        var pts = pointsFor(r.picks.ranked, r.picks.dark, title, finish);
        cell(tr, pts === null ? "—" : pts, pts === null ? "dash" : pts > 0 ? "pos" : "zero");
      });
      grid.appendChild(tr);
      if (i === 9) {
        var div = document.createElement("tr");
        div.className = "divider";
        var td = document.createElement("td");
        td.colSpan = 2 + rows.length;
        td.textContent = "Outside the top 10";
        div.appendChild(td);
        grid.appendChild(div);
      }
    });
  }

  document.getElementById("wiReset").addEventListener("click", fill);
  fill();
  new Sortable(list, {
    animation: 150,                       // rows slide out of the way during the drag
    ghostClass: "dragging",               // the mockup's class: 40% opacity
    delay: 150, delayOnTouchOnly: true,   // press-and-hold on touch so the page still scrolls
    touchStartThreshold: 4,
    filter: ".mv button", preventOnFilter: false,   // ▲ ▼ still click
    onEnd: rescore                        // Sortable moved the <li>; just read the DOM order
  });
})();
