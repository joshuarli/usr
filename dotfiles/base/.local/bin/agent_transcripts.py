#!/usr/bin/env python3
"""Per-harness transcript discovery, header reading, and event normalization."""
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import unquote

HARNESSES = ("codex", "claude", "muse", "grok")
SUBSTANTIVE_KINDS = ("user", "assistant", "developer", "tool-call", "tool-output", "task_complete", "compacted", "context", "skill_read_observed")
HEADER_SCAN_LINES = 200
HEADER_SCAN_BYTES = 524288
MAX_NATIVE_ID = 256
_SKIP_TEXT_KEYS = frozenset((
    "encrypted_content", "internal_chat_message_metadata_passthrough", "id", "call_id",
    "type", "status", "role", "timestamp", "ordinal",
))
_CLAUDE_KNOWN = frozenset((
    "summary", "system", "attachment", "queue-operation", "permission-mode", "mode", "atis-latch", "last-prompt",
    "ai-title", "custom-title", "file-history-snapshot", "file-history-delta", "progress", "api-request",
    "api-request-blob", "pr-link", "agent-name", "tag",
))
_EXIT_PATTERNS = (
    re.compile(r"(?im)^\s*exit(?:ed)? (?:code|status)[: ]+(-?\d+)\b"),
    re.compile(r"(?i)\b(?:process )?exited with (?:exit )?code (-?\d+)\b"),
    re.compile(r"(?im)^exit: (-?\d+)\s*$"),
)


def qualified_id(harness, native_id):
    if harness == "codex" and not _has_harness_prefix(native_id):
        return native_id
    return harness + ":" + native_id


def split_id(value):
    prefix, separator, rest = str(value).partition(":")
    if separator and prefix in HARNESSES:
        return prefix, rest
    return "codex", str(value)


def _has_harness_prefix(value):
    prefix, separator, _ = str(value).partition(":")
    return bool(separator) and prefix in HARNESSES


def clean_native_id(value, path):
    text = str(value)
    if not text or len(text) > MAX_NATIVE_ID or any(ord(char) < 32 for char in text):
        return "path-" + hashlib.sha256(str(path).encode("utf-8", "surrogateescape")).hexdigest()[:24]
    return text


def default_roots(environ=None):
    environ = os.environ if environ is None else environ
    home = Path(environ.get("HOME") or str(Path.home()))
    codex_home = Path(environ.get("CODEX_HOME") or str(home / ".codex")).expanduser()
    claude_home = Path(environ.get("CLAUDE_CONFIG_DIR") or str(home / ".claude")).expanduser()
    data_home = Path(environ.get("XDG_DATA_HOME") or str(home / ".local" / "share")).expanduser()
    grok_home = Path(environ.get("GROK_HOME") or str(home / ".grok")).expanduser()
    return {
        "codex": [codex_home / "sessions", codex_home / "archived_sessions"],
        "claude": [claude_home / "projects"],
        "muse": [data_home / "muse" / "sessions"],
        "grok": [grok_home / "sessions"],
    }


def coerce_roots(roots):
    if roots is None:
        return default_roots()
    if isinstance(roots, dict):
        unknown = set(roots) - set(HARNESSES)
        if unknown:
            raise ValueError("unsupported transcript harness: " + ", ".join(sorted(unknown)))
        return {name: [Path(root) for root in _listed(value)] for name, value in roots.items()}
    return {"codex": [Path(root) for root in _listed(roots)]}


def _listed(value):
    return [value] if isinstance(value, (str, os.PathLike)) else list(value)


def is_source_name(harness, name):
    if harness == "codex":
        return name.startswith("rollout-") and name.endswith(".jsonl")
    if harness == "claude":
        return name.endswith(".jsonl")
    if harness == "muse":
        return name == "session.jsonl"
    return name == "chat_history.jsonl"


