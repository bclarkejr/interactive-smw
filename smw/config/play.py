"""Play-along build configuration (play-along spec §6.1). Optional per season."""
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

USERNAME_RE = re.compile(r"[a-z0-9][a-z0-9-]{1,22}[a-z0-9]")  # §3.3, fullmatch


@dataclass(frozen=True)
class PlayConfig:
    api_base_url: str
    default_group: tuple[str, ...]


def load_play(path: Path) -> PlayConfig | None:
    path = Path(path)
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a mapping")
    unknown = set(raw) - {"api_base_url", "default_group"}
    if unknown:
        raise ValueError(f"{path}: unknown key(s): {', '.join(sorted(unknown))}")
    url = raw.get("api_base_url")
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        raise ValueError(f"{path}: api_base_url must be a string starting with https:// (or http://)")
    if url.endswith("/"):
        raise ValueError(f"{path}: api_base_url must not have a trailing slash")
    if "?" in url or "#" in url:
        raise ValueError(f"{path}: api_base_url must not carry a query or fragment")
    group = raw.get("default_group")
    if group is None:
        group = []
    if not isinstance(group, list):
        raise ValueError(f"{path}: default_group must be a list of usernames")
    for u in group:
        if not isinstance(u, str) or not USERNAME_RE.fullmatch(u):
            raise ValueError(f"{path}: default_group entry {u!r} is not a valid username "
                             "(3-24 chars: lowercase, digits, interior hyphens)")
    if len(set(group)) != len(group):
        raise ValueError(f"{path}: default_group has duplicate usernames")
    return PlayConfig(api_base_url=url, default_group=tuple(group))
