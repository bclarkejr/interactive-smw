// -- resolver: runs in <head>, before any body content paints (§13.2 [Changed])
(function () {
  var t = null;
  try { t = localStorage.getItem("theme"); } catch (e) {}
  if (t === "dark" || t === "light") {
    document.documentElement.setAttribute("data-theme", t);
  }
  // no stored choice: leave attribute off; the prefers-color-scheme CSS block applies
})();

document.addEventListener("DOMContentLoaded", function () {
  var btn = document.getElementById("theme-toggle");
  if (!btn) return;
  btn.addEventListener("click", function () {
    var root = document.documentElement;
    var dark = root.getAttribute("data-theme") === "dark" ||
      (!root.getAttribute("data-theme") &&
       matchMedia("(prefers-color-scheme: dark)").matches);
    var next = dark ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) {}
  });
});
