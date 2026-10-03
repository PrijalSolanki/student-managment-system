"""Minimal ``.env`` loader.

Implemented locally so the project does not depend on an extra package for
environment handling.  Supports ``KEY=value``, ``export KEY=value``, quoted
values and ``#`` comments.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

BASE_DIR = Path(__file__).resolve().parent.parent


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_env_file(path: Path) -> Dict[str, str]:
    """Return a dict of key/value pairs contained in ``path``."""
    values: Dict[str, str] = {}
    if not path.is_file():
        return values

    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if "#" in value and not (value[:1] in {"'", '"'}):
                value = value.split("#", 1)[0].strip()
            values[key] = _strip_quotes(value)
    return values


def load_env(path: Optional[Path] = None, override: bool = False) -> Dict[str, str]:
    """Load ``.env`` into ``os.environ`` and return the parsed mapping."""
    env_path = path or BASE_DIR / ".env"
    parsed = parse_env_file(env_path)
    for key, value in parsed.items():
        if override or key not in os.environ:
            os.environ[key] = value
    return parsed


def env(key: str, default: Optional[str] = None) -> Optional[str]:
    """Read an environment variable."""
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    return value


def env_bool(key: str, default: bool = False) -> bool:
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def env_int(key: str, default: int) -> int:
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def env_list(key: str, default: str = "") -> list[str]:
    value = env(key, default) or ""
    return [item.strip() for item in value.split(",") if item.strip()]


load_env()
