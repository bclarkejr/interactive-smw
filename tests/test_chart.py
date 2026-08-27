from smw.render.chart import build_history_data, render_chart_svg

ROWS = [
    {"date": "2026-06-01", "player": "bob", "win_prob": 0.30},
    {"date": "2026-06-01", "player": "alice", "win_prob": 0.55},
    {"date": "2026-06-08", "player": "alice", "win_prob": 0.60},
    {"date": "2026-06-08", "player": "bob", "win_prob": 0.25},
    # alice missing on 06-15 → gap in her line
    {"date": "2026-06-15", "player": "bob", "win_prob": 0.20},
    {"date": "2026-06-22", "player": "alice", "win_prob": 0.70},
    {"date": "2026-06-22", "player": "bob", "win_prob": 0.15},
    # same-date duplicate: later line supersedes
    {"date": "2026-06-22", "player": "bob", "win_prob": 0.18},
]

def test_empty_rows_is_none():
    assert build_history_data([]) is None

def test_series_sorted_by_username_with_stable_colors():
    d = build_history_data(ROWS)
    assert [s["name"] for s in d["series"]] == ["alice", "bob"]
    assert [s["color"] for s in d["series"]] == [0, 1]

def test_missing_value_is_null_not_interpolated():
    d = build_history_data(ROWS)
    alice = d["series"][0]
    assert alice["values"] == [0.55, 0.60, None, 0.70]

def test_later_run_supersedes_same_date():
    d = build_history_data(ROWS)
    bob = d["series"][1]
    assert bob["values"][-1] == 0.18

def test_gap_breaks_svg_path():
    svg = render_chart_svg(build_history_data(ROWS))
    # alice's path must contain two M (move) commands: one start, one after the gap
    import re
    alice_path = re.search(r'<path class="series-0" d="([^"]+)"', svg).group(1)
    assert alice_path.count("M") == 2

def test_y_axis_next_decile_above_max():
    svg = render_chart_svg(build_history_data(ROWS))
    assert ">80%<" in svg      # max 0.70 → axis tops at 0.8
    assert ">90%<" not in svg

def test_x_labels_thinned_to_eight_max_including_latest():
    rows = [{"date": f"2026-06-{d:02d}", "player": "a", "win_prob": 0.5}
            for d in range(1, 29)]
    svg = render_chart_svg(build_history_data(rows))
    labels = svg.count('text-anchor="middle"')
    assert labels <= 8
    assert "2026-06-28" in svg

def test_hostile_player_name_is_escaped_in_svg():
    rows = [{"date": "2026-06-01", "player": "<script>x</script>", "win_prob": 0.5}]
    svg = render_chart_svg(build_history_data(rows))
    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg

def test_degraded_refresh_dates_appear_as_gaps():
    rows = [{"date": "2026-06-01", "player": "a", "win_prob": 0.5},
            {"date": "2026-06-15", "player": "a", "win_prob": 0.6}]
    d = build_history_data(rows, refresh_dates={"2026-06-08"})
    assert d["dates"] == ["2026-06-01", "2026-06-08", "2026-06-15"]
    assert d["series"][0]["values"] == [0.5, None, 0.6]
    assert build_history_data([], refresh_dates={"2026-06-08"}) is None

def test_direct_labels_stay_inside_viewbox():
    import re
    from smw.render.chart import H, MB, LABEL_MIN_GAP
    rows = [{"date": "2026-06-01", "player": p, "win_prob": 0.01} for p in "abcd"]
    svg = render_chart_svg(build_history_data(rows))
    ys = sorted(float(y) for y in re.findall(r'class="dl" x="[\d.]+" y="([\d.]+)"', svg))
    assert len(ys) == 4 and ys[-1] <= H - MB
    assert all(b - a >= LABEL_MIN_GAP - 1e-9 for a, b in zip(ys, ys[1:]))

def test_mockup_geometry_and_elements():
    svg = render_chart_svg(build_history_data(ROWS))
    assert svg.startswith('<svg viewBox="0 0 920 360" width="100%" role="img" aria-label="Line chart of win probability by refresh date for 2 players">')
    assert 'stroke="var(--baseline)"' in svg           # 0% baseline
    assert 'stroke="var(--grid)"' in svg               # gridlines
    assert svg.count('r="3"') == 7                     # one marker per value (8 rows, 1 superseded)
    assert 'width="10" height="10" rx="3"' in svg      # direct-label swatch
    assert 'class="dl"' in svg and ">alice</text>" in svg
    assert '<line class="xh"' in svg and 'display:none' in svg
    assert 'class="x-label"' not in svg and 'class="direct-label"' not in svg

def test_history_js_geometry_matches_chart_py():
    from pathlib import Path
    from smw.render.chart import W, ML, MR
    js = (Path(__file__).parent.parent / "smw" / "render" / "static" / "history.js").read_text()
    assert f"var W = {W}, L = {ML}, R = {MR}," in js
