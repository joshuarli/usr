"""Reconcile exact user-level Pi npm packages declared by the tracked profile."""

from __future__ import annotations

import json
import re
from pathlib import Path

NAME = re.compile(r"(?:@[a-z0-9._-]+/)?[a-z0-9._-]+")
VERSION = re.compile(r"\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?")


def pins(settings_file: Path) -> list[tuple[str, str, str]]:
    settings = json.loads(settings_file.read_text())
    if not isinstance(settings, dict) or not isinstance(settings.get("packages"), list):
        raise ValueError("Pi packages must be an array")
    result = []
    for entry in settings["packages"]:
        source = entry if isinstance(entry, str) else entry.get("source") if isinstance(entry, dict) else None
        if not isinstance(source, str) or not source.startswith("npm:"):
            raise ValueError("sync supports only exact-pinned npm Pi packages")
        name, separator, version = source[4:].rpartition("@")
        if not separator or not NAME.fullmatch(name) or not VERSION.fullmatch(version):
            raise ValueError("Pi package requires an exact npm version: " + source)
        result.append((source, name, version))
    return result


def installed_version(home: Path, name: str) -> str | None:
    path = home / ".pi/agent/npm/node_modules" / name / "package.json"
    try:
        data = json.loads(path.read_text())
        value = data.get("version") if isinstance(data, dict) else None
        return value if isinstance(value, str) else None
    except (OSError, ValueError):
        return None


def missing(settings_file: Path, home: Path) -> list[tuple[str, str, str, str | None]]:
    return [(source, name, version, actual)
            for source, name, version in pins(settings_file)
            if (actual := installed_version(home, name)) != version]
