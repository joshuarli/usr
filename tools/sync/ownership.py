"""Record content identities only for objects claimed by a successful sync install."""

from __future__ import annotations

import hashlib
import fcntl
from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat
import tempfile


@contextmanager
def ownership_lock(ownership: Path):
    """Cross-process writer lease for the legacy paths and verified manifest.

    Acquire before *reading* records; hold through the last persist/installer
    operation. Never unlink this lock file: unlinking can split the lease into
    separate inodes and allow concurrent writers.
    """
    ownership.parent.mkdir(parents=True, exist_ok=True)
    lockfile = Path(str(ownership) + ".lock")
    fd = os.open(lockfile, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def records(path: Path) -> set[tuple[str, Path]]:
    if not path.is_file():
        return set()
    result: set[tuple[str, Path]] = set()
    for line in path.read_text().splitlines():
        kind, tab, raw = line.partition("\t")
        if tab and kind in ("F", "D", "E", "K") and raw:
            result.add((kind, Path(raw)))
    return result


def manifest_path(ownership: Path) -> Path:
    return Path(str(ownership) + ".verified.json")


def fingerprint(path: Path, kind: str) -> str | None:
    """Fingerprint content, modes, relative paths and symlink destinations without following links."""
    if not path.is_symlink() and not path.exists():
        return None
    if kind == "D" and (not path.is_dir() or path.is_symlink()):
        return None
    if kind in ("F", "K") and path.is_dir() and not path.is_symlink():
        return None
    digest = hashlib.sha256()

    def visit(item: Path, label: str) -> None:
        st = item.lstat()
        mode = stat.S_IMODE(st.st_mode)
        if stat.S_ISLNK(st.st_mode):
            digest.update(f"L {label} {mode:o} {os.readlink(item)}\n".encode())
        elif stat.S_ISREG(st.st_mode):
            digest.update(f"F {label} {mode:o} {st.st_size}\n".encode())
            with item.open("rb") as stream:
                for part in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(part)
        elif stat.S_ISDIR(st.st_mode):
            digest.update(f"D {label} {mode:o}\n".encode())
            for child in sorted(item.iterdir(), key=lambda p: p.name):
                visit(child, label + "/" + child.name)
        else:
            raise ValueError(f"unverifiable special file: {item}")

    visit(path, ".")
    return digest.hexdigest()


def read_manifest(ownership: Path) -> dict[str, dict[str, str]]:
    path = manifest_path(ownership)
    if path.is_symlink():
        raise ValueError(f"symlinked ownership manifest: {path}")
    if not path.exists():
        return {}
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or value.get("schema") != 1 or not isinstance(value.get("entries"), dict):
        raise ValueError(f"unrecognized ownership manifest: {path}")
    entries = value["entries"]
    if any(not isinstance(k, str) or not isinstance(v, dict) or
           set(v) != {"kind", "fingerprint"} or
           not isinstance(v["kind"], str) or not isinstance(v["fingerprint"], str)
           for k, v in entries.items()):
        raise ValueError(f"invalid ownership manifest: {path}")
    return entries


def capture_new(ownership: Path, before: set[tuple[str, Path]],
                claimed: set[tuple[str, Path]] | None = None) -> None:
    """Never bless legacy path-only records; a leaf installer must report an actual installation."""
    entries = read_manifest(ownership)
    changed = False
    candidates = records(ownership) - before if claimed is None else records(ownership) & claimed
    for kind, path in sorted(candidates, key=lambda x: (x[0], str(x[1]))):
        if kind not in ("F", "D", "K"):
            continue
        identity = fingerprint(path, kind)
        if identity is None:
            continue
        entries[str(path)] = {"kind": kind, "fingerprint": identity}
        changed = True
    if not changed:
        return
    path = manifest_path(ownership)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".sync-owned-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump({"schema": 1, "entries": entries}, stream, sort_keys=True)
            stream.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