def _text_value(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(part for part in (_text_value(item) for item in value) if part)
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            if key in _SKIP_TEXT_KEYS:
                continue
            text = _text_value(item)
            if text:
                parts.append((str(key) + ": " if len(value) > 1 else "") + text)
        return "\n".join(parts)
    return ""


def _content_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(part for part in (_content_text(item) for item in value) if part)
    if isinstance(value, dict):
        block_type = value.get("type")
        if block_type in ("image", "input_image", "audio", "input_audio", "encrypted_content", "thinking", "redacted_thinking"):
            return ""
        if "text" in value:
            return _text_value(value.get("text"))
        if "content" in value:
            return _content_text(value.get("content"))
    return ""


def exit_outcome(text):
    for pattern in _EXIT_PATTERNS:
        match = pattern.search(text[:4000])
        if match:
            return "ok" if int(match.group(1)) == 0 else "error"
    return None


def _record(kind, text="", timestamp=None, call_id=None, raw_type=None, outcome=None, **fields):
    record = {
        "kind": str(kind),
        "text": text if isinstance(text, str) else _text_value(text),
        "timestamp": str(timestamp) if timestamp is not None else None,
        "call_id": str(call_id) if call_id is not None else None,
        "raw_type": str(raw_type) if raw_type is not None else None,
        "outcome": outcome,
    }
    record.update(fields)
    return record


def _codex_record(obj):
    top_type = obj.get("type", "unknown")
    payload = obj.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    item_type = payload.get("type")
    timestamp = obj.get("timestamp") or payload.get("timestamp")
    if top_type == "response_item":
        if item_type == "message":
            role = payload.get("role") or "unknown"
            return _record(str(role), _content_text(payload.get("content", "")), timestamp, raw_type=top_type, role=role)
        if item_type == "agent_message":
            return _record("assistant", _content_text(payload.get("content", "")), timestamp, raw_type=top_type, role="assistant")
        if item_type in ("function_call", "custom_tool_call"):
            name = payload.get("name") or "tool"
            args = payload.get("arguments", payload.get("input", ""))
            return _record("tool-call", str(name) + ("\n" + _text_value(args) if args else ""), timestamp, payload.get("call_id"), top_type, tool_name=name)
        if item_type in ("function_call_output", "custom_tool_call_output"):
            output = payload.get("output", "")
            text = output if isinstance(output, str) else _content_text(output) or _text_value(output)
            return _record("tool-output", text, timestamp, payload.get("call_id"), top_type, outcome=exit_outcome(text))
        if item_type == "reasoning":
            return _record("reasoning", "", timestamp, raw_type=top_type)
        return _record("response_item:" + str(item_type or "unknown"), _text_value(payload), timestamp, payload.get("call_id"), top_type)
    if top_type == "event_msg":
        if item_type == "task_complete":
            return _record("task_complete", payload.get("last_agent_message", ""), timestamp, raw_type=top_type)
        if item_type == "turn_aborted":
            return _record("turn_aborted", payload.get("reason", ""), timestamp, raw_type=top_type)
        return _record("event_msg:" + str(item_type or "unknown"), "", timestamp, raw_type=top_type)
    if top_type == "session_meta":
        return _record("session_meta", "", timestamp, raw_type=top_type)
    if top_type in ("world_state", "turn_context", "token_usage_record", "inter_agent_communication_metadata"):
        return _record(str(top_type), "", timestamp, raw_type=top_type)
    if top_type == "compacted":
        return _record("compacted", _text_value(payload), timestamp, raw_type=top_type)
    return _record("unknown:" + str(top_type), _text_value(payload), timestamp, raw_type=top_type)


def _claude_blocks(content):
    return [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []


def _claude_record(obj):
    kind = obj.get("type") or "unknown"
    timestamp = obj.get("timestamp")
    message = obj.get("message")
    message = message if isinstance(message, dict) else {}
    content = message.get("content", obj.get("content", ""))
    blocks = _claude_blocks(content)
    if kind == "user":
        results = [block for block in blocks if block.get("type") == "tool_result"]
        if results:
            text = "\n".join(part for part in (_content_text(block.get("content", "")) for block in results) if part)
            failed = any(block.get("is_error") for block in results)
            call_id = ",".join(str(block["tool_use_id"]) for block in results if block.get("tool_use_id"))
            return _record("tool-output", text, timestamp, call_id or None, kind, outcome="error" if failed else "ok", role="user")
        text = _content_text(content)
        injected = obj.get("isMeta") or obj.get("sourceToolUseID") or obj.get("isCompactSummary")
        return _record("context" if injected else "user", text, timestamp, raw_type=kind, role="user")
    if kind == "assistant":
        calls = [block for block in blocks if block.get("type") == "tool_use"]
        text = "\n".join(part for part in (_content_text(block) for block in blocks if block.get("type") == "text") if part)
        if calls:
            rendered = "\n".join(str(call.get("name") or "tool") + "\n" + _text_value(call.get("input", {})) for call in calls)
            call_id = ",".join(str(call["id"]) for call in calls if call.get("id"))
            if text:
                return _record("assistant", text + "\n" + rendered, timestamp, call_id or None, kind, role="assistant")
            return _record("tool-call", rendered, timestamp, call_id or None, kind, tool_name=str(calls[0].get("name") or "tool"))
        if text:
            return _record("assistant", text, timestamp, raw_type=kind, role="assistant")
        return _record("reasoning" if any(block.get("type") in ("thinking", "redacted_thinking") for block in blocks) else "assistant", "", timestamp, raw_type=kind)
    if kind in _CLAUDE_KNOWN:
        return _record(str(kind), "", timestamp, raw_type=kind)
    return _record("unknown:" + str(kind), "", timestamp, raw_type=kind)


def _muse_record(obj):
    payload = obj.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    event = payload.get("event")
    event = event if isinstance(event, dict) else {}
    timestamp = obj.get("recorded_at")
    if isinstance(timestamp, (int, float)):
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp / 1_000_000))
    if payload.get("kind") == "metadata" and not event:
        return _record("session_meta", "", timestamp, raw_type="metadata")
    event_type = event.get("kind") or payload.get("kind")
    if not event_type:
        return _record("unknown:muse", "", timestamp, raw_type=payload.get("kind", "event"))
    if event_type == "model_user_messages":
        return _record("user", _content_text(event.get("messages", [])), timestamp, raw_type=event_type, role="user")
    if event_type == "skill_read_observed":
        return _record(str(event_type), _text_value(event), timestamp, raw_type=event_type)
    if event_type == "model_request_configured":
        return _record(str(event_type), "", timestamp, raw_type=event_type)
    return _record("unknown:" + str(event_type), "", timestamp, raw_type=event_type)


