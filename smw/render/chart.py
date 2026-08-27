"""Hand-rolled SVG line chart for win odds over time (spec §12.4). A few hundred
lines of path arithmetic beats a charting library that would be the page's largest
dependency by an order of magnitude."""
import math
from html import escape

W, H = 660, 300
ML, MR, MT, MB = 48, 118, 12, 30  # right margin leaves room for direct labels
MAX_X_LABELS = 8
DIRECT_LABELS = 4
LABEL_MIN_GAP = 14


def build_history_data(rows: list[dict]) -> "dict | None":
    if not rows:
        return None
    dates = sorted({r["date"] for r in rows})
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

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" class="odds-chart" '
             'aria-label="Each player\'s win probability at every refresh">']
    # gridlines every 10%
    tick = 0.0
    while tick <= ymax + 1e-9:
        y = _y(tick, ymax)
        parts.append(f'<line class="grid" x1="{ML}" y1="{y:.1f}" '
                     f'x2="{W - MR}" y2="{y:.1f}"/>')
        parts.append(f'<text class="y-label" x="{ML - 6}" y="{y + 4:.1f}" '
                     f'text-anchor="end">{round(tick * 100)}%</text>')
        tick += 0.1
    # x labels, thinned, always including the most recent
    step = max(1, math.ceil(n / MAX_X_LABELS))
    idxs = sorted(set(range(0, n, step)) | {n - 1})[-MAX_X_LABELS:]
    for i in idxs:
        parts.append(f'<text class="x-label" x="{_x(i, n):.1f}" y="{H - 8}" '
                     f'text-anchor="middle">{escape(str(dates[i]))}</text>')
    # one path per series; a None breaks the line (§12.4 — a gap means no forecast
    # was produced; drawing through it would assert a number never computed)
    for s in series:
        d_cmds, pen_down = [], False
        for i, v in enumerate(s["values"]):
            if v is None:
                pen_down = False
                continue
            cmd = "L" if pen_down else "M"
            d_cmds.append(f"{cmd}{_x(i, n):.1f} {_y(v, ymax):.1f}")
            pen_down = True
        parts.append(f'<path class="line series-{s["color"]}" d="{" ".join(d_cmds)}"/>')
        for i, v in enumerate(s["values"]):
            if v is not None:
                parts.append(f'<circle class="marker series-{s["color"]}" '
                             f'cx="{_x(i, n):.1f}" cy="{_y(v, ymax):.1f}" r="2.5"/>')
    # direct labels: top four by latest value, nudged apart
    latest = []
    for s in series:
        vals = [v for v in s["values"] if v is not None]
        if vals:
            last_i = max(i for i, v in enumerate(s["values"]) if v is not None)
            latest.append((s, s["values"][last_i], last_i))
    latest.sort(key=lambda t: -t[1])
    placed = []
    for s, v, last_i in latest[:DIRECT_LABELS]:
        y = _y(v, ymax)
        while any(abs(y - py) < LABEL_MIN_GAP for py in placed):
            y += LABEL_MIN_GAP
        placed.append(y)
        x = W - MR + 8
        parts.append(f'<rect class="swatch series-{s["color"]}" x="{x}" '
                     f'y="{y - 8:.1f}" width="8" height="8"/>')
        parts.append(f'<text class="direct-label" x="{x + 12}" y="{y:.1f}">'
                     f'{escape(str(s["name"]))} {round(v * 100)}%</text>')
    parts.append("</svg>")
    return "".join(parts)
