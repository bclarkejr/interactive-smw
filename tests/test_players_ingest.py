import pytest
import requests
from smw.ingest import players

def test_picked_titles_unions_all_strings_and_skips_junk():
    rows = [
        {"username": "a", "ranked": ["X", "Y"], "dark_horses": ["Z"]},
        {"username": "b", "ranked": "not a list", "dark_horses": ["Z", 7, None]},
        "not a dict",
    ]
    assert players.picked_titles(rows) == {"X", "Y", "Z"}

def test_fetch_players_calls_the_endpoint(monkeypatch):
    seen = {}
    class R:
        def raise_for_status(self): pass
        def json(self): return {"year": 2026, "players": [{"username": "a"}]}
    def get(url, timeout):
        seen["url"], seen["timeout"] = url, timeout
        return R()
    monkeypatch.setattr(players.requests, "get", get)
    assert players.fetch_players("https://x.example") == [{"username": "a"}]
    assert seen == {"url": "https://x.example/api/players", "timeout": 10}

def test_fetch_players_raises_on_http_error(monkeypatch):
    class R:
        def raise_for_status(self): raise requests.HTTPError("500")
    monkeypatch.setattr(players.requests, "get", lambda url, timeout: R())
    with pytest.raises(requests.HTTPError):
        players.fetch_players("https://x.example")

def test_fetch_players_raises_on_wrong_shape(monkeypatch):
    class R:
        def raise_for_status(self): pass
        def json(self): return {"players": "nope"}
    monkeypatch.setattr(players.requests, "get", lambda url, timeout: R())
    with pytest.raises(ValueError, match="players"):
        players.fetch_players("https://x.example")
