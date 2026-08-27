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
    alice_path = re.search(r'<path class="line series-0" d="([^"]+)"', svg).group(1)
    assert alice_path.count("M") == 2

def test_y_axis_next_decile_above_max():
    svg = render_chart_svg(build_history_data(ROWS))
    assert ">80%<" in svg      # max 0.70 → axis tops at 0.8
    assert ">90%<" not in svg

def test_x_labels_thinned_to_eight_max_including_latest():
    rows = [{"date": f"2026-06-{d:02d}", "player": "a", "win_prob": 0.5}
            for d in range(1, 29)]
    svg = render_chart_svg(build_history_data(rows))
    labels = svg.count('class="x-label"')
    assert labels <= 8
    assert "2026-06-28" in svg