def _grok_record(obj):
    kind = obj.get("type") or "unknown"
    timestamp = obj.get("timestamp")
    if kind == "user":
        text = _content_text(obj.get("content", ""))
        return _record("context" if obj.get("synthetic_reason") else "user", text, timestamp, raw_type=kind, role="user")
    if kind == "assistant":
        text = _content_text(obj.get("content", ""))
        calls = [call for call in obj.get("tool_calls", []) or [] if isinstance(call, dict)]
        rendered = []
        for call in calls:
            args = call.get("arguments", "")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    pass
            rendered.append(str(call.get("name") or "tool") + "\n" + _text_value(args))
        if rendered:
            call_id = ",".join(str(call["id"]) for call in calls if call.get("id"))
            if text:
                return _record("assistant", text + "\n" + "\n".join(rendered), timestamp, call_id or None, kind, role="assistant")
            return _record("tool-call", "\n".join(rendered), timestamp, call_id or None, kind, tool_name=str(calls[0].get("name") or "tool"))
        return _record("assistant", text, timestamp, raw_type=kind, role="assistant")
    if kind == "tool_result":
        text = _content_text(obj.get("content", ""))
        return _record("tool-output", text, timestamp, obj.get("tool_call_id"), kind, outcome=exit_outcome(text))
    if kind in ("reasoning", "system"):
        return _record(str(kind), "", timestamp, raw_type=kind)
    return _record("unknown:" + str(kind), "", timestamp, raw_type=kind)


def normalize(obj, harness="codex"):
    if not isinstance(obj, dict):
        return [_record("unknown:non_object", "", raw_type=type(obj).__name__)]
    if harness == "codex":
        return [_codex_record(obj)]
    if harness == "claude":
        return [_claude_record(obj)]
    if harness == "muse":
        return [_muse_record(obj)]
    if harness == "grok":
        return [_grok_record(obj)]
    raise ValueError("unsupported transcript harness: " + str(harness))


