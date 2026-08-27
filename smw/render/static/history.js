"use strict";
(function () {
  var D = window.HISTORY;
  var svg = document.querySelector(".odds-chart");
  var tip = document.getElementById("crosshair-tip");
  if (!svg || !tip) return;
  var ML = 48, MR = 118;
  svg.addEventListener("mousemove", function (e) {
    var rect = svg.getBoundingClientRect();
    var frac = (e.clientX - rect.left) / rect.width;   // viewBox is 0..660
    var px = frac * 660;
    var n = D.dates.length;
    var span = 660 - ML - MR;
    var i = Math.round((px - ML) / (n > 1 ? span / (n - 1) : span));
    i = Math.max(0, Math.min(n - 1, i));
    var lines = [D.dates[i]];
    D.series.forEach(function (s) {
      var v = s.values[i];
      lines.push(s.name + ": " + (v === null ? "·" : Math.round(v * 1000) / 10 + "%"));
    });
    tip.hidden = false;
    tip.textContent = lines.join("  ");
  });
  svg.addEventListener("mouseleave", function () { tip.hidden = true; });
})();
