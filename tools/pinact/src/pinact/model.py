"""Shared source document model: one parse per file for all rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pinact._vendor import yaml
from pinact._vendor.yaml.composer import ComposerError
from pinact._vendor.yaml.nodes import MappingNode, ScalarNode, SequenceNode


@dataclass
class YamlProblem:
    line: int
    column: int
    message: str


@dataclass
class SourceDocument:
    path: Path
    display: str
    text: str
    lines: list[str]
    documents: list[object] = field(default_factory=list)
    syntax_error: YamlProblem | None = None
    duplicate_keys: list[tuple[int, int, str]] = field(default_factory=list)
    kind: str = "workflow"


def _mark_line_col(node) -> tuple[int, int]:
    return node.start_mark.line + 1, node.start_mark.column + 1


def mapping_pairs(node: MappingNode) -> list[tuple[ScalarNode, object]]:
    out = []
    for key, value in node.value:
        out.append((key, value))
    return out


def mapping_get(node: MappingNode, name: str) -> object | None:
    for key, value in node.value:
        if isinstance(key, ScalarNode) and key.value == name:
            return value
    return None


def mapping_get_key(node: MappingNode, name: str) -> ScalarNode | None:
    for key, _ in node.value:
        if isinstance(key, ScalarNode) and key.value == name:
            return key
    return None


def scalar_text(node: object) -> str | None:
    if isinstance(node, ScalarNode):
        return node.value
    return None


def _collect_duplicates(node: object, seen: set[int], out: list[tuple[int, int, str]]) -> None:
    if isinstance(node, MappingNode):
        if id(node) in seen:
            return
        seen.add(id(node))
        counts: dict[str, int] = {}
        for key, value in node.value:
            if isinstance(key, ScalarNode):
                counts[key.value] = counts.get(key.value, 0) + 1
                if counts[key.value] > 1:
                    out.append((key.start_mark.line + 1, key.start_mark.column + 1, key.value))
            _collect_duplicates(value, seen, out)
    elif isinstance(node, SequenceNode):
        if id(node) in seen:
            return
        seen.add(id(node))
        for item in node.value:
            _collect_duplicates(item, seen, out)


def parse_document(path: Path, display: str) -> tuple[SourceDocument, YamlProblem | None]:
    try:
        with path.open(encoding="utf-8", newline="") as f:
            text = f.read()
    except (OSError, UnicodeError) as exc:
        return SourceDocument(path=path, display=display, text="", lines=[]), YamlProblem(1, 1, str(exc))
    lines = text.splitlines(keepends=True)
    doc = SourceDocument(path=path, display=display, text=text, lines=lines)
    name = path.name
    if name in ("action.yml", "action.yaml"):
        doc.kind = "action"
    try:
        documents = list(yaml.compose_all(text, Loader=yaml.BaseLoader))
    except ComposerError as exc:
        msg = str(exc)
        line, col = 1, 1
        if hasattr(exc, "problem_mark") and exc.problem_mark is not None:
            line = exc.problem_mark.line + 1
            col = exc.problem_mark.column + 1
        doc.syntax_error = YamlProblem(line, col, f"unresolvable anchor: {msg}")
        return doc, doc.syntax_error
    except yaml.YAMLError as exc:
        msg = str(exc).replace("\n", " ")
        line, col = 1, 1
        mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
        if mark is not None:
            line = mark.line + 1
            col = mark.column + 1
        else:
            import re as _re
            m = _re.search(r"line (\d+), column (\d+)", msg)
            if m:
                line, col = int(m.group(1)), int(m.group(2))
        doc.syntax_error = YamlProblem(line, col, msg)
        return doc, doc.syntax_error
    doc.documents = [d for d in documents if d is not None]
    dupes: list[tuple[int, int, str]] = []
    _collect_duplicates_list(doc.documents, dupes)
    doc.duplicate_keys = dupes
    if doc.kind != "action":
        for d in doc.documents:
            if isinstance(d, MappingNode):
                for key, _ in d.value:
                    if isinstance(key, ScalarNode) and key.value == "runs":
                        has_jobs = any(
                            isinstance(k, ScalarNode) and k.value == "jobs"
                            for k, _ in d.value
                        )
                        has_on = any(
                            isinstance(k, ScalarNode) and k.value in ("on", True)
                            or (isinstance(k, ScalarNode) and k.value == "on")
                            for k, _ in d.value
                        )
                        if not has_jobs and not has_on:
                            doc.kind = "action"
                        break
    return doc, None


def _collect_duplicates_list(documents: list[object], out: list[tuple[int, int, str]]) -> None:
    seen: set[int] = set()
    for document in documents:
        _collect_duplicates(document, seen, out)
