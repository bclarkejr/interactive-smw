"use strict";
(function () {
  var D = window.WHATIF;
  var list = document.getElementById("film-list");
  var order = D.films.slice();

  function top10() { return order.slice(0, 10); }

  function rebuild() {
    list.innerHTML = "";
    order.forEach(function (title, idx) {
      var li = document.createElement("li");
      li.draggable = true;
      li.dataset.title = title;
      var name = document.createElement("span");
      name.className = "wi-title";
      name.textContent = title;
      li.appendChild(name);
      [["▲", -1], ["▼", 1]].forEach(function (pair) {
        var b = document.createElement("button");
        b.type = "button";
        b.textContent = pair[0];
        b.setAttribute("aria-label",
          "Move " + title + (pair[1] < 0 ? " up" : " down") + " one slot");
        b.addEventListener("click", function () {
          var j = order.indexOf(title), k = j + pair[1];
          if (k < 0 || k >= order.length) return;
          order.splice(j, 1); order.splice(k, 0, title);
          rebuild(); rescore();
          // return focus so repeated presses keep walking the film (§12.2)
          var again = list.children[k].querySelectorAll("button")[pair[1] < 0 ? 0 : 1];
          again.focus();
        });
        li.appendChild(b);
      });
      li.addEventListener("dragstart", function (e) {
        e.dataTransfer.setData("text/plain", title);
        li.classList.add("dragging");
      });
      li.addEventListener("dragend", function () { li.classList.remove("dragging"); });
      li.addEventListener("dragover", function (e) { e.preventDefault(); });
      li.addEventListener("drop", function (e) {
        e.preventDefault();
        var dragged = e.dataTransfer.getData("text/plain");
        if (!dragged || dragged === title) return;
        var from = order.indexOf(dragged), to = order.indexOf(title);
        order.splice(from, 1); order.splice(to, 0, dragged);
        rebuild(); rescore();
      });
      // touch: press-and-hold before a drag begins so page scrolling still works
      var holdTimer = null, touchDragging = false;
      li.addEventListener("touchstart", function () {
        holdTimer = setTimeout(function () { touchDragging = true;
          li.classList.add("dragging"); }, 350);
      }, { passive: true });
      li.addEventListener("touchmove", function (e) {
        if (!touchDragging) { clearTimeout(holdTimer); return; }
        e.preventDefault();
        var y = e.touches[0].clientY;
        var target = document.elementFromPoint(e.touches[0].clientX, y);
        var over = target && target.closest("#film-list li");
        if (over && over !== li) {
          var from = order.indexOf(title), to = order.indexOf(over.dataset.title);
          order.splice(from, 1); order.splice(to, 0, title);
          rebuild(); rescore();
        }
      }, { passive: false });
      li.addEventListener("touchend", function () {
        clearTimeout(holdTimer); touchDragging = false;
        li.classList.remove("dragging");
      });
      list.appendChild(li);
    });
  }

  function rescore() {
    var finish = top10();
    var rowsData = D.players.map(function (p) {
      return { name: p.name, pts: scorePlayer(p.ranked, p.dark, finish),
               base: D.baseline[p.name] };
    });
    rowsData.sort(function (a, b) { return b.pts - a.pts || (a.name < b.name ? -1 : 1); });
    var tbody = document.getElementById("standings-body");
    tbody.innerHTML = "";
    var place = 0, shown = 0, prev = null;
    rowsData.forEach(function (r) {
      shown += 1;
      if (r.pts !== prev) { place = shown; prev = r.pts; }  // competition ranking 1,1,3
      var tr = document.createElement("tr");
      var delta = r.pts - r.base;
      var deltaTxt = delta > 0 ? "▲" + delta : delta < 0 ? "▼" + (-delta) : "–";
      [place, (place === 1 ? "👑 " : "") + r.name, r.pts, deltaTxt].forEach(function (v) {
        var td = document.createElement("td");
        td.textContent = v;
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    var grid = document.getElementById("points-grid-body");
    grid.innerHTML = "";
    order.forEach(function (title, i) {
      var tr = document.createElement("tr");
      var td0 = document.createElement("td"); td0.textContent = (i + 1) + ". " + title;
      tr.appendChild(td0);
      rowsData.forEach(function (r) {
        var p = D.players.filter(function (x) { return x.name === r.name; })[0];
        var pts = pointsFor(p.ranked, p.dark, title, finish);
        var td = document.createElement("td");
        td.className = "num " + (pts === null ? "cell-none" : pts > 0 ? "cell-pos" : "cell-zero");
        td.textContent = pts === null ? "—" : String(pts);
        tr.appendChild(td);
      });
      grid.appendChild(tr);
    });
    var head = document.getElementById("points-grid-head");
    head.innerHTML = "<th>Film</th>" + rowsData.map(function (r) {
      return "<th class=\"num\"></th>"; }).join("");
    var ths = head.querySelectorAll("th.num");
    rowsData.forEach(function (r, i) { ths[i].textContent = r.name; });
  }

  document.getElementById("reset-order").addEventListener("click", function () {
    order = D.films.slice();
    rebuild(); rescore();
  });
  rebuild(); rescore();
})();
