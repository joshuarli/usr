"""Reject network-installed Pi packages; all extensions live in usr's runtime archive."""
from __future__ import annotations
import json
from pathlib import Path


def pins(settings_file: Path) -> list[tuple[str, str, str]]:
    settings = json.loads(settings_file.read_text())
    packages = settings.get("packages")
    if not isinstance(packages, list):
        raise ValueError("Pi packages must be an array")
    if packages:
        raise ValueError("Pi npm/git/package installs are forbidden by offline usr runtime")
    return []


def missing(settings_file: Path, home: Path) -> list[tuple[str, str, str, str | None]]:
    pins(settings_file)
    return []
