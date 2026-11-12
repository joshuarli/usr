"""Apply a validated link plan with no-overwrite syscalls and durable ownership.

The planner is authoritative for what to change. The applier rechecks every
precondition before writing, and uses dirfd operations to avoid following
newly replaced symlinked parents outside the target home.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile

from link_plan import LinkPlan, Snapshot, snapshot
from ownership import fingerprint, manifest_path, read_manifest, records
from link_recovery import finish, pending_links, stage_link


class LinkApplyError(RuntimeError):
    """A filesystem precondition changed or an unsafe mutation was refused."""


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise LinkApplyError(f"ownership state is a symlink: {path}")
    fd, temporary = tempfile.mkstemp(prefix=".sync-ownership-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        dir_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)


class Ownership:
    def __init__(self, path: Path):
        if path.is_symlink():
            raise LinkApplyError(f"ownership records are symlinked: {path}")
        self.path = path
        self.entries = records(path)
        self.proofs = read_manifest(path)

    def add(self, kind: str, path: Path) -> None:
        self.entries.add((kind, path))
        self._save_records()
        if kind == "F":
            identity = fingerprint(path, kind)
            if identity is None:
                raise LinkApplyError(f"cannot fingerprint linked path: {path}")
            self.proofs[str(path)] = {"kind": kind, "fingerprint": identity}
            self._save_proofs()

    def remove(self, kind: str, path: Path) -> None:
        self.entries.discard((kind, path))
        self._save_records()
        if kind == "F" and str(path) in self.proofs:
            del self.proofs[str(path)]
            self._save_proofs()

    def _save_records(self) -> None:
        payload = "".join(f"{kind}\t{path}\n" for kind, path in sorted(self.entries, key=lambda e: (e[0], str(e[1]))))
        _atomic_bytes(self.path, payload.encode())

    def _save_proofs(self) -> None:
        path = manifest_path(self.path)
        payload = json.dumps({"schema": 1, "entries": self.proofs}, sort_keys=True) + "\n"
        _atomic_bytes(path, payload.encode())


def _observed(fd: int, name: str) -> Snapshot:
    try:
        st = os.stat(name, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        return Snapshot("absent")
    kind = ("symlink" if stat.S_ISLNK(st.st_mode) else "directory" if stat.S_ISDIR(st.st_mode)
            else "file" if stat.S_ISREG(st.st_mode) else "special")
    text = os.readlink(name, dir_fd=fd) if kind == "symlink" else None
    return Snapshot(kind, (st.st_dev, st.st_ino, st.st_mode, st.st_mtime_ns), text)


def _directory_fd(target: Path, parent: Path, owner: Ownership) -> int:
    if not parent.is_relative_to(target):
        raise LinkApplyError(f"path outside managed home: {parent}")
    resolved = parent.resolve(strict=False)
    if not resolved.is_relative_to(target):
        raise LinkApplyError(f"parent escapes home through symlink: {parent}")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(target, flags)
    try:
        current = target
        for component in resolved.relative_to(target).parts:
            current = current / component
            created = False
            try:
                os.mkdir(component, dir_fd=fd)
                created = True
            except FileExistsError:
                pass
            next_fd = os.open(component, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
            if created:
                owner.add("E", current)
        if parent.resolve(strict=False) != resolved:
            raise LinkApplyError(f"parent changed while planning: {parent}")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _recover_pending(plan: LinkPlan, owner: Ownership, owned_file: Path) -> list[str]:
    results = []
    for entry in pending_links(owned_file):
        if entry.target != plan.target:
            raise LinkApplyError(f"pending link targets a different home: {entry.path}")
        fd = _directory_fd(plan.target, entry.path.parent, owner)
        try:
            stage = _observed(fd, entry.stage)
            if stage.kind == "absent":
                current = _observed(fd, entry.path.name)
                if (current.kind != "symlink" or current.identity is None or
                    current.identity[:2] != (entry.device, entry.inode) or current.text != entry.text):
                    raise LinkApplyError(f"pending link destination changed: {entry.path}")
            elif (stage.kind != "symlink" or stage.identity is None or
                  stage.identity[:2] != (entry.device, entry.inode) or stage.text != entry.text):
                raise LinkApplyError(f"pending link stage changed: {entry.path}")
            current = _observed(fd, entry.path.name)
            if current.kind == "absent":
                os.link(entry.stage, entry.path.name, src_dir_fd=fd, dst_dir_fd=fd,
                        follow_symlinks=False)
            elif (current.kind != "symlink" or current.identity is None or
                  current.identity[:2] != (entry.device, entry.inode) or current.text != entry.text):
                raise LinkApplyError(f"pending link destination changed: {entry.path}")
            owner.add("F", entry.path)
            finish(entry, fd)
            results.append(f"RECOVER: {entry.path}")
        finally:
            os.close(fd)
    return results


def apply(plan: LinkPlan, owned_file: Path) -> list[str]:
    if plan.conflicts:
        raise LinkApplyError("link conflicts:\n" + "\n".join(plan.conflicts))
    # Check the complete plan before the first filesystem mutation.
    for action in plan.actions:
        if snapshot(action.path) != action.before:
            raise LinkApplyError(f"link changed since planning: {action.path}")
        if not action.path.parent.resolve(strict=False).is_relative_to(plan.target):
            raise LinkApplyError(f"link parent escaped the home: {action.path}")
    if not plan.actions and not plan.pending:
        return []
    owner = Ownership(owned_file)
    performed: list[str] = _recover_pending(plan, owner, owned_file)
    for action in plan.actions:
        if action.kind == "forget":
            if snapshot(action.path) != action.before:
                raise LinkApplyError(f"stale record's destination changed: {action.path}")
            owner.remove("F", action.path)
            performed.append(f"FORGET: {action.path}")
            continue
        # Resolving only the parent permits link targets that are themselves
        # symlinks, and disallows writes through an escaping parent symlink.
        fd = _directory_fd(plan.target, action.path.parent, owner)
        try:
            observed = _observed(fd, action.path.name)
            if observed != action.before:
                raise LinkApplyError(f"link changed since planning: {action.path}")
            if action.kind == "prune":
                if observed.kind != "symlink":
                    raise LinkApplyError(f"refusing to remove non-symlink: {action.path}")
                os.unlink(action.path.name, dir_fd=fd)
                owner.remove("F", action.path)
                performed.append(f"PRUNE: {action.path}")
                continue
            if action.desired_text is None:
                raise LinkApplyError(f"missing declared link target: {action.path}")
            # Make the exact symlink inode recoverable before touching the
            # destination. A staged symlink hardlink is an O_EXCL creation,
            # so a foreign file is never overwritten during recovery.
            entry = stage_link(owned_file, plan.target, action.path, action.desired_text, fd)
            if action.kind == "replace":
                if observed.kind != "symlink":
                    raise LinkApplyError(f"refusing to replace non-symlink: {action.path}")
                os.unlink(action.path.name, dir_fd=fd)
            os.link(entry.stage, action.path.name, src_dir_fd=fd, dst_dir_fd=fd,
                    follow_symlinks=False)
            owner.add("F", action.path)
            finish(entry, fd)
            performed.append(f"LINK: {action.path} -> {action.desired_text}")
        finally:
            os.close(fd)
    return performed
