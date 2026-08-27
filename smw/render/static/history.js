"use strict";
(function () {
  var D = window.HISTORY;
  var svg = document.querySelector(".chartbox svg");
  var tip = document.getElementById("tipbox");
  if (!svg || !tip) return;
  var W = 920, L = 52, R = 110, iw = W - L - R;
  var n = D.dates.length;
  var xh = svg.querySelector(".xh");
  function x(i) { return n > 1 ? L + iw * i / (n - 1) : L + iw / 2; }
  svg.addEventListener("mousemove", function (ev) {
    var r = svg.getBoundingClientRect(), sx = W / r.width;
    var i = n > 1 ? Math.round(((ev.clientX - r.left) * sx - L) / (iw / (n - 1))) : 0;
    i = Math.max(0, Math.min(n - 1, i));
    xh.setAttribute("x1", x(i)); xh.setAttribute("x2", x(i));
    xh.style.display = "";
    tip.textContent = "";
    var b = document.createElement("strong");
    b.textContent = D.dates[i];
    tip.appendChild(b);
    D.series.forEach(function (s) {
      tip.appendChild(document.createElement("br"));
      var sw = document.createElement("span");
      sw.className = "dlsw series-" + s.color;
      sw.style.background = "var(--series)";
      tip.appendChild(sw);
      var v = s.values[i];
      tip.appendChild(document.createTextNode(
        s.name + ": " + (v === null ? "·" : (Math.round(v * 1000) / 10).toFixed(1) + "%")));
    });
    tip.style.display = "block";
    tip.style.left = (ev.clientX + 14) + "px";
    tip.style.top = (ev.clientY + 10) + "px";
  });
  svg.addEventListener("mouseleave", function () {
    tip.style.display = "none";
    xh.style.display = "none";
  });
})();
