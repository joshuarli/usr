"""Seed a Pi release cache for runtime tests from the maintainer cache.

The maintainer cache at .work/cache/pi-releases holds the pinned archive for
this host. It is filled from the pinned release only when it is missing, so
repeat test runs need no network. Seeded caches receive a hard link, or a copy
across filesystems. The release consumer then reuses that file without fetching.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/sync"))
import pi_offline  # noqa: E402
import pi_release  # noqa: E402

MAINTAINER_CACHE = ROOT / ".work/cache/pi-releases"


def seed(cache: Path) -> Path:
    pin = pi_release.load_pin()
    archive = pi_release.acquire(pin, pi_offline.platform_key(), MAINTAINER_CACHE)
    cache.mkdir(parents=True, exist_ok=True)
    seeded = cache / archive.name
    if not seeded.exists():
        try:
            os.link(archive, seeded)
        except OSError:
            shutil.copy2(archive, seeded)
    seed_companions(cache, pin)
    return seeded


def seed_companions(cache: Path, pin: dict) -> None:
    try:
        entries = pi_release.companions(pin)
    except Exception:
        return
    import hashlib
    import companions

    companions.acquire(pin, MAINTAINER_CACHE)
    key = hashlib.sha256(pin["provenance_sha256"].encode()).hexdigest()
    names = [f"companions-{key}.json", f"companions-{key}.SHA256SUMS"]
    names.extend(entries[name]["sha256"] + ".tgz" for name in pi_release.COMPANIONS)
    for name in names:
        source = MAINTAINER_CACHE / name
        target = cache / name
        if target.exists():
            continue
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)
