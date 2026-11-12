"""Discover declared dotfile links once, across all ordered layers.

Discovery observes Git's tracked and unignored files; .sym-dir selects a
whole-directory link. This module never touches the destination home.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import subprocess


class LinkError(ValueError):
    """Unsafe or ambiguous link declaration."""


@dataclass(frozen=True)
class LinkSpec:
    relative: PurePosixPath
    source: Path
    layer: Path
    directory: bool
    home_link_text: str | None = None


CODE_DECLARED_LINKS: tuple[tuple[PurePosixPath, PurePosixPath], ...] = (
    (PurePosixPath(".claude/skills"), PurePosixPath(".agents/skills")),
)


@dataclass(frozen=True)
class Discovery:
    target: Path
    sources: tuple[Path, ...]
    desired: tuple[LinkSpec, ...]


def _safe_relative(name: PurePosixPath) -> None:
    # Historical ownership records are tab-delimited. Reject tabs until the
    # migration to a length-delimited record format; no shell word splitting.
    if name.is_absolute() or not name.parts or any(
        part in ("", ".", "..") or any(ord(char) < 32 or 0xDC80 <= ord(char) <= 0xDCFF for char in part)
        for part in name.parts
    ):
        raise LinkError(f"unsafe source path {name!s}")


def _git_toplevel(root: Path) -> Path | None:
    top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True, check=False)
    return Path(top.stdout.strip()).resolve() if top.returncode == 0 else None


def _listing(root: Path, layer: Path) -> tuple[set[PurePosixPath], set[PurePosixPath]]:
    # Only the checkout's own index describes its layers. A root nested inside
    # another repository (or its ignored scratch) must not inherit that repository's view.
    git = subprocess.run(
        ["git", "-C", str(layer), "-c", "core.quotePath=false", "ls-files", "-z",
         "--cached", "--others", "--exclude-standard", "--", "."],
        capture_output=True, check=False,
    ) if _git_toplevel(root) == root.resolve() else None
    names: set[PurePosixPath] = set()
    if git is not None and git.returncode == 0:
        for raw in git.stdout.split(b"\0"):
            if not raw:
                continue
            relative = PurePosixPath(os.fsdecode(raw))
            _safe_relative(relative)
            names.add(relative)
    else:
        # Preserve sym's nongit fallback without following symlink directories.
        for root, dirs, files in os.walk(layer, followlinks=False):
            root_path = Path(root)
            for item in files + [d for d in dirs if (root_path / d).is_symlink()]:
                relative = PurePosixPath((root_path / item).relative_to(layer).as_posix())
                _safe_relative(relative)
                names.add(relative)
    markers = {relative.parent for relative in names if relative.name == ".sym-dir"}
    top: set[PurePosixPath] = set()
    for marker in sorted(markers, key=lambda p: (len(p.parts), p.as_posix())):
        if not any(marker == parent or parent in marker.parents for parent in top):
            top.add(marker)
    return names - {p for p in names if p.name == ".sym-dir"}, top


def discover(root: Path, target: Path, platform: str) -> Discovery:
    if not target.is_dir():
        raise LinkError(f"target directory does not exist: {target}")
    target_real = target.resolve(strict=True)
    if "\t" in str(target) or "\t" in str(target_real):
        raise LinkError("target directory contains a tab")
    specs: dict[PurePosixPath, LinkSpec] = {}
    sources: list[Path] = []
    for layer in (root / "dotfiles/base", root / "dotfiles" / platform):
        if not layer.is_dir():
            continue
        source_root = layer.resolve(strict=True)
        sources.append(source_root)
        names, markers = _listing(root, layer)
        for rel in sorted(markers, key=lambda p: p.as_posix()):
            if rel == PurePosixPath("."):
                raise LinkError("root .sym-dir would replace the target home")
            _safe_relative(rel)
            _add(specs, LinkSpec(rel, source_root / rel, source_root, True))
        for rel in sorted(names, key=lambda p: p.as_posix()):
            if any(marker == rel or marker in rel.parents for marker in markers):
                continue
            if not (layer / rel).is_file() and not (layer / rel).is_symlink():
                continue
            _safe_relative(rel)
            _add(specs, LinkSpec(rel, source_root / rel, source_root, False))
    for relative, home_target in CODE_DECLARED_LINKS:
        if relative in specs:
            raise LinkError(f"{relative} is declared in code; remove its file from {specs[relative].layer}")
        if target_spec := specs.get(home_target):
            text = os.path.relpath(home_target, relative.parent)
            specs[relative] = LinkSpec(relative, target_spec.source, target_spec.layer, False, text)
    keys = sorted(specs, key=lambda p: p.as_posix())
    for relative in keys:
        for parent in relative.parents:
            if parent in specs and specs[parent].directory:
                raise LinkError(f"overlapping link declarations: {parent} contains {relative}")
    return Discovery(target_real, tuple(sources), tuple(specs[key] for key in keys))


def _add(specs: dict[PurePosixPath, LinkSpec], spec: LinkSpec) -> None:
    if previous := specs.get(spec.relative):
        raise LinkError(f"duplicate link declaration {spec.relative}: {previous.layer} and {spec.layer}")
    specs[spec.relative] = spec
