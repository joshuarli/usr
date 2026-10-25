"""Approved-pin catalogs: offline resolution with strong safety invariants.

Accepted file: TOML (``tomllib`` when available, else a minimal subset
parser for ``[table]`` + ``key = "value"``) with one table per action:

.. code-block:: toml

   [actions.checkout]
   channel = "v4"
   version = "v4.2.2"
   sha = "11bd71901bbe5b1630ceea73d27597364c9af683"

Table names accept ``owner/repo`` with an optional ``actions.`` prefix
(repomod style). Required fields: ``channel`` (``vN``), ``version``
(``vN...`` with the same major), ``sha`` (40 hex). Validation refuses:
missing/invalid shape, major mismatch between channel and version,
ambiguous records for one repo, and unlabeled SHAs are never minted here.

Safety invariants (offline-first, never network):

- no silent major bump: a ``uses: repo@ref`` whose major differs from the
  catalog channel is left unchanged with a diagnostic;
- no silent downgrade: an already-pinned SHA that is not the catalog SHA
  is left unchanged (the catalog never proves the pinned commit is older);
- subpath preservation: ``owner/repo/sub/path@ref`` keeps ``/sub/path``;
- missing approval: repos absent from the catalog yield an
  ``unapproved-pin``-style diagnostic, never a guessed SHA;
- unlabeled SHA: a ``uses: repo@<sha>`` without a version comment is never
  rewritten from the catalog (a SHA is not proof of approval).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SHA = re.compile(r"[0-9a-fA-F]{40}\Z")
CHANNEL = re.compile(r"v\d+\Z")
VERSION = re.compile(r"v\d+[0-9A-Za-z._+-]*\Z")
NUMERIC_VERSION = re.compile(r"v(\d+)(?:\.(\d+))?(?:\.(\d+))?\Z")


class CatalogError(Exception):
    """A catalog file cannot be safely used."""


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    repo: str
    channel: str
    version: str
    sha: str


def _major(text: str) -> str | None:
    match = re.match(r"v(\d+)", text)
    return match.group(1) if match else None


def _version_order(text: str) -> tuple[int, int, int] | None:
    match = NUMERIC_VERSION.fullmatch(text)
    if match is None:
        return None
    return tuple(int(part or 0) for part in match.groups())


def _parse_toml_subset(text: str) -> dict[str, dict[str, str]]:
    tables: dict[str, dict[str, str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip().strip('"').strip("'")
            tables.setdefault(current, {})
            continue
        if "=" not in line or current is None:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().split("#", 1)[0].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        tables[current][key.strip()] = value
    return tables


def load_catalog(path: Path) -> dict[str, CatalogEntry]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CatalogError(f"catalog not found: {path}") from exc
    try:
        import tomllib as _tomllib  # type: ignore[import]
        with path.open("rb") as handle:
            try:
                data = _tomllib.load(handle)
            except Exception as exc:
                raise CatalogError(f"invalid catalog {path}: {exc}") from exc
        flat: dict[str, dict[str, str]] = {}

        def walk(prefix: str, node: object) -> None:
            if isinstance(node, dict) and {"channel", "version", "sha"} <= set(node):
                flat[prefix] = {k: str(v) for k, v in node.items()
                                if k in ("channel", "version", "sha")}
                return
            if isinstance(node, dict):
                for key, value in node.items():
                    name = f"{prefix}.{key}" if prefix else str(key)
                    walk(name, value)

        walk("", data)
    except ImportError:
        flat = _parse_toml_subset(text)
    entries: dict[str, CatalogEntry] = {}
    for table, fields in flat.items():
        repo = table.strip().strip('"').strip("'")
        if repo.startswith("actions."):
            repo = repo.removeprefix("actions.")
            if "/" not in repo:
                repo = "actions/" + repo
        if "/" not in repo:
            continue
        channel = str(fields.get("channel", "")).strip()
        version = str(fields.get("version", "")).strip()
        sha = str(fields.get("sha", "")).strip()
        if not channel or not version or not sha:
            raise CatalogError(f"invalid catalog record '{table}': "
                               "need channel/version/sha")
        if not CHANNEL.fullmatch(channel):
            raise CatalogError(f"invalid catalog record '{table}': "
                               f"bad channel {channel!r}")
        if not VERSION.fullmatch(version):
            raise CatalogError(f"invalid catalog record '{table}': "
                               f"bad version {version!r}")
        if not SHA.fullmatch(sha):
            raise CatalogError(f"invalid catalog record '{table}': bad sha")
        if _major(channel) != _major(version):
            raise CatalogError(f"invalid catalog record '{table}': channel "
                               f"{channel} and version {version} disagree on major")
        key = repo.lower()
        if key in entries:
            raise CatalogError(f"ambiguous catalog record for '{repo}'")
        entries[key] = CatalogEntry(repo=repo, channel=channel,
                                    version=version, sha=sha.lower())
    if not entries:
        raise CatalogError(f"invalid catalog {path}: no action records")
    return entries


def catalog_pin_for_spec(spec: str,
                         entries: dict[str, CatalogEntry]) -> tuple[str | None, str, str]:
    """Return (sha, subpath, note). sha None means refuse; note explains why."""
    from pinact import pinning
    try:
        parsed = pinning.parse_action(spec)
    except Exception:
        return None, "", "unparseable uses value"
    if parsed is None:
        return None, "", "local/docker action"
    base, ref = parsed
    name = spec.rsplit("@", 1)[0]
    name_parts = name.split("/")
    subpath = ""
    if len(name_parts) > 2:
        subpath = "/" + "/".join(name_parts[2:])
    entry = entries.get(base.lower())
    if entry is None:
        return None, subpath, f"no approved pin for '{base}'"
    if SHA.fullmatch(ref):
        return None, subpath, "SHA without version label is not proof of approval"
    if _major(ref) != _major(entry.channel):
        return None, subpath, (f"ref {ref} crosses major of approved channel "
                                f"{entry.channel}; refusing major bump")
    current_version = _version_order(ref)
    approved_version = _version_order(entry.version)
    if ref != entry.channel and (current_version is None or approved_version is None):
        return None, subpath, "cannot compare ref with catalog version; refusing downgrade"
    if (current_version is not None and approved_version is not None
            and current_version > approved_version):
        return None, subpath, (f"ref {ref} is newer than catalog version "
                               f"{entry.version}; refusing downgrade")
    return entry.sha, subpath, f"approved {entry.version}"


def catalog_approves_use(use, entries: dict[str, CatalogEntry]) -> tuple[bool, str]:
    from pinact import pinning
    try:
        parsed = pinning.parse_action(use.spec)
    except pinning.PinError:
        return False, "unparseable uses value"
    if parsed is None:
        return False, "local/docker action"
    repo, ref = parsed
    entry = entries.get(repo.lower())
    if entry is None:
        return False, f"no approved pin for '{repo}'"
    if not SHA.fullmatch(ref):
        sha, _, note = catalog_pin_for_spec(use.spec, entries)
        return sha is not None, note
    label = pinning.version_comment(use.comment)
    if label is None:
        return False, "SHA without version label is not proof of approval"
    if _major(label) != _major(entry.channel):
        return False, f"version label {label} does not match approved channel {entry.channel}"
    label_version = _version_order(label)
    approved_version = _version_order(entry.version)
    if label_version is None or approved_version is None:
        return False, "cannot compare version label with catalog version"
    if label_version > approved_version:
        return False, (f"version label {label} is newer than catalog version "
                       f"{entry.version}; refusing downgrade")
    if ref.lower() != entry.sha:
        return False, "pinned SHA differs from catalog SHA"
    return True, f"approved {entry.version}"
