"""Validation and extraction of the ffmpeg-build shared runtime archive.

The archive holds the ffmpeg and ffprobe programs plus their libav shared
libraries. Symlinks are allowed only as the library version links directly in
lib/, each naming a sibling that resolves to a regular file.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import tarfile

LIBRARIES = ("libavcodec", "libavdevice", "libavfilter", "libavformat", "libavutil", "libswresample", "libswscale")
PROGRAMS = ("ffmpeg", "ffprobe")
MANIFEST = "share/ffmpeg-build/manifest.json"
MAX_EXTRACTED_BYTES = 1 << 30
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class RuntimeArchiveError(Exception):
    pass


def identity_key(os_name: str) -> str:
    return "install_name" if os_name == "darwin" else "soname"


def identity_name(library: str, major: int, os_name: str) -> str:
    return f"@rpath/{library}.{major}.dylib" if os_name == "darwin" else f"{library}.so.{major}"


def link_names(library: str, major: int, os_name: str) -> list[str]:
    if os_name == "darwin":
        return [f"{library}.{major}.dylib", f"{library}.dylib"]
    return [f"{library}.so.{major}", f"{library}.so"]


def versioned_file_pattern(library: str, os_name: str) -> re.Pattern[str]:
    if os_name == "darwin":
        return re.compile(rf"^lib/{library}\.(\d+)(?:\.\d+)*\.dylib$")
    return re.compile(rf"^lib/{library}\.so\.(\d+)(?:\.\d+)*$")


def plan_members(members: list[tarfile.TarInfo], top: str) -> None:
    by_name: dict[str, tarfile.TarInfo] = {}
    total = 0
    for member in members:
        name = member.name
        parts = name.split("/")
        if name.startswith("/") or "\0" in name or any(part in ("", ".", "..") for part in parts):
            raise RuntimeArchiveError(f"invalid member path {name!r}")
        if parts[0] != top:
            raise RuntimeArchiveError(f"member {name!r} is outside {top}/")
        if name in by_name:
            raise RuntimeArchiveError(f"duplicate member {name!r}")
        if not (member.isreg() or member.isdir() or member.issym()):
            raise RuntimeArchiveError(f"member {name!r} is neither a file, a directory, nor a symlink")
        if member.isreg():
            total += member.size
        by_name[name] = member
    if total > MAX_EXTRACTED_BYTES:
        raise RuntimeArchiveError("archive expands beyond the size limit")
    if top not in by_name and not any(name.startswith(top + "/") for name in by_name):
        raise RuntimeArchiveError(f"archive has no {top}/ directory")
    for name in by_name:
        parts = name.split("/")
        for depth in range(1, len(parts)):
            ancestor = by_name.get("/".join(parts[:depth]))
            if ancestor is not None and not ancestor.isdir():
                raise RuntimeArchiveError(f"member {name!r} lies below non-directory {ancestor.name!r}")
    for member in by_name.values():
        if member.issym():
            _check_link(member, top, by_name)


def _check_link(member: tarfile.TarInfo, top: str, by_name: dict[str, tarfile.TarInfo]) -> None:
    relative = member.name[len(top) + 1:]
    parts = relative.split("/")
    if len(parts) != 2 or parts[0] != "lib":
        raise RuntimeArchiveError(f"symlink {member.name!r} is not directly in lib/")
    seen = {member.name}
    current = member
    while current.issym():
        target = current.linkname
        if not target or target in (".", "..") or "/" in target or "\0" in target:
            raise RuntimeArchiveError(f"symlink {current.name!r} target {target!r} is not a sibling filename")
        resolved = f"{top}/lib/{target}"
        if resolved in seen:
            raise RuntimeArchiveError(f"symlink {member.name!r} is cyclic")
        seen.add(resolved)
        nxt = by_name.get(resolved)
        if nxt is None:
            raise RuntimeArchiveError(f"symlink {current.name!r} is dangling")
        current = nxt
    if not current.isreg():
        raise RuntimeArchiveError(f"symlink {member.name!r} does not resolve to a regular file")


def extract(archive_path: Path, top: str, target: Path) -> None:
    try:
        with tarfile.open(archive_path, "r:*") as archive:
            members = archive.getmembers()
            plan_members(members, top)
            links: list[tuple[Path, str]] = []
            for member in members:
                if member.name == top:
                    continue
                destination = target / member.name[len(top) + 1:]
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                elif member.issym():
                    links.append((destination, member.linkname))
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    executable = bool(member.mode & 0o111)
                    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                         0o755 if executable else 0o644)
                    with os.fdopen(descriptor, "wb") as out:
                        source = archive.extractfile(member)
                        if source is None:
                            raise RuntimeArchiveError(f"cannot read member {member.name!r}")
                        shutil.copyfileobj(source, out)
                    destination.chmod(0o755 if executable else 0o644)
            for destination, linkname in links:
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(linkname, destination)
    except (tarfile.TarError, OSError) as exc:
        raise RuntimeArchiveError(f"cannot extract: {exc}") from exc


def elf_soname(path: Path) -> str:
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise RuntimeArchiveError(f"{path.name} is not a little-endian ELF64 file")
    phoff, = struct.unpack_from("<Q", data, 0x20)
    phentsize, phnum = struct.unpack_from("<HH", data, 0x36)
    loads: list[tuple[int, int, int]] = []
    dynamic: tuple[int, int] | None = None
    for index in range(phnum):
        p_type, _, offset, vaddr, _, filesz, _, _ = struct.unpack_from("<IIQQQQQQ", data, phoff + index * phentsize)
        if p_type == 1:
            loads.append((vaddr, offset, filesz))
        elif p_type == 2:
            dynamic = (int(offset), int(filesz))
    if dynamic is None:
        raise RuntimeArchiveError(f"{path.name} has no dynamic section")
    strtab = soname_offset = None
    start, size = dynamic
    for position in range(start, start + size, 16):
        tag, value = struct.unpack_from("<qQ", data, position)
        if tag == 0:
            break
        if tag == 5:
            strtab = value
        elif tag == 14:
            soname_offset = value
    if strtab is None or soname_offset is None:
        raise RuntimeArchiveError(f"{path.name} has no SONAME")
    for vaddr, offset, filesz in loads:
        if vaddr <= strtab < vaddr + filesz:
            begin = offset + (strtab - vaddr) + soname_offset
            return data[begin:data.index(b"\0", begin)].decode()
    raise RuntimeArchiveError(f"{path.name} has an unmapped string table")


def macho_install_name(path: Path) -> str:
    data = path.read_bytes()
    if len(data) < 32 or struct.unpack_from("<I", data, 0)[0] != 0xFEEDFACF:
        raise RuntimeArchiveError(f"{path.name} is not a 64-bit little-endian Mach-O file")
    ncmds, = struct.unpack_from("<I", data, 16)
    position = 32
    for _ in range(ncmds):
        command, size = struct.unpack_from("<II", data, position)
        if command == 0xD:
            name_offset, = struct.unpack_from("<I", data, position + 8)
            begin = position + name_offset
            return data[begin:data.index(b"\0", begin)].decode()
        position += size
    raise RuntimeArchiveError(f"{path.name} has no install name")


def library_identity(path: Path, os_name: str) -> str:
    return macho_install_name(path) if os_name == "darwin" else elf_soname(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1 << 20), b""):
            digest.update(part)
    return digest.hexdigest()


def _regular(root: Path, relative: str) -> Path:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise RuntimeArchiveError(f"{relative} is missing or not a regular file")
    return path


def verified_libraries(root: Path, os_name: str) -> dict[str, Path]:
    """Check the installed tree against its manifest; return library name to real file."""
    try:
        manifest = json.loads(_regular(root, MANIFEST).read_text())
    except ValueError as exc:
        raise RuntimeArchiveError(f"{MANIFEST} is not valid JSON") from exc
    libraries = manifest.get("libraries") if isinstance(manifest, dict) else None
    if not isinstance(libraries, dict) or set(libraries) != set(LIBRARIES):
        raise RuntimeArchiveError(f"{MANIFEST} libraries must be exactly {', '.join(LIBRARIES)}")
    key = identity_key(os_name)
    files: dict[str, Path] = {}
    for library in LIBRARIES:
        entry = libraries[library]
        if not isinstance(entry, dict) or set(entry) != {"file", "links", key, "sha256"}:
            raise RuntimeArchiveError(f"{library}: manifest entry must have file, links, {key}, and sha256")
        file, links, identity, sha256 = entry["file"], entry["links"], entry[key], entry["sha256"]
        match = versioned_file_pattern(library, os_name).match(file) if isinstance(file, str) else None
        if match is None:
            raise RuntimeArchiveError(f"{library}: {file!r} is not a versioned library file in lib/")
        major = int(match.group(1))
        if identity != identity_name(library, major, os_name):
            raise RuntimeArchiveError(f"{library}: manifest {key} {identity!r} does not match its major version")
        want_links = sorted(f"lib/{name}" for name in link_names(library, major, os_name))
        if not isinstance(links, list) or sorted(map(str, links)) != want_links:
            raise RuntimeArchiveError(f"{library}: manifest links must be {want_links}")
        if not isinstance(sha256, str) or not SHA256.match(sha256):
            raise RuntimeArchiveError(f"{library}: manifest sha256 is malformed")
        path = _regular(root, file)
        actual = library_identity(path, os_name)
        if actual != identity:
            raise RuntimeArchiveError(f"{library}: library reports {key} {actual!r}, expected {identity!r}")
        if sha256_file(path) != sha256:
            raise RuntimeArchiveError(f"{library}: sha256 does not match the manifest")
        for link in links:
            link_path = root / link
            if not link_path.is_symlink() or os.readlink(link_path) != Path(file).name \
                    or not link_path.resolve().samefile(path):
                raise RuntimeArchiveError(f"{library}: {link} is not a symlink to {Path(file).name}")
        files[library] = path
    return files


def check_identity(root: Path, *, target: str, version: str, commit: str, archive: str) -> None:
    try:
        manifest = json.loads(_regular(root, MANIFEST).read_text())
    except ValueError as exc:
        raise RuntimeArchiveError(f"{MANIFEST} is not valid JSON") from exc
    want = {("profile",): "runtime", ("target",): target, ("sources", "ffmpeg", "version"): version,
            ("producer", "commit"): commit, ("release", "archive"): archive}
    for keys, value in want.items():
        found = manifest
        for key in keys:
            found = found.get(key) if isinstance(found, dict) else None
        if found != value:
            raise RuntimeArchiveError(f"{MANIFEST} {'.'.join(keys)} is {found!r}, expected {value!r}")


def verified_programs(root: Path) -> list[Path]:
    programs = []
    for name in PROGRAMS:
        path = _regular(root, f"bin/{name}")
        if not os.access(path, os.X_OK):
            raise RuntimeArchiveError(f"bin/{name} is not executable")
        programs.append(path)
    return programs
