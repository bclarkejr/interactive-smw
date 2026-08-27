import json
from datetime import date
from pathlib import Path
import pytest
import smw.render.build as build
from tests.conftest import FIXTURES

TODAY = date(2026, 8, 15)
CHART_HTML = (FIXTURES / "synthetic_chart.html").read_text()

@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    (d / "groups").mkdir(parents=True)
    (d / "season.yaml").write_text(
        "year: 2026\nwindow_start: 2026-05-01\nwindow_end: 2026-09-07\n"
        "seed: 42\nmonte_carlo_trials: 500\nmin_projections_for_forecast: 25\n")
    (d / "groups" / "g.yaml").write_text(
        "group_id: g\ndisplay_name: G\nplayers:\n"
        "  alice:\n"
        "    ranked: [Big Summer Film, Mid June Comedy, Labor Day Opener, F4, F5, F6, F7, F8, F9, F10]\n"
        "    dark_horses: [D1, D2, Tiny Tail Film]\n")
    return d

@pytest.fixture(autouse=True)
def offline_chart(monkeypatch):
    monkeypatch.setattr(build, "fetch", lambda year: CHART_HTML)

def _run(data_dir, tmp_path, today=TODAY, local=True):
    out = tmp_path / "out"
    build.run_build(data_dir, out, today, local=local)
    return out

def test_writes_all_pages_and_data_json(data_dir, tmp_path):
    out = _run(data_dir, tmp_path)
    for f in ("index.html", "whatif.html", "scenarios.html", "history.html",
              "rules.html", "data.json"):
        assert (out / f).exists()

def test_degraded_run_data_json_shape(data_dir, tmp_path):
    # 4 windowed chart films, but Labor Day Opener (Sep 7) is pre_release on Aug 15
    # with no analyst entry → 3 non-zero projections, threshold 25 → Early.
    # §5.7: the six forecast keys MUST be present as maps of every username to null.
    out = _run(data_dir, tmp_path)
    d = json.loads((out / "data.json").read_text())
    assert d["forecast_available"] is False
    assert "only 3 films have non-zero projections" in d["forecast_unavailable_reason"]
    for key in ("win_prob", "tie_prob", "median_final_pts",
                "p10_final_pts", "p90_final_pts"):
        assert d[key] == {"alice": None}
    assert d["winning_scenarios"] == {"alice": None}
    assert d["captured_at"] == "2026-08-15"
    assert isinstance(d["current_points"]["alice"], int)
    assert d["non_zero_projections"] == 3

def _add_estimates(data_dir, n=8):
    # Complete analyst entries for n extra in-window films → n more non-zero
    # projections (3 chart films + n).
    entries = "".join(
        f'"Estimated Film {i}":\n'
        "  release_date: 2026-07-10\n"
        "  opening_weekend_estimate: 40_000_000\n"
        "  total_domestic_estimate: 110_000_000\n"
        "  confidence: med\n"
        for i in range(n))
    (data_dir / "preopening_projections.yaml").write_text(entries)

def test_forecast_gate_boundary(data_dir, tmp_path):
    # §13.5 named gap: one below the threshold degrades, at the threshold forecasts.
    _add_estimates(data_dir, n=8)   # 3 + 8 = 11 non-zero projections
    season_yaml = (data_dir / "season.yaml").read_text()
    (data_dir / "season.yaml").write_text(
        season_yaml.replace("min_projections_for_forecast: 25",
                            "min_projections_for_forecast: 12"))
    out = _run(data_dir, tmp_path)  # 11 < 12 → degraded, no forecast keys populated
    d = json.loads((out / "data.json").read_text())
    assert d["forecast_available"] is False
    assert d["win_prob"] == {"alice": None}
    (data_dir / "season.yaml").write_text(
        season_yaml.replace("min_projections_for_forecast: 25",
                            "min_projections_for_forecast: 11"))
    out = _run(data_dir, tmp_path)  # 11 >= 11 (and >= 10 structural) → forecasts
    d = json.loads((out / "data.json").read_text())
    assert d["forecast_available"] is True
    assert isinstance(d["win_prob"]["alice"], float)

def test_structural_floor_dominates_policy_threshold(data_dir, tmp_path):
    # Threshold met but fewer than 10 projected films: a top ten cannot be ranked
    # (§9.5 structural). The site build must degrade, not crash.
    season_yaml = (data_dir / "season.yaml").read_text()
    (data_dir / "season.yaml").write_text(
        season_yaml.replace("min_projections_for_forecast: 25",
                            "min_projections_for_forecast: 3"))
    out = _run(data_dir, tmp_path)  # 3 >= 3 policy, but 3 < 10 structural
    d = json.loads((out / "data.json").read_text())
    assert d["forecast_available"] is False

def test_local_run_appends_nothing(data_dir, tmp_path):
    _run(data_dir, tmp_path, local=True)
    assert not (data_dir / "box_office_history.jsonl").exists()
    assert not (data_dir / "forecast_history.jsonl").exists()

def test_production_run_appends_box_office_rows(data_dir, tmp_path):
    # §13.5 named gap: a production run appends the expected rows; local appends none.
    _run(data_dir, tmp_path, local=False)
    lines = [json.loads(l) for l in
             (data_dir / "box_office_history.jsonl").read_text().splitlines()]
    titles = {l["movie"] for l in lines}
    assert "Big Summer Film" in titles and "Tiny Tail Film" in titles
    assert all(l["date"] == "2026-08-15" for l in lines)
    assert all(l["cumulative_gross"] > 0 for l in lines)
    # degraded run → no forecast history line (the chart gap, §5.6)
    assert not (data_dir / "forecast_history.jsonl").exists()

