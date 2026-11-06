"""Pure-ish reconcile planning: inspect live state, never mutate the target."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Literal

from links import Discovery, LinkSpec
from ownership import fingerprint, read_manifest, records


@dataclass(frozen=True)
class Snapshot:
    kind: Literal["absent", "symlink", "file", "directory", "special"]
    identity: tuple[int, int, int, int] | None = None
    text: str | None = None


def snapshot(path: Path) -> Snapshot:
    try:
        st = path.lstat()
    except FileNotFoundError:
        return Snapshot("absent")
    kind = ("symlink" if path.is_symlink() else "directory" if path.is_dir()
            else "file" if path.is_file() else "special")
    text = os.readlink(path) if kind == "symlink" else None
    return Snapshot(kind, (st.st_dev, st.st_ino, st.st_mode, st.st_mtime_ns), text)


@dataclass(frozen=True)
class LinkAction:
    kind: Literal["link", "replace", "prune", "forget"]
    path: Path
    before: Snapshot
    desired_text: str | None = None


@dataclass(frozen=True)
class LinkPlan:
    target: Path
    actions: tuple[LinkAction, ...]
    conflicts: tuple[str, ...]
    current: int

    @property
    def converged(self) -> bool:
        return not self.actions and not self.conflicts

    def lines(self) -> list[str]:
        lines = [f"CONFLICT: {reason}" for reason in self.conflicts]
        for action in self.actions:
            if action.kind == "prune":
                lines.append(f"PRUNE: {action.path}")
            elif action.kind == "forget":
                lines.append(f"FORGET: {action.path} (absent owned record)")
            else:
                lines.append(f"LINK: {action.path} -> {action.desired_text}")
        return lines


def _inside(path: Path, directory: Path) -> bool:
    return path == directory or path.is_relative_to(directory)


def _parent_safe(path: Path, discovery: Discovery) -> bool:
    # Resolve existing ancestors, including symlink redirects. The output
    # directory must stay beneath the *physical* home and outside sources.
    real = path.parent.resolve(strict=False)
    return _inside(real, discovery.target) and not any(
        _inside(real, source) for source in discovery.sources
    )


def _desired_text(spec: LinkSpec, path: Path) -> str:
    if not spec.directory and spec.source.is_symlink():
        source_text = os.readlink(spec.source)
        if not os.path.isabs(source_text):
            return source_text
        return os.path.relpath(source_text, path.parent)
    return os.path.relpath(spec.source, path.parent)


def _source_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _old_managed_link(path: Path, sources: tuple[Path, ...], rel: Path) -> bool:
    if not path.is_symlink():
        return False
    raw = os.readlink(path)
    pointed = Path(os.path.normpath(os.path.join(path.parent, raw)))
    # Check the *lexical* old source path, not resolve(): a deleted source
    # is precisely the condition we are trying to detect.
    return any(pointed == source / rel and not _source_exists(source / rel)
               for source in sources)


def _already_correct(spec: LinkSpec, path: Path, text: str,
                     planned_symlink_dirs: set[Path]) -> bool:
    if not path.is_symlink():
        return False
    if _source_exists(spec.source):
        try:
            if path.samefile(spec.source):
                return True
        except OSError:
            pass
    if spec.directory:
        return False
    if os.readlink(path) != text:
        return False
    if path.exists():
        return True
    # An existing dangling link can become valid when another declared
    # whole-directory link is installed in this same global plan.
    pointed = Path(os.path.normpath(os.path.join(path.parent, text)))
    return pointed in planned_symlink_dirs


def plan_links(discovery: Discovery, owned_file: Path) -> LinkPlan:
    desired = {discovery.target / spec.relative.as_posix(): spec for spec in discovery.desired}
    previous = records(owned_file)
    # A historical path claim does not authorize deleting a currently different
    # link. Use the verified *live* identity before planning prune/replacement.
    proofs = read_manifest(owned_file)
    owned_records = {path for kind, path in previous
                     if kind == "F" and _inside(path, discovery.target)}
    owned_links = {
        path for path in owned_records
        if path.is_symlink()
        and proofs.get(str(path)) == {"kind": "F", "fingerprint": fingerprint(path, "F")}
    }
    actions: list[LinkAction] = []
    conflicts: list[str] = []
    correct = 0
    projected_dirs = {discovery.target / s.relative.as_posix() for s in discovery.desired if s.directory}
    # Extra check for a symlink directory ancestor not covered by desired links.
    for path, spec in desired.items():
        if not _parent_safe(path, discovery):
            conflicts.append(f"{path} passes through an unsafe symlinked parent")
            continue
        before = snapshot(path)
        text = _desired_text(spec, path)
        if before.kind == "absent":
            actions.append(LinkAction("link", path, before, text))
        elif before.kind == "symlink" and _already_correct(spec, path, text, projected_dirs):
            correct += 1
        elif before.kind == "symlink" and path in owned_links and _old_managed_link(
            path, discovery.sources, path.relative_to(discovery.target)
        ):
            actions.append(LinkAction("replace", path, before, text))
        else:
            conflicts.append(f"{path} already exists and is not the declared link")

    for path in sorted(owned_records - desired.keys(), key=str):
        before = snapshot(path)
        if before.kind == "absent":
            actions.append(LinkAction("forget", path, before))
        elif path in owned_links and before.kind == "symlink" and _old_managed_link(
            path, discovery.sources, path.relative_to(discovery.target)
        ):
            if not _parent_safe(path, discovery):
                conflicts.append(f"{path} passes through an unsafe symlinked parent")
            else:
                actions.append(LinkAction("prune", path, before))
        # An owned record pointing to a still-present source may belong to
        # another deliberately retained link. Do not treat it as stale.
    order = {"prune": 0, "forget": 1, "replace": 2, "link": 3}
    actions.sort(key=lambda a: (order[a.kind], str(a.path)))
    return LinkPlan(discovery.target, tuple(actions), tuple(sorted(set(conflicts))), correct)
