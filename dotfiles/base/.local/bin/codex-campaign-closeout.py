#!/usr/bin/env python3

import argparse
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional


STATE_NAME = "codex-campaign-closeout.json"


class CloseoutError(Exception):
    pass


def git_output(cwd, *args):
    result = subprocess.run(
        ["git", "-C", os.fspath(cwd), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        message = os.fsdecode(result.stderr).strip()
        raise CloseoutError(message or "git command failed")
    return result.stdout


def canonical(path):
    return os.path.normcase(os.path.realpath(os.fspath(path)))


def repository_root(cwd):
    output = git_output(cwd, "rev-parse", "--show-toplevel")
    return Path(os.fsdecode(output.rstrip(b"\n"))).resolve(strict=True)


def filesystem_root(cwd):
    try:
        directory = Path(cwd).resolve(strict=True)
    except OSError:
        return None
    if directory.is_file():
        directory = directory.parent
    for candidate in (directory, *directory.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def listed_worktrees(root):
    output = git_output(root, "worktree", "list", "--porcelain", "-z")
    worktrees = []
    current: Optional[dict[str, Any]] = None
    for field in output.split(b"\0"):
        if field.startswith(b"worktree "):
            if current is not None:
                worktrees.append(current)
            current = {
                "path": Path(os.fsdecode(field[len(b"worktree ") :])),
                "head": None,
                "branch": None,
            }
        elif field == b"" and current is not None:
            worktrees.append(current)
            current = None
        elif current is not None and field.startswith(b"HEAD "):
            current["head"] = os.fsdecode(field[len(b"HEAD ") :])
        elif current is not None and field.startswith(b"branch "):
            current["branch"] = os.fsdecode(field[len(b"branch ") :])
    if current is not None:
        worktrees.append(current)
    if not worktrees or any(not worktree["head"] for worktree in worktrees):
        raise CloseoutError("git returned no registered worktrees")
    return worktrees


def state_path(root):
    return root / ".work" / STATE_NAME


def retained_worktree_is_under_work_directory(root, path):
    work_directory = Path(canonical(root)) / ".work"
    candidate = Path(canonical(path))
    try:
        candidate.relative_to(work_directory)
    except ValueError:
        return False
    return candidate != work_directory


def work_directory(root):
    directory = root / ".work"
    if directory.is_symlink():
        raise CloseoutError(f"{directory} must not be a symlink")
    return directory


def state_file_status(path):
    work_directory(path.parent.parent)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(info.st_mode):
        raise CloseoutError(f"{path} must be a regular file")
    return True


def marker_through_symlink(root):
    marker = state_path(root)
    try:
        marker.lstat()
    except FileNotFoundError:
        return False
    return True


def check_symlinked_marker(root):
    try:
        if marker_through_symlink(root):
            block("Campaign closeout marker is under a symlinked .work directory. Restore .work as a real directory.")
    except OSError as error:
        block(f"Campaign closeout check failed: cannot inspect marker under symlinked .work: {error}")


def load_state(root):
    path = state_path(root)
    if not state_file_status(path):
        raise CloseoutError("campaign closeout has not been started")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CloseoutError(f"cannot read {path}: {error}") from error
    if not isinstance(state, dict) or state.get("schema") != 1:
        raise CloseoutError(f"{path} has an unsupported format")
    integration_root = state.get("integration_root")
    if not isinstance(integration_root, str) or "\0" in integration_root:
        raise CloseoutError(f"{path} has an invalid integration root")
    if canonical(integration_root) != canonical(root):
        raise CloseoutError(f"{path} belongs to a different integration worktree")
    if not isinstance(state.get("baseline_roots"), list) or not all(
        isinstance(root_name, str) and "\0" not in root_name and Path(root_name).is_absolute()
        for root_name in state["baseline_roots"]
    ):
        raise CloseoutError(f"{path} has invalid baseline roots")
    if not isinstance(state.get("allowed"), dict):
        raise CloseoutError(f"{path} has invalid allowed worktrees")
    for path_name, entry in state["allowed"].items():
        if (
            not isinstance(path_name, str)
            or "\0" in path_name
            or not Path(path_name).is_absolute()
            or not retained_worktree_is_under_work_directory(root, path_name)
            or not isinstance(entry, dict)
            or not isinstance(entry.get("head"), str)
            or not entry["head"]
            or (entry.get("branch") is not None and not isinstance(entry.get("branch"), str))
            or not isinstance(entry.get("reason"), str)
            or not entry["reason"].strip()
        ):
            raise CloseoutError(f"{path} has an invalid allowed worktree entry")
    return state


def save_state(root, state, create=False):
    directory = root / ".work"
    if directory.is_symlink() or not directory.is_dir():
        raise CloseoutError(f"{directory} must be a real directory")
    path = state_path(root)
    if create and state_file_status(path):
        raise CloseoutError(f"{path} already exists")
    if not create and not state_file_status(path):
        raise CloseoutError("campaign closeout has not been started")
    encoded = (json.dumps(state, ensure_ascii=True, sort_keys=True) + "\n").encode()
    if create:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError as error:
            raise CloseoutError(f"{path} already exists") from error
        with os.fdopen(descriptor, "wb") as output:
            output.write(encoded)
        return
    descriptor, temporary = tempfile.mkstemp(prefix=".codex-campaign-closeout.", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(encoded)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def ensure_work_directory(root):
    directory = work_directory(root)
    ignored = subprocess.run(
        ["git", "-C", os.fspath(root), "check-ignore", "--verbose", "-z", "--stdin"],
        input=b".work/\0",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if ignored.returncode != 0:
        raise CloseoutError(".work must be ignored before campaign closeout starts")
    fields = ignored.stdout.split(b"\0")
    if len(fields) < 5 or fields[3] != b".work/":
        raise CloseoutError("git returned an invalid .work ignore rule")
    ignore_file = Path(os.fsdecode(fields[0]))
    if not ignore_file.is_absolute():
        ignore_file = root / ignore_file
    expected_ignore_file = Path(
        os.fsdecode(git_output(root, "rev-parse", "--path-format=absolute", "--git-path", "info/exclude").rstrip(b"\n"))
    )
    if canonical(ignore_file) != canonical(expected_ignore_file):
        raise CloseoutError(".work must be ignored through .git/info/exclude")
    if not directory.exists():
        directory.mkdir(mode=0o700)
    if not directory.is_dir():
        raise CloseoutError(f"{directory} must be a directory")
    return directory


def begin(root):
    ensure_work_directory(root)
    if state_file_status(state_path(root)):
        load_state(root)
        print(f"Campaign closeout is already active in {root}")
        return
    worktrees = listed_worktrees(root)
    roots = {canonical(worktree["path"]) for worktree in worktrees}
    integration = canonical(root)
    if integration not in roots:
        raise CloseoutError(f"{root} is not a registered worktree")
    baseline = canonical(worktrees[0]["path"])
    state = {
        "schema": 1,
        "integration_root": os.fspath(root),
        "baseline_roots": sorted({integration, baseline}),
        "allowed": {},
    }
    save_state(root, state, create=True)
    print(f"Campaign closeout is active in {root}")


def allow(root, path, reason):
    if not reason.strip():
        raise CloseoutError("an allow reason is required")
    state = load_state(root)
    candidate = canonical(path)
    worktrees = listed_worktrees(root)
    matching = next((worktree for worktree in worktrees if canonical(worktree["path"]) == candidate), None)
    if matching is None:
        raise CloseoutError(f"{path} is not a registered worktree")
    if candidate in set(state["baseline_roots"]) | {canonical(root)}:
        raise CloseoutError(f"{path} is a baseline worktree and does not need an allowance")
    if not retained_worktree_is_under_work_directory(root, candidate):
        raise CloseoutError(f"{path} must be under {root}/.work")
    if git_output(matching["path"], "status", "--porcelain", "--untracked-files=all"):
        raise CloseoutError(f"{path} has uncommitted or untracked files")
    state["allowed"][candidate] = {
        "branch": matching["branch"],
        "head": matching["head"],
        "reason": reason.strip(),
    }
    save_state(root, state)
    print(f"Recorded retained worktree {path}")


def cancel(root):
    path = state_path(root)
    if not state_file_status(path):
        print("Campaign closeout is not active")
        return
    path.unlink()
    print("Campaign closeout is cancelled")


def hook_input():
    raw = sys.stdin.buffer.read()
    try:
        event = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as error:
        return Path.cwd(), f"cannot read the Stop hook event: {error}"
    if not isinstance(event, dict):
        return Path.cwd(), "the Stop hook event is not an object"
    cwd = event.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return Path.cwd(), "the Stop hook event has no working directory"
    return Path(cwd), None


def block(reason):
    sys.stdout.write(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=True))
    sys.stdout.write("\n")


def run_hook():
    cwd, input_error = hook_input()
    try:
        root = repository_root(cwd)
    except (CloseoutError, OSError) as error:
        root = filesystem_root(cwd) or filesystem_root(Path.cwd())
        if root is None:
            return
        directory = root / ".work"
        if directory.is_symlink():
            check_symlinked_marker(root)
            return
        if not directory.is_dir():
            return
        try:
            if not state_file_status(state_path(root)):
                return
        except (CloseoutError, OSError, ValueError) as state_error:
            block(f"Campaign closeout check failed: {state_error}")
            return
        block(f"Campaign closeout check failed: cannot resolve the repository root: {error}")
        return
    directory = root / ".work"
    if directory.is_symlink():
        check_symlinked_marker(root)
        return
    if not directory.is_dir():
        return
    marker = state_path(root)
    try:
        if not state_file_status(marker):
            return
        if input_error:
            raise CloseoutError(input_error)
        state = load_state(root)
        worktrees = listed_worktrees(root)
        baseline = {canonical(path) for path in state["baseline_roots"]}
        remaining = []
        for worktree in worktrees:
            path = worktree["path"]
            path_key = canonical(path)
            if path_key in baseline | {canonical(root)}:
                continue
            expected = state["allowed"].get(path_key)
            if expected is None:
                remaining.append(path)
                continue
            if expected["head"] != worktree["head"] or expected["branch"] != worktree["branch"]:
                remaining.append(path)
                continue
            if git_output(path, "status", "--porcelain", "--untracked-files=all"):
                remaining.append(path)
        if remaining:
            paths = "\n".join(f"- {path}" for path in remaining)
            reason = (
                "Campaign closeout is active. Run git worktree prune to clear stale registrations, "
                "then remove safe worktrees. For each tree that must stay, "
                "put it under .work/, commit and name it in the campaign handoff, then run "
                "codex-campaign-closeout.py allow --path <path> --reason <reason>. "
                f"Unaccounted registered worktrees:\n{paths}"
            )
            block(reason)
            return
        marker.unlink()
    except (CloseoutError, OSError, ValueError) as error:
        block(f"Campaign closeout check failed: {error}")


def arguments():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("begin")
    allowance = commands.add_parser("allow")
    allowance.add_argument("--path", required=True)
    allowance.add_argument("--reason", required=True)
    commands.add_parser("cancel")
    commands.add_parser("hook")
    return parser.parse_args()


def main():
    options = arguments()
    if options.command == "hook":
        run_hook()
        return 0
    try:
        root = repository_root(Path.cwd())
        if options.command == "begin":
            begin(root)
        elif options.command == "allow":
            allow(root, options.path, options.reason)
        else:
            cancel(root)
    except (CloseoutError, OSError) as error:
        print(f"codex-campaign-closeout.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
