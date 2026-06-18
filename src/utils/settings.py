"""Lightweight JSON settings persistence for UI defaults."""

import json
from pathlib import Path
from typing import Any, List

from .file_ops import get_default_save_dir


def _settings_path() -> Path:
    base = Path(get_default_save_dir("Settings"))
    return base / "settings.json"


def load_settings() -> dict:
    path = _settings_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_settings(settings: dict) -> None:
    path = _settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(settings, file, indent=2, sort_keys=True)
    except OSError:
        # Settings are convenience state. Workflow output must not fail because
        # a user profile settings file is locked or temporarily unwritable.
        return


def get_setting(key: str, default: Any = None) -> Any:
    return load_settings().get(key, default)


def set_setting(key: str, value: Any) -> None:
    settings = load_settings()
    settings[key] = value
    save_settings(settings)


def get_recent_paths(key: str, limit: int = 10) -> List[str]:
    value = get_setting(key, [])
    if not isinstance(value, list):
        return []
    paths = [str(item) for item in value if item]
    return paths[:limit]


def add_recent_path(key: str, path: str, limit: int = 10) -> None:
    if not path:
        return
    paths = [item for item in get_recent_paths(key, limit) if item != path]
    paths.insert(0, path)
    set_setting(key, paths[:limit])


def clear_recent_paths(key: str) -> None:
    set_setting(key, [])
