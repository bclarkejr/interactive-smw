import pytest
from smw.config.groups import load_group

VALID = """\
group_id: testers
display_name: "Test League"
players:
  alice:
    ranked: [F1, F2, F3, F4, F5, F6, F7, F8, F9, F10]
    dark_horses: [D1, D2, D3]
"""

def _write(tmp_path, text):
    p = tmp_path / "g.yaml"
    p.write_text(text)
    return p

def test_valid_group_loads(tmp_path):
    g = load_group(_write(tmp_path, VALID))
    assert g.group_id == "testers"
    assert g.display_name == "Test League"
    assert g.players["alice"].ranked == tuple(f"F{i}" for i in range(1, 11))
    assert g.players["alice"].dark_horses == ("D1", "D2", "D3")
    assert g.players["alice"].username == "alice"

def test_wrong_ranked_count_names_player(tmp_path):
    bad = VALID.replace(", F10]", "]")
    with pytest.raises(ValueError, match="alice.*10 ranked"):
        load_group(_write(tmp_path, bad))

def test_wrong_dark_horse_count_names_player(tmp_path):
    bad = VALID.replace(", D3]", "]")
    with pytest.raises(ValueError, match="alice.*3 dark horse"):
        load_group(_write(tmp_path, bad))

def test_duplicate_title_rejected(tmp_path):
    bad = VALID.replace("dark_horses: [D1, D2, D3]", "dark_horses: [D1, D2, F1]")
    with pytest.raises(ValueError, match="alice.*distinct"):
        load_group(_write(tmp_path, bad))

def test_empty_players_is_legal(tmp_path):
    g = load_group(_write(tmp_path, "group_id: t\ndisplay_name: T\nplayers: {}\n"))
    assert g.players == {}
