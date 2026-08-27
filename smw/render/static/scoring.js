"use strict";
function rankedPickPoints(predicted, actual) {
  if (actual === null || actual === undefined) return 0;
  var d = Math.abs(predicted - actual);
  if (d === 0) return (actual === 1 || actual === 10) ? 13 : 10;
  if (d === 1) return 7;
  if (d === 2) return 5;
  return 3;
}
function positionMap(topTitles) {
  var pos = {};
  for (var i = 0; i < topTitles.length; i++) pos[topTitles[i]] = i + 1;
  return pos;
}
function pointsFor(ranked, dark, title, topTitles) {
  var pos = positionMap(topTitles)[title];
  var ri = ranked.indexOf(title);
  if (ri >= 0) return pos ? rankedPickPoints(ri + 1, pos) : 0;
  if (dark.indexOf(title) >= 0) return pos ? 1 : 0;
  return null; // not picked
}
function scorePlayer(ranked, dark, topTitles) {
  var pos = positionMap(topTitles), total = 0;
  for (var i = 0; i < ranked.length; i++)
    if (pos[ranked[i]]) total += rankedPickPoints(i + 1, pos[ranked[i]]);
  for (var j = 0; j < dark.length; j++)
    if (pos[dark[j]]) total += 1;
  return total;
}
if (typeof module !== "undefined") {
  module.exports = { rankedPickPoints: rankedPickPoints, scorePlayer: scorePlayer };
}
