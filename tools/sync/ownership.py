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
import threading

_lock_mutex = threading.Lock()
_lock_entries: dict[str, list] = {}


@contextmanager
def ownership_lock(ownership: Path):
    """Cross-process writer lease for the legacy paths and verified manifest.

    Threads in one process share a single flock, reference counted until the
    last holder exits, so parallel tasks in one sync run do not block each
    other. A separate process still blocks until every holder in this process
    has exited. Never unlink this lock file: unlinking can split the lease
    into separate inodes and allow concurrent writers.
    """
    key = str(ownership)
    with _lock_mutex:
        entry = _lock_entries.get(key)
        if entry is None:
            ownership.parent.mkdir(parents=True, exist_ok=True)
            lockfile = Path(str(ownership) + ".lock")
            fd = os.open(lockfile, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
            except BaseException:
                os.close(fd)
                raise
            entry = [fd, 0]
            _lock_entries[key] = entry
        entry[1] += 1
    try:
        yield
    finally:
        with _lock_mutex:
            entry[1] -= 1
            if entry[1] == 0:
                fd = entry[0]
                del _lock_entries[key]
                fcntl.flock(fd, fcntl.LOCK_UN)
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


def merge_claims(ownership: Path, claimed: set[tuple[str, Path]],
                 removed: set[Path] | None = None) -> None:
    """Persist one installer's claims; the caller must hold ownership_lock.

    Leaf installers write claims to a per-task file rather than appending to
    the shared records file, so parallel installs cannot interleave or lose
    records. Removed paths are a superseded install (for example a previous
    Node.js release directory) whose records must not survive the merge.
    """
    claimed = {(kind, path) for kind, path in claimed if kind in ("F", "D", "E", "K")}
    removed = set(removed or ())
    lines = ownership.read_text().splitlines() if ownership.is_file() else []
    existing: set[tuple[str, Path]] = set()
    kept: list[str] = []
    changed = False
    for line in lines:
        kind, tab, raw = line.partition("\t")
        if tab and kind in ("F", "D", "E", "K") and raw:
            existing.add((kind, Path(raw)))
            if Path(raw) in removed:
                changed = True
                continue
        kept.append(line)
    additions = sorted(claimed - existing, key=lambda item: (item[0], str(item[1])))
    for kind, path in additions:
        kept.append(f"{kind}\t{path}")
    if additions:
        changed = True
    if not changed:
        return
    ownership.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(ownership.stat().st_mode) if ownership.exists() else 0o644
    fd, tmp = tempfile.mkstemp(prefix=".dl-owned-", dir=ownership.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w") as stream:
            stream.write("".join(line + "\n" for line in kept))
        os.replace(tmp, ownership)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


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
