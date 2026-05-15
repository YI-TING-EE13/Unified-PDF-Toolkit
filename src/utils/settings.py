"""Lightweight JSON settings persistence for UI defaults."""

import json
from pathlib import Path
from typing import Any

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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(settings, file, indent=2, sort_keys=True)


def get_setting(key: str, default: Any = None) -> Any:
    return load_settings().get(key, default)


def set_setting(key: str, value: Any) -> None:
    settings = load_settings()
    settings[key] = value
    save_settings(settings)
