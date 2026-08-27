import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class PlayerPicks:
    username: str
    ranked: tuple[str, ...]
    dark_horses: tuple[str, ...]


@dataclass(frozen=True)
class Group:
    group_id: str
    display_name: str
    players: dict[str, PlayerPicks]


def load_group(path: Path) -> Group:
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict) or "group_id" not in raw or "display_name" not in raw:
        raise ValueError(f"{path}: group file needs group_id and display_name")
    gid = raw["group_id"]
    if not isinstance(gid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", gid):
        raise ValueError(f"{path}: group_id must be a slug of [a-z0-9_-] (used as a directory name)")
    if not isinstance(raw["display_name"], str) or not raw["display_name"].strip():
        raise ValueError(f"{path}: display_name must be a non-empty string")
    raw_players = raw.get("players")
    if raw_players is None:
        raw_players = {}
    if not isinstance(raw_players, dict):
        raise ValueError(f"{path}: players must be a mapping of username -> picks")
    players: dict[str, PlayerPicks] = {}
    for username, picks in raw_players.items():
        if not isinstance(username, str) or not username.strip():
            raise ValueError(f"{path}: player usernames must be non-empty strings")
        if not isinstance(picks, dict):
            raise ValueError(f"{username}: picks must be a mapping with ranked and dark_horses")
        for key in ("ranked", "dark_horses"):
            v = picks.get(key)
            if v is not None and not isinstance(v, list):
                raise ValueError(f"{username}: {key} must be a YAML list")
        ranked = tuple(picks.get("ranked") or [])
        dark = tuple(picks.get("dark_horses") or [])
        if any(not isinstance(t, str) or not t.strip() for t in ranked + dark):
            raise ValueError(f"{username}: every title must be a non-empty string")
        if len(ranked) != 10:
            raise ValueError(f"{username}: expected exactly 10 ranked picks, got {len(ranked)}")
        if len(dark) != 3:
            raise ValueError(f"{username}: expected exactly 3 dark horses, got {len(dark)}")
        if len(set(ranked + dark)) != 13:
            raise ValueError(f"{username}: all 13 titles must be distinct")
        players[username] = PlayerPicks(username=username, ranked=ranked, dark_horses=dark)
    return Group(group_id=raw["group_id"], display_name=raw["display_name"], players=players)
