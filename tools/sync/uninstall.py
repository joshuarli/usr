"""Conservative uninstall of provenance-verified managed objects."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from ownership import fingerprint, manifest_path, read_manifest, records, ownership_lock

if TYPE_CHECKING:
    from main import Context


def uninstall(ctx: Context) -> None:
    with ownership_lock(ctx.state):
        _uninstall_locked(ctx)


def _uninstall_locked(ctx: Context) -> None:
    from main import BRIDGE, PI_BRIDGE, command, required

    owner = ctx.state
    entries = read_manifest(owner)
    inventory = sorted(records(owner), key=lambda x: (x[0], str(x[1])))
    for kind, path in inventory:
        if kind == "K":
            from main import kache_install_path
            if path != kache_install_path(ctx):
                raise RuntimeError(f"unrecognized kache ownership path: {path}")
        allowed = path.is_absolute() and (
            path.is_relative_to(ctx.home) or path.is_relative_to(Path("/Applications"))
        )
        if not allowed or ".." in path.parts:
            raise RuntimeError(f"unsafe recorded uninstall path: {path}")
        parent = path.parent.resolve()
        if not (parent.is_relative_to(ctx.home.resolve()) or parent.is_relative_to(Path("/Applications"))):
            raise RuntimeError(f"recorded uninstall path escapes its owner: {path}")
        identity = fingerprint(path, kind) if kind != "E" else None
        if identity is None:
            continue
        proof = entries.get(str(path))
        if proof != {"kind": kind, "fingerprint": identity}:
            raise RuntimeError(f"unverified or modified managed path: {path}; preserving all files")

    # Preflight every managed object before the first destructive operation.
    required(command(ctx, os.sys.executable, "-I", str(BRIDGE), "remove"), "Claude MCP removal")
    required(command(ctx, os.sys.executable, "-I", str(PI_BRIDGE), "remove"), "Pi MCP removal")
    removed_directories: list[Path] = []
    directories = sorted((path for kind, path in inventory if kind == "D"), key=lambda p: len(p.parts))
    for path in directories:
        if any(path.is_relative_to(parent) for parent in removed_directories):
            continue
        if path.is_dir() and not path.is_symlink():
            if entries.get(str(path)) != {"kind": "D", "fingerprint": fingerprint(path, "D")}:
                raise RuntimeError(f"changed during uninstall: {path}")
            shutil.rmtree(path)
            removed_directories.append(path)
    for kind, path in inventory:
        if any(path.is_relative_to(parent) for parent in removed_directories):
            continue
        if kind in ("F", "K") and fingerprint(path, kind) is not None:
            if entries.get(str(path)) != {"kind": kind, "fingerprint": fingerprint(path, kind)}:
                raise RuntimeError(f"changed during uninstall: {path}")
            if kind == "F":
                path.unlink()
            else:
                required(command(ctx, "sh", str(ctx.root / "dotfiles/base/.local/bin/setup-kache"),
                                 "uninstall", "--purge"), "kache uninstall")
    for kind, path in sorted(inventory, key=lambda x: len(x[1].parts), reverse=True):
        if kind == "E" and path.is_dir() and not path.is_symlink():
            try:
                path.rmdir()
            except OSError:
                pass
    owner.unlink(missing_ok=True)
    manifest_path(owner).unlink(missing_ok=True)
