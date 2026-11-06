"""Compatibility migration for installations recorded by the former shell installer."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import Context


def uninstall(ctx: Context) -> None:
    from main import BRIDGE, command, required

    required(command(ctx, os.sys.executable, "-I", str(BRIDGE), "remove"),
             "Claude MCP removal")
    ctx.state.parent.mkdir(parents=True, exist_ok=True)
    required(command(ctx, "sh", str(ctx.root / "tools/sync/install.sh"),
                     extra={"DL_OWNED_FILE": str(ctx.state), "DL_RECORD_OWNED": "true"}),
             "managed install inventory")
    if not ctx.state.exists():
        return
    paths: list[tuple[str, Path]] = []
    for record in ctx.state.read_text().splitlines():
        kind, separator, value = record.partition("\t")
        if separator and kind in ("F", "D", "E", "K") and value:
            path = Path(value)
            allowed = path.is_absolute() and (
                path.is_relative_to(ctx.home) or
                path.is_relative_to(Path("/Applications"))
            )
            if not allowed or any(part == ".." for part in path.parts):
                raise RuntimeError(f"unsafe recorded uninstall path: {value}")
            home_real = ctx.home.resolve()
            parent_real = path.parent.resolve()
            if not (parent_real.is_relative_to(home_real) or parent_real.is_relative_to(Path("/Applications"))):
                raise RuntimeError(f"recorded uninstall path escapes its owner: {value}")
            paths.append((kind, path))
    for kind, path in paths:
        if kind == "F" and (path.is_symlink() or path.is_file()):
            path.unlink()
    for kind, path in paths:
        if kind == "D" and path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
    for kind, path in reversed(paths):
        if kind == "E":
            try:
                path.rmdir()
            except OSError:
                pass
    for kind, path in paths:
        if kind == "K" and path.exists():
            required(command(ctx, "sh", str(ctx.root / "dotfiles/base/.local/bin/setup-kache"),
                             "uninstall", "--purge"), "kache uninstall")
    ctx.state.unlink(missing_ok=True)
