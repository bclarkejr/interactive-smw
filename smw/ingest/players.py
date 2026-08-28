"""Play-along roster fetch (play-along spec §6.3). Optional network dependency:
the caller warns and continues on any exception."""
import requests


def fetch_players(api_base_url: str) -> list[dict]:
    r = requests.get(f"{api_base_url}/api/players", timeout=10)
    r.raise_for_status()
    body = r.json()
    if not isinstance(body, dict) or not isinstance(body.get("players"), list):
        raise ValueError("players API response has no 'players' list")
    return body["players"]


def picked_titles(players: list[dict]) -> set[str]:
    titles: set[str] = set()
    for p in players:
        if not isinstance(p, dict):
            continue
        for key in ("ranked", "dark_horses"):
            v = p.get(key)
            if isinstance(v, list):
                titles.update(t for t in v if isinstance(t, str) and t.strip())
    return titles
