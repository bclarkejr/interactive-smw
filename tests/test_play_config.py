import pytest
from smw.config.play import PlayConfig, load_play


def test_absent_file_is_none(tmp_path):
    assert load_play(tmp_path / "play.yaml") is None


def test_loads_url_and_group(tmp_path):
    p = tmp_path / "play.yaml"
    p.write_text("api_base_url: https://smw-players.example.workers.dev\n"
                 "default_group:\n  - popcorn-goblin\n  - matinee-mike\n")
    assert load_play(p) == PlayConfig("https://smw-players.example.workers.dev",
                                      ("popcorn-goblin", "matinee-mike"))


def test_default_group_may_be_empty_or_omitted(tmp_path):
    p = tmp_path / "play.yaml"
    p.write_text("api_base_url: https://x.example\n")
    assert load_play(p).default_group == ()
    p.write_text("api_base_url: https://x.example\ndefault_group: []\n")
    assert load_play(p).default_group == ()


@pytest.mark.parametrize("text, msg", [
    ("default_group: [a]\n", "api_base_url"),
    ("api_base_url: ftp://x.example\n", "https://"),
    ("api_base_url: https://x.example/\n", "trailing slash"),
    ("api_base_url: https://x.example?y=1\n", "query"),
    ("api_base_url: https://x.example\ndefault_group: popcorn\n", "list"),
    ("api_base_url: https://x.example\ndefault_group: [Popcorn]\n", "username"),
    ("api_base_url: https://x.example\ndefault_group: [aaa, aaa]\n", "duplicate"),
    ("api_base_url: https://x.example\nextra: 1\n", "unknown key"),
    ("- not a mapping\n", "mapping"),
])
def test_rejects_bad_config(tmp_path, text, msg):
    p = tmp_path / "play.yaml"
    p.write_text(text)
    with pytest.raises(ValueError, match=msg):
        load_play(p)