def test_frozen_run_never_fetches(data_dir, tmp_path, monkeypatch):
    def boom(year):
        raise AssertionError("chart fetched after freeze")
    monkeypatch.setattr(build, "fetch", boom)
    # seed history so resolution has something to carry
    (data_dir / "box_office_history.jsonl").write_text(
        '{"movie": "Big Summer Film", "date": "2026-09-08", "cumulative_gross": 100.0}\n')
    out = _run(data_dir, tmp_path, today=date(2026, 9, 9))
    assert (out / "index.html").exists()

def test_missing_history_file_is_warning_not_error(data_dir, tmp_path, capsys):
    _run(data_dir, tmp_path)
    assert "history" in capsys.readouterr().out.lower()

def test_roster_alias_scores_against_canonical_title(data_dir, tmp_path):
    # §6.5 point 2: a roster's variant spelling must score like the canonical title.
    baseline = json.loads((_run(data_dir, tmp_path) / "data.json").read_text())
    (data_dir / "movies_overrides.yaml").write_text(
        '"Big Summer Movie":\n  alias_of: "Big Summer Film"\n')
    g = (data_dir / "groups" / "g.yaml").read_text()
    (data_dir / "groups" / "g.yaml").write_text(
        g.replace("ranked: [Big Summer Film,", "ranked: [Big Summer Movie,"))
    d = json.loads((_run(data_dir, tmp_path) / "data.json").read_text())
    assert baseline["current_points"]["alice"] > 0
    assert d["current_points"]["alice"] == baseline["current_points"]["alice"]

def test_final_state_collapses_projections_and_forecasts(data_dir, tmp_path, monkeypatch):
    # §10.1 Final: chart frozen, every projection == frozen gross with sigma 0, and the
    # standings run regardless of the 25-film policy threshold.
    monkeypatch.setattr(build, "fetch", lambda year: (_ for _ in ()).throw(AssertionError()))
    rows = [{"movie": f"Film {i:02d}", "date": "2026-09-08", "cumulative_gross": 1e6 * (20 - i)}
            for i in range(12)]
    (data_dir / "box_office_history.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")
    _add_estimates(data_dir, n=3)  # zero-gross films with estimates: must NOT project
    out = _run(data_dir, tmp_path, today=date(2026, 9, 9))
    d = json.loads((out / "data.json").read_text())
    assert d["forecast_available"] is True
    assert all(p["sigma"] == 0.0 and p["median_in_window_gross"] == p["floor"]
               for p in d["projections"])
    assert all(p["median_in_window_gross"] == 0.0 for p in d["projections"]
               if p["movie_title"].startswith("Estimated Film"))

def test_production_history_page_includes_current_refresh(data_dir, tmp_path):
    _add_estimates(data_dir, n=8)
    (data_dir / "season.yaml").write_text(
        (data_dir / "season.yaml").read_text().replace(
            "min_projections_for_forecast: 25", "min_projections_for_forecast: 11"))
    out = _run(data_dir, tmp_path, local=False)
    assert (data_dir / "forecast_history.jsonl").exists()
    html = (out / "history.html").read_text()
    assert "No forecast history yet" not in html
    assert "2026-08-15" in html

def test_projection_uses_todays_snapshot_not_just_persisted_history(data_dir, tmp_path):
    # Observed-decay blend needs ≥3 snapshots; two persisted + today's = 3.
    hist = [{"movie": "Big Summer Film", "date": "2026-08-01", "cumulative_gross": 100e6},
            {"movie": "Big Summer Film", "date": "2026-08-08", "cumulative_gross": 200e6}]
    (data_dir / "box_office_history.jsonl").write_text(
        "\n".join(json.dumps(r) for r in hist) + "\n")
    d = json.loads((_run(data_dir, tmp_path) / "data.json").read_text())
    big = next(p for p in d["projections"] if p["movie_title"] == "Big Summer Film")
    (data_dir / "box_office_history.jsonl").unlink()
    d0 = json.loads((_run(data_dir, tmp_path) / "data.json").read_text())
    big0 = next(p for p in d0["projections"] if p["movie_title"] == "Big Summer Film")
    assert big["median_in_window_gross"] != big0["median_in_window_gross"]

def test_degraded_production_refresh_shows_as_history_gap(data_dir, tmp_path):
    # Refresh 1 (live) appends a forecast row; refresh 2 (degraded) appends only
    # box-office rows; the history page must still list refresh 2's date as a gap.
    _add_estimates(data_dir, n=8)
    season = (data_dir / "season.yaml").read_text()
    (data_dir / "season.yaml").write_text(
        season.replace("min_projections_for_forecast: 25", "min_projections_for_forecast: 11"))
    _run(data_dir, tmp_path, today=date(2026, 8, 8), local=False)
    (data_dir / "season.yaml").write_text(season)  # back to 25 → degraded
    out = _run(data_dir, tmp_path, today=date(2026, 8, 15), local=False)
    html = (out / "history.html").read_text()
    assert "2026-08-08" in html and "2026-08-15" in html
    assert 'class="line series-0" d="M' in html and html.count("<circle") == 1
