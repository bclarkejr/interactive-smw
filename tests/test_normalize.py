from datetime import date
import pytest
from smw.catalog.normalize import (
    Override, PreopeningEstimate, apply_chart_aliases, canonical,
    load_overrides, load_preopening,
)
from smw.ingest.boxoffice import ChartRow

def test_load_overrides_all_fields(tmp_path):
    p = tmp_path / "movies_overrides.yaml"
    p.write_text(
        '"Toy Story 5":\n  category: animated_family\n'
        '"Variant Title":\n  alias_of: "Canonical Title"\n'
        '"Bad Date Film":\n  release_date: 2026-07-10\n  status: pre_release\n'
    )
    ov = load_overrides(p)
    assert ov["Toy Story 5"].category == "animated_family"
    assert ov["Variant Title"].alias_of == "Canonical Title"
    assert ov["Bad Date Film"].release_date == date(2026, 7, 10)
    assert ov["Bad Date Film"].status == "pre_release"

def test_missing_overrides_file_is_empty(tmp_path):
    assert load_overrides(tmp_path / "nope.yaml") == {}

def test_unknown_override_key_raises(tmp_path):
    p = tmp_path / "o.yaml"
    p.write_text('"X":\n  categry: wide\n')
    with pytest.raises(ValueError, match="categry"):
        load_overrides(p)

def test_canonical_resolves_alias():
    ov = {"Variant": Override(alias_of="Canonical")}
    assert canonical("Variant", ov) == "Canonical"
    assert canonical("Other", ov) == "Other"

def test_apply_chart_aliases_renames_rows():
    ov = {"Variant": Override(alias_of="Canonical")}
    rows = [ChartRow("Variant", 5.0, date(2026, 6, 1), False),
            ChartRow("Untouched", 1.0, date(2026, 6, 1), False)]
    out = apply_chart_aliases(rows, ov)
    assert [r.title for r in out] == ["Canonical", "Untouched"]
    assert out[0].gross == 5.0

def test_load_preopening_with_underscore_separators(tmp_path):
    p = tmp_path / "pre.yaml"
    p.write_text(
        '"Toy Story 5":\n'
        "  release_date: 2026-06-19\n"
        "  opening_weekend_estimate: 168_000_000\n"
        "  total_domestic_estimate: 559_000_000\n"
        "  confidence: med\n"
        '  source: "Box Office Theory"\n'
        "  as_of: 2026-04-23\n"
    )
    pre = load_preopening(p)
    est = pre["Toy Story 5"]
    assert est.opening_weekend_estimate == 168_000_000
    assert est.total_domestic_estimate == 559_000_000
    assert est.confidence == "med"
    assert est.is_complete()

def test_partial_entry_is_not_complete(tmp_path):
    p = tmp_path / "pre.yaml"
    p.write_text('"X":\n  opening_weekend_estimate: 10_000_000\n')
    assert not load_preopening(p)["X"].is_complete()

def test_nonpositive_figure_is_not_complete():
    est = PreopeningEstimate(opening_weekend_estimate=0,
                             total_domestic_estimate=100.0, confidence="med")
    assert not est.is_complete()

def test_bad_confidence_raises(tmp_path):
    p = tmp_path / "pre.yaml"
    p.write_text('"X":\n  confidence: certain\n')
    with pytest.raises(ValueError, match="confidence"):
        load_preopening(p)

def test_release_date_override_applied_to_chart_rows_before_window_filter(season):
    from smw.ingest.boxoffice import windowed
    ov = {"Misdated": Override(release_date=date(2026, 5, 8))}
    rows = apply_chart_aliases([ChartRow("Misdated", 9.0, date(2026, 4, 24), False)], ov)
    assert rows[0].release_date == date(2026, 5, 8)
    assert [r.title for r in windowed(rows, season)] == ["Misdated"]

def test_alias_entry_metadata_folds_onto_canonical(tmp_path):
    p = tmp_path / "o.yaml"
    p.write_text('"Variant":\n  alias_of: "Canon"\n  category: animated_family\n  release_date: 2026-07-10\n'
                 '"Canon":\n  status: closed\n')
    ov = load_overrides(p)
    assert ov["Canon"] == Override(category="animated_family", release_date=date(2026, 7, 10),
                                   status="closed")
    assert ov["Variant"].alias_of == "Canon"

def test_alias_entry_conflicting_metadata_rejected(tmp_path):
    p = tmp_path / "o.yaml"
    p.write_text('"Variant":\n  alias_of: "Canon"\n  category: animated_family\n'
                 '"Canon":\n  category: wide\n')
    with pytest.raises(ValueError, match="conflicting category"):
        load_overrides(p)

@pytest.mark.parametrize("body,needle", [
    ('  opening_weekend_estimate: "168000000"\n', "opening_weekend_estimate"),
    ('  release_date: "June 19"\n', "release_date"),
    ('  source: 42\n', "source"),
])
def test_preopening_bad_types_fail_at_load(tmp_path, body, needle):
    p = tmp_path / "pre.yaml"
    p.write_text('"X":\n' + body)
    with pytest.raises(ValueError, match=needle):
        load_preopening(p)

@pytest.mark.parametrize("body,needle", [
    ('  alias_of: 12\n', "alias_of"),
    ('  release_date: "July 10"\n', "release_date"),
])
def test_override_bad_types_fail_at_load(tmp_path, body, needle):
    p = tmp_path / "o.yaml"
    p.write_text('"X":\n' + body)
    with pytest.raises(ValueError, match=needle):
        load_overrides(p)
