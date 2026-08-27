from datetime import date
import pytest
from smw.catalog.normalize import Film, Override, PreopeningEstimate, build_films
from smw.config.groups import Group, PlayerPicks
from smw.ingest.boxoffice import ChartRow

TODAY = date(2026, 7, 1)

def _group(*titles):
    ranked = list(titles) + [f"Pad{i}" for i in range(10 - len(titles))]
    return Group("g", "G", {"u": PlayerPicks("u", tuple(ranked), ("DH1", "DH2", "DH3"))})

def _films(season, **kw):
    args = dict(groups=[], chart_rows=[], grosses={}, carried=set(),
                overrides={}, preopening={}, today=TODAY)
    args.update(kw)
    return {f.title: f for f in build_films(season, **args)}

def test_candidate_set_union(season):
    films = _films(
        season,
        groups=[_group("Picked Film")],
        chart_rows=[ChartRow("Chart Film", 100.0, date(2026, 5, 8), False)],
        grosses={"Chart Film": 100.0, "Carried Film": 50.0},
        carried={"Carried Film"},
        preopening={"Analyst Film": PreopeningEstimate(release_date=date(2026, 8, 1))},
    )
    for t in ("Picked Film", "Chart Film", "Carried Film", "Analyst Film",
              "DH1", "Pad0"):
        assert t in films

def test_chart_contenders_cap(season):
    rows = [ChartRow(f"C{i:03d}", 1000.0 - i, date(2026, 5, 8), False) for i in range(40)]
    films = _films(season, chart_rows=rows,
                   grosses={r.title: r.gross for r in rows})
    # top `chart_contenders` (25) by gross admitted; the rest only if carried/picked
    assert "C000" in films and "C024" in films and "C025" not in films

def test_release_date_precedence(season):
    est = PreopeningEstimate(release_date=date(2026, 8, 20))
    films = _films(
        season,
        chart_rows=[ChartRow("OnChart", 10.0, date(2026, 6, 5), False)],
        grosses={"OnChart": 10.0, "GrossOnly": 5.0},
        carried={"GrossOnly"},
        overrides={"OnChart": Override(release_date=date(2026, 6, 12))},
        preopening={"AnalystOnly": est},
    )
    assert films["OnChart"].release_date == date(2026, 6, 12)   # override beats chart
    assert films["AnalystOnly"].release_date == date(2026, 8, 20)  # estimate file
    assert films["GrossOnly"].release_date == TODAY             # positive gross, no date info
    films2 = _films(season, groups=[_group("NoData")])
    assert films2["NoData"].release_date == season.window_end   # nothing at all

def test_status_inference(season):
    films = _films(
        season,
        chart_rows=[ChartRow("Playing", 10.0, date(2026, 6, 5), False)],
        grosses={"Playing": 10.0, "Faded": 5.0},
        carried={"Faded"},
        overrides={"Forced": Override(status="closed"), "Playing2": Override()},
        groups=[_group("Future", "Forced")],
        preopening={"Future": PreopeningEstimate(release_date=date(2026, 8, 1))},
    )
    assert films["Playing"].status == "in_theaters"   # gross > 0, on chart
    assert films["Faded"].status == "closed"          # gross > 0, absent from chart
    assert films["Future"].status == "pre_release"    # release date after today
    assert films["Forced"].status == "closed"         # explicit override wins

def test_category_from_override_default_wide(season):
    films = _films(season, groups=[_group("Toon")],
                   overrides={"Toon": Override(category="animated_family")})
    assert films["Toon"].category == "animated_family"
    assert films["Pad0"].category == "wide"

def test_roster_variant_resolves_to_canonical_gross(season):
    # Alias application point 2 (§6.5): the roster's spelling finds the canonical record.
    films = _films(
        season,
        groups=[_group("Variant Spelling")],
        grosses={"Canonical": 42.0},
        carried={"Canonical"},
        overrides={"Variant Spelling": Override(alias_of="Canonical")},
    )
    assert "Variant Spelling" not in films
    assert films["Canonical"].cumulative_gross == 42.0

def test_alias_collapsing_two_picks_is_rejected():
    from smw.catalog.normalize import canonical_group
    g = _group("Variant", "Canonical")
    with pytest.raises(ValueError, match="u.*Canonical"):
        canonical_group(g, {"Variant": Override(alias_of="Canonical")})
    assert canonical_group(g, {}) == g
