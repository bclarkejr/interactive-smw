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
    players: dict[str, PlayerPicks] = {}
    for username, picks in (raw.get("players") or {}).items():
        ranked = tuple(picks.get("ranked") or [])
        dark = tuple(picks.get("dark_horses") or [])
        if len(ranked) != 10:
            raise ValueError(f"{username}: expected exactly 10 ranked picks, got {len(ranked)}")
        if len(dark) != 3:
            raise ValueError(f"{username}: expected exactly 3 dark horses, got {len(dark)}")
        if len(set(ranked + dark)) != 13:
            raise ValueError(f"{username}: all 13 titles must be distinct")
        players[username] = PlayerPicks(username=username, ranked=ranked, dark_horses=dark)
    return Group(group_id=raw["group_id"], display_name=raw["display_name"], players=players)
