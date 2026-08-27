"""Hand-rolled SVG line chart for win odds over time (spec §12.4). A few hundred
lines of path arithmetic beats a charting library that would be the page's largest
dependency by an order of magnitude."""
import math
from html import escape

W, H = 920, 360
ML, MR, MT, MB = 52, 110, 16, 34  # right margin leaves room for direct labels
MAX_X_LABELS = 8
DIRECT_LABELS = 4
LABEL_MIN_GAP = 15


def build_history_data(rows: list[dict], refresh_dates=()) -> "dict | None":
    """`refresh_dates`: extra axis dates (production refreshes that produced no forecast);
    they render as gaps, never interpolated (§12.4)."""
    if not rows:
        return None
    
    # The logic with first is meant to only start the x-axis at the first date that has a forecast.
    # Otherwise, the graph will start at the first date of the wager, even though we know that the
    # first half of the wager will never have a forecast, since too few movies will have been released.
    first = min(r["date"] for r in rows)

    dates = sorted({r["date"] for r in rows} | {d for d in refresh_dates if d >= first})
    players = sorted({r["player"] for r in rows})
    values: dict[tuple[str, str], float] = {}
    for r in rows:  # file order: later run supersedes a shared date
        values[(r["date"], r["player"])] = r["win_prob"]
    return {
        "dates": dates,
        "series": [
            {"name": p, "color": i % 8,
             "values": [values.get((d, p)) for d in dates]}
            for i, p in enumerate(players)
        ],
    }


def _x(i: int, n: int) -> float:
    if n == 1:
        return ML + (W - ML - MR) / 2
    return ML + i * (W - ML - MR) / (n - 1)


def _y(v: float, ymax: float) -> float:
    return MT + (1 - v / ymax) * (H - MT - MB)


def render_chart_svg(data: dict) -> str:
    dates, series = data["dates"], data["series"]
    n = len(dates)
    vmax = max((v for s in series for v in s["values"] if v is not None), default=0.0)
    ymax = max(0.1, math.floor(vmax * 10 + 1) / 10)  # next decile above the max
    ymax = min(ymax, 1.0)
    iw = W - ML - MR

    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" '
             f'aria-label="Line chart of win probability by refresh date for '
             f'{len(series)} players">']
    tick = 0.0
    while tick <= ymax + 1e-9:  # gridlines every 10%
        y = _y(tick, ymax)
        parts.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{ML + iw}" y2="{y:.1f}" '
                     'stroke="var(--grid)"/>')
        parts.append(f'<text x="{ML - 8}" y="{y + 4:.1f}" text-anchor="end">'
                     f'{round(tick * 100)}%</text>')
        tick += 0.1
    # x labels thinned to <= 8, walking back from the most recent (mockup)
    step = max(1, math.ceil(n / MAX_X_LABELS))
    for i in sorted(range(n - 1, -1, -step)):
        parts.append(f'<text x="{_x(i, n):.1f}" y="{H - 10}" text-anchor="middle">'
                     f'{escape(str(dates[i]))}</text>')
    y0 = _y(0.0, ymax)
    parts.append(f'<line x1="{ML}" y1="{y0:.1f}" x2="{ML + iw}" y2="{y0:.1f}" '
                 'stroke="var(--baseline)"/>')
    # one path per series; a None breaks the line (§12.4 — a gap means no forecast
    # was produced; drawing through it would assert a number never computed)
    for s in series:
        d_cmds, pen_down = [], False
        for i, v in enumerate(s["values"]):
            if v is None:
                pen_down = False
                continue
            d_cmds.append(f'{"L" if pen_down else "M"}{_x(i, n):.1f} {_y(v, ymax):.1f}')
            pen_down = True
        parts.append(f'<path class="series-{s["color"]}" d="{" ".join(d_cmds)}" fill="none" '
                     'stroke="var(--series)" stroke-width="2" stroke-linejoin="round" '
                     'stroke-linecap="round"/>')
        for i, v in enumerate(s["values"]):
            if v is not None:
                parts.append(f'<circle class="series-{s["color"]}" cx="{_x(i, n):.1f}" '
                             f'cy="{_y(v, ymax):.1f}" r="3" fill="var(--series)"/>')
    # direct labels: top four by latest value, nudged apart; ink text + coloured swatch
    latest = []
    for s in series:
        idx = [i for i, v in enumerate(s["values"]) if v is not None]
        if idx:
            latest.append((s, s["values"][idx[-1]]))
    latest.sort(key=lambda t: (-t[1], t[0]["name"]))
    latest = latest[:DIRECT_LABELS]
    placed = []
    for s, v in latest:
        y = _y(v, ymax)
        while any(abs(y - py) < LABEL_MIN_GAP for py in placed):
            y += LABEL_MIN_GAP
        placed.append(y)
    # Keep the stack inside the plot: shift everything up by any overflow, then
    # re-separate from the top down so the minimum gap survives the shift.
    bottom, top = H - MB - 4, MT + 10
    overflow = max(0.0, max(placed, default=0.0) - bottom)
    placed = sorted(py - overflow for py in placed)
    for k in range(len(placed)):
        floor_y = top if k == 0 else placed[k - 1] + LABEL_MIN_GAP
        placed[k] = max(placed[k], floor_y)
    for (s, v), y in zip(latest, placed):  # latest is top-down; placed is ascending y
        x = ML + iw + 8
        parts.append(f'<rect class="series-{s["color"]}" x="{x}" y="{y - 9:.1f}" '
                     'width="10" height="10" rx="3" fill="var(--series)"/>')
        parts.append(f'<text class="dl" x="{x + 14}" y="{y:.1f}">'
                     f'{escape(str(s["name"]))}</text>')
    # crosshair: emitted hidden so history.js never needs the SVG namespace URL
    parts.append(f'<line class="xh" x1="{ML}" x2="{ML}" y1="{MT}" y2="{H - MB}" '
                 'stroke="var(--baseline)" stroke-dasharray="3 3" style="display:none"/>')
    parts.append("</svg>")
    return "".join(parts)
