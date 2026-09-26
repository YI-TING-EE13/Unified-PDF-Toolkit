"""Strict parsing and comparison for numeric dotted versions."""

from __future__ import annotations

import re
from typing import Any

_NUMERIC_VERSION = re.compile(r"[0-9]+(?:\.[0-9]+)*\Z")


def parse_numeric_version(value: Any) -> tuple[int, ...] | None:
    """Parse a complete numeric dotted version without guessing its format."""

    if not isinstance(value, str):
        return None
    text = value.strip()
    if not _NUMERIC_VERSION.fullmatch(text):
        return None
    try:
        return tuple(int(component) for component in text.split("."))
    except ValueError:
        return None


def numeric_version_at_least(
    version: tuple[int, ...], minimum: tuple[int, ...]
) -> bool:
    """Compare numeric versions, treating omitted trailing components as zero."""

    width = max(len(version), len(minimum))
    normalized_version = version + (0,) * (width - len(version))
    normalized_minimum = minimum + (0,) * (width - len(minimum))
    return normalized_version >= normalized_minimum
