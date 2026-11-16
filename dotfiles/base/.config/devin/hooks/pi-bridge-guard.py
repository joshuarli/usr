#!/usr/bin/env python3
"""PreToolUse guard: Devin sessions never invoke pi-subagent-bridge.

Reads the hook event JSON on stdin and blocks exec-like tool calls that
would run the pi-subagent-bridge binary. Only command positions count:
mentions in arguments (rg, grep, cd into the source tree, echo) pass.
"""

import json
import os
import re
import shutil
import sys

REASON = "Devin sessions delegate only through native run_subagent subagents; pi-subagent-bridge is banned by policy."

ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SEGMENT_SPLIT = re.compile(r"[;|&`\n(){}]+|\$\(")
C_FLAG = re.compile(r"(?:^|\s)-c\s+(['\"])(.*?)\1")
WRAPPERS = {
    "sudo", "doas", "env", "command", "exec", "nohup", "time", "nice",
    "ionice", "stdbuf", "xargs", "builtin", "sh", "bash", "zsh", "dash",
    "ash", "eval",
}


def is_invocation(word: str) -> bool:
    base = word.rsplit("/", 1)[-1]
    if base != "pi-subagent-bridge":
        return False
    if "/" not in word:
        return shutil.which(word) is not None
    return os.path.isfile(os.path.expanduser(word))


def check(command: str, depth: int = 0) -> bool:
    if depth > 4:
        return False
    for segment in SEGMENT_SPLIT.split(command):
        words = segment.split()
        i = 0
        while i < len(words):
            word = words[i].strip("\"'")
            if ASSIGNMENT.match(word) or word in WRAPPERS or (
                "/" in word and word.rsplit("/", 1)[-1] in WRAPPERS
            ):
                i += 1
                continue
            if is_invocation(word):
                return True
            break
        for match in C_FLAG.finditer(segment):
            if check(match.group(2), depth + 1):
                return True
    return False


def main() -> int:
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input") or {}
    for field in ("command", "text_input", "bytes_input"):
        value = tool_input.get(field)
        if isinstance(value, str) and check(value):
            print(json.dumps({"decision": "block", "reason": REASON}))
            return 0
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
