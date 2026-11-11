#!/usr/bin/env python3
"""Audit or refresh selected upstream Pi source snapshots; never install packages."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "vendor/pi/upstreams.json"
EXCLUDE = re.compile(r"(\.test\.|^test/|^\.github/|package-lock\.json|\.png$|\.jpg$|\.webp$|\.gitignore$)")
SUBAGENTS = re.compile(r"^(src/|agents/|docs/|skills/|prompts/|index\.ts$|.*\.mjs$|.*\.cjs$|package\.json$|LICENSE$|README\.md$)")
OTHER = re.compile(r"^(src/|broker/|ui/|provider/|skills/|index\.ts$|.*\.ts$|.*\.mjs$|.*\.cjs$|package\.json$|LICENSE$|README\.md$|COPYRIGHT$|LICENSE_TRANSITION\.md$|THIRD_PARTY_NOTICES\.md$|tsconfig(?:\.build)?\.json$)")
SHA = re.compile(r"[0-9a-f]{40}")
SUPPORTED = {"pi-subagents", "agent-intercom-pi", "agent-intercom-core", "pi-muse-subscription"}


def source_files(folder: Path, name: str) -> list[Path]:
    pattern = SUBAGENTS if name == "pi-subagents" else OTHER
    result = []
    for path in folder.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symlink in upstream snapshot: {path}")
        if path.is_file():
            relative = path.relative_to(folder).as_posix()
            if not EXCLUDE.search(relative) and pattern.search(relative):
                result.append(path)
    return sorted(result)


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}".encode() + bytes([0]) + data).hexdigest()


def load() -> dict:
    data = json.loads(MANIFEST.read_text())
    if data.get("schema") != 1 or set(data.get("sources", {})) != SUPPORTED:
        raise ValueError("unsupported or incomplete Pi vendor manifest")
    for name, src in data["sources"].items():
        if src["path"] != f"vendor/pi/{name}" or not SHA.fullmatch(src["sha"]):
            raise ValueError(f"invalid identity for {name}")
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", src["repository"]):
            raise ValueError(f"invalid upstream repository for {name}")
        if not isinstance(src["files"], dict) or not src["files"]:
            raise ValueError(f"empty source inventory for {name}")
        if any(not SHA.fullmatch(sha) for sha in src["files"].values()):
            raise ValueError(f"invalid upstream file hashes for {name}")
    return data


def check(data: dict) -> None:
    for name, src in data["sources"].items():
        folder = ROOT / src["path"]
        if not folder.is_dir():
            raise ValueError(f"missing source directory: {folder}")
        expected = src["files"]
        actual = {p.relative_to(folder).as_posix(): git_blob_sha(p.read_bytes())
                  for p in source_files(folder, name)}
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        modified = sorted(k for k in actual.keys() & expected.keys() if actual[k] != expected[k])
        if missing or extra or modified:
            raise ValueError(f"{name}: missing={missing[:8]}, extra={extra[:8]}, changed={modified[:8]}")
        print(f"ok: {name} {len(actual)} files upstream={src['sha']}")


def command(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode:
        raise ValueError(f"{' '.join(args[:3])} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def plan(data: dict) -> None:
    for name, src in data["sources"].items():
        remote = f"https://github.com/{src['repository']}.git"
        current = command("git", "ls-remote", remote, "refs/heads/main")
        new_sha = current.split()[0] if current else "(missing branch)"
        print(f"{name:24s} {src['sha']} -> {new_sha}")
    print("Pi CLI/SDK remain track-only; rebuild and vendor the full executable/dependency closure before activation.")


def update(data: dict, refs: dict[str, str]) -> None:
    # This operation updates source *only*. It does not activate a runtime.
    state = command("git", "status", "--porcelain", "--", "vendor/pi", cwd=ROOT)
    if state:
        raise ValueError("vendor/pi has uncommitted changes; refusing to overwrite them")
    staged = copy.deepcopy(data)
    with tempfile.TemporaryDirectory(prefix=".pi-update-", dir=ROOT / "vendor/pi") as temp:
        temp_root = Path(temp)
        for name, src in staged["sources"].items():
            remote = f"https://github.com/{src['repository']}.git"
            ref = refs.get(name, "main")
            if not re.fullmatch(r"[A-Za-z0-9._/-]+", ref) or ref.startswith("-") or ".." in ref:
                raise ValueError(f"unsafe ref: {ref}")
            checkout = temp_root / f"{name}-checkout"
            command("git", "clone", "--quiet", "--depth=1", "--filter=blob:none",
                    "--branch", ref, remote, str(checkout))
            upstream_sha = command("git", "rev-parse", "HEAD", cwd=checkout)
            if not SHA.fullmatch(upstream_sha):
                raise ValueError(f"invalid upstream revision for {name}")
            output = temp_root / f"{name}-new"
            output.mkdir()
            sources = source_files(checkout, name)
            if not sources:
                raise ValueError(f"no source files for {name}")
            hashes = {}
            for file in sources:
                relative = file.relative_to(checkout)
                target = output / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, target)
                hashes[relative.as_posix()] = git_blob_sha(file.read_bytes())
            package = json.loads((output / "package.json").read_text())
            src.update(sha=upstream_sha, ref=ref, version=package["version"],
                       files=dict(sorted(hashes.items())))
        # Do not partially replace sources if fetching or inspecting any source failed.
        swapped = []
        try:
            for name, src in staged["sources"].items():
                destination = ROOT / src["path"]
                backup = temp_root / f"{name}-previous"
                os.replace(destination, backup)
                try:
                    os.replace(temp_root / f"{name}-new", destination)
                except OSError:
                    os.replace(backup, destination)
                    raise
                swapped.append((destination, backup))
            proposed = MANIFEST.with_suffix(".json.tmp")
            try:
                proposed.write_text(json.dumps(staged, indent=2) + "\n")
                os.replace(proposed, MANIFEST)
            finally:
                proposed.unlink(missing_ok=True)
        except Exception:
            for destination, backup in reversed(swapped):
                shutil.rmtree(destination)
                os.replace(backup, destination)
            raise
    check(staged)
    print("Source snapshots refreshed. NOT a runtime/SDK update; run /pi-update gates before integration.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "plan", "update"])
    parser.add_argument("--ref", action="append", default=[], metavar="NAME=REF",
                        help="Select a compatible upstream branch/tag for a source (update only)")
    args = parser.parse_args()
    refs = {}
    for assignment in args.ref:
        name, sep, ref = assignment.partition("=")
        if not sep or name not in SUPPORTED or not ref or name in refs:
            parser.error(f"invalid or duplicate --ref: {assignment}")
        refs[name] = ref
    try:
        data = load()
        if args.action == "check":
            if refs:
                parser.error("--ref is only valid with update")
            check(data)
        elif args.action == "plan":
            if refs:
                parser.error("--ref is only valid with update")
            plan(data)
        else:
            check(data)
            update(data, refs)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"pi-vendor: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
