"""Durable, inode-identified pending link creations.

A staged symlink is hard-linked to its destination, so its inode proves
which link belongs to an interrupted sync. Merely matching link text must
never confer ownership of a pre-existing user link.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from uuid import uuid4


@dataclass(frozen=True)
class PendingLink:
    path: Path
    target: Path
    stage: str
    text: str
    device: int
    inode: int
    journal: Path


def _directory(ownership: Path) -> Path:
    return Path(str(ownership) + ".pending-links")


def _path_for(ownership: Path, destination: Path) -> Path:
    key = hashlib.sha256(os.fsencode(str(destination))).hexdigest()
    return _directory(ownership) / (key + ".json")


def _write_record(path: Path, payload: dict[str, object]) -> None:
    directory = path.parent
    if directory.is_symlink():
        raise ValueError(f"refusing symlinked link journal directory: {directory}")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix=".pending-", dir=directory)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(payload, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        dir_fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def pending_links(ownership: Path) -> tuple[PendingLink, ...]:
    directory = _directory(ownership)
    if directory.is_symlink():
        raise ValueError(f"refusing symlinked link journal directory: {directory}")
    if not directory.exists():
        return ()
    pending = []
    for file in sorted(directory.iterdir()):
        if not file.is_file() or file.is_symlink():
            raise ValueError(f"unrecognized link journal entry: {file}")
        data = json.loads(file.read_text())
        if not isinstance(data, dict) or set(data) != {"path", "target", "stage", "text", "device", "inode"}:
            raise ValueError(f"invalid link journal: {file}")
        path, target, stage, text, device, inode = (data[k] for k in ("path", "target", "stage", "text", "device", "inode"))
        if not isinstance(path, str) or not isinstance(target, str) or not isinstance(stage, str) or not isinstance(text, str) or not isinstance(device, int) or not isinstance(inode, int):
            raise ValueError(f"invalid link journal fields: {file}")
        dest, home = Path(path), Path(target)
        if (not dest.is_absolute() or not home.is_absolute() or not dest.is_relative_to(home)
            or ".." in dest.parts or ".." in home.parts or device < 0 or inode < 0
            or re.fullmatch(r"\.sync-link-[0-9a-f]{32}", stage) is None
            or file != _path_for(ownership, dest)):
            raise ValueError(f"unsafe link journal: {file}")
        pending.append(PendingLink(dest, home, stage, text, device, inode, file))
    return tuple(pending)


def pending_paths(ownership: Path) -> tuple[Path, ...]:
    return tuple(item.path for item in pending_links(ownership))


def stage_link(ownership: Path, home: Path, path: Path, text: str, fd: int) -> PendingLink:
    # The journal is saved *after* stage creation and *before* destination
    # creation. A crash before the journal leaves only a safe temp symlink.
    if _path_for(ownership, path).exists():
        raise ValueError(f"link already has a pending transaction: {path}")
    stage = ".sync-link-" + uuid4().hex
    os.symlink(text, stage, dir_fd=fd)
    try:
        meta = os.stat(stage, dir_fd=fd, follow_symlinks=False)
        if not stat.S_ISLNK(meta.st_mode):
            raise ValueError("staged object is not a symlink")
        entry = PendingLink(path, home, stage, text, meta.st_dev, meta.st_ino, _path_for(ownership, path))
        _write_record(entry.journal, {
            "path": str(path), "target": str(home), "stage": stage, "text": text,
            "device": meta.st_dev, "inode": meta.st_ino,
        })
        return entry
    except BaseException:
        os.unlink(stage, dir_fd=fd)
        raise


def finish(entry: PendingLink, fd: int) -> None:
    st = os.stat(entry.stage, dir_fd=fd, follow_symlinks=False)
    if not stat.S_ISLNK(st.st_mode) or (st.st_dev, st.st_ino) != (entry.device, entry.inode):
        raise ValueError(f"pending link stage changed: {entry.path}")
    os.unlink(entry.stage, dir_fd=fd)
    entry.journal.unlink()
    try:
        entry.journal.parent.rmdir()
    except OSError:
        pass