def _json_object(raw):
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _head_lines(path, open_source, stats, wanted):
    lines, used = [], 0
    with open_source(path, stats) as stream:
        info = os.fstat(stream.fileno())
        while len(lines) < wanted and used < HEADER_SCAN_BYTES:
            raw = stream.readline()
            if not raw:
                break
            used += len(raw)
            if stats is not None:
                stats["bytes_read"] += len(raw)
            lines.append(raw)
    return lines, info


def _sibling_json(path, name, open_source, stats, limit=65536):
    try:
        with open_source(Path(path).parent / name, stats) as stream:
            data = stream.read(limit)
        if stats is not None:
            stats["bytes_read"] += len(data)
        return _json_object(data)
    except OSError:
        return None


def _grok_primary(path, open_source, stats):
    try:
        with open_source(Path(path).parent / "events.jsonl", stats) as stream:
            for _ in range(HEADER_SCAN_LINES):
                raw = stream.readline()
                if not raw:
                    return False
                if stats is not None:
                    stats["bytes_read"] += len(raw)
                obj = _json_object(raw)
                if obj and obj.get("type") == "turn_started":
                    return obj.get("session_relationship") == "primary"
    except OSError:
        return False
    return False


def _json_text(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) if value is not None else None
    except (TypeError, ValueError):
        return None


def read_header(harness, path, open_source, stats=None):
    lines, info = _head_lines(path, open_source, stats, HEADER_SCAN_LINES if harness in ("claude", "muse") else 1)
    first = lines[0] if lines else b""
    header = {
        "native_id": path.stem, "cwd": "", "parent": None, "source": None, "thread_source": None,
        "ancestry": "known", "first": first, "file_stat": info, "parent_native": None,
    }
    objects = [obj for obj in (_json_object(raw) for raw in lines) if obj is not None]
    if harness == "codex":
        obj = objects[0] if objects and _json_object(first) is not None else {}
        payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
        header["native_id"] = str(payload.get("id") or payload.get("session_id") or path.stem)
        header["cwd"] = payload.get("cwd") if isinstance(payload.get("cwd"), str) else ""
        source = payload.get("source")
        thread_source = payload.get("thread_source")
        if source is None:
            source = thread_source
        header["source"] = _json_text(source)
        header["thread_source"] = str(thread_source) if thread_source is not None else None
        parent = payload.get("parent_thread_id")
        if parent is None and isinstance(source, dict):
            spawned = source.get("subagent")
            spawned = spawned.get("thread_spawn") if isinstance(spawned, dict) else None
            parent = spawned.get("parent_thread_id") if isinstance(spawned, dict) else None
        header["parent_native"] = str(parent) if parent is not None else None
        return header
    if harness == "claude":
        sidechain = False
        session = None
        for obj in objects:
            session = session or (obj.get("sessionId") if isinstance(obj.get("sessionId"), str) else None)
            if isinstance(obj.get("cwd"), str) and obj["cwd"]:
                header["cwd"] = obj["cwd"]
                sidechain = bool(obj.get("isSidechain"))
                break
        sidechain = sidechain or "subagents" in path.parts
        if sidechain:
            header["native_id"] = path.stem
            header["parent_native"] = session if session and session != path.stem else None
            header["source"] = _json_text({"subagent": {"sidechain": True}})
            header["thread_source"] = "subagent"
        else:
            header["native_id"] = session or path.stem
            header["thread_source"] = "user"
            header["source"] = _json_text("user")
        return header
    if harness == "muse":
        header["native_id"] = path.parent.name
        header["ancestry"] = "unknown"
        for obj in objects:
            payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
            record = payload.get("record") if isinstance(payload.get("record"), dict) else {}
            if payload.get("kind") == "metadata" and isinstance(record.get("workspace_root"), str):
                header["cwd"] = record["workspace_root"]
                break
        return header
    header["native_id"] = path.parent.name
    summary = _sibling_json(path, "summary.json", open_source, stats)
    info_block = summary.get("info") if isinstance(summary, dict) and isinstance(summary.get("info"), dict) else {}
    if isinstance(info_block.get("cwd"), str):
        header["cwd"] = info_block["cwd"]
    else:
        header["cwd"] = unquote(path.parent.parent.name)
    if not header["cwd"].startswith("/"):
        header["cwd"] = ""
    header["ancestry"] = "known" if _grok_primary(path, open_source, stats) else "unknown"
    return header
