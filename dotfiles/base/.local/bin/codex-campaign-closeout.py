#!/usr/bin/env python3

import argparse
import fcntl
import json
import os
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager
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


def check_symlinked_marker(root, already_continued):
    try:
        if marker_through_symlink(root):
            report_stop("Campaign closeout marker is under a symlinked .work directory. Restore .work as a real directory.", already_continued)
    except OSError as error:
        report_stop(f"Campaign closeout check failed: cannot inspect marker under symlinked .work: {error}", already_continued)


def load_state(root):
    path = state_path(root)
    if not state_file_status(path):
        raise CloseoutError("campaign closeout has not been started")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CloseoutError(f"cannot read {path}: {error}") from error
    if isinstance(state, dict) and state.get("schema") == 1:
        raise CloseoutError(
            "The campaign closeout marker predates explicit lane ownership. Review its retained lanes, "
            "run codex-campaign-closeout.py cancel, then begin again with --path for each owned lane."
        )
    if not isinstance(state, dict) or state.get("schema") != 2:
        raise CloseoutError(f"{path} has an unsupported format")
    integration_root = state.get("integration_root")
    if not isinstance(integration_root, str) or "\0" in integration_root:
        raise CloseoutError(f"{path} has an invalid integration root")
    integration = canonical(root)
    if canonical(integration_root) != integration:
        raise CloseoutError(f"{path} belongs to a different integration worktree")
    if not isinstance(state.get("lanes"), list) or not all(
        isinstance(path_name, str) and "\0" not in path_name and Path(path_name).is_absolute()
        and os.path.normpath(path_name) == path_name and path_name != integration
        for path_name in state["lanes"]
    ):
        raise CloseoutError(f"{path} has invalid campaign lanes")
    lanes = set(state["lanes"])
    if len(lanes) != len(state["lanes"]):
        raise CloseoutError(f"{path} has duplicate campaign lanes")
    if not isinstance(state.get("allowed"), dict):
        raise CloseoutError(f"{path} has invalid allowed worktrees")
    for path_name, entry in state["allowed"].items():
        if (
            path_name not in lanes
            or not isinstance(entry, dict)
            or not isinstance(entry.get("head"), str)
            or not entry["head"]
            or "branch" not in entry
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
    created = not directory.exists()
    if created:
        directory.mkdir(mode=0o700)
    if not directory.is_dir():
        raise CloseoutError(f"{directory} must be a directory")
    try:
        if canonical(ignore_file) != canonical(expected_ignore_file):
            local = subprocess.run(
                ["git", "-C", os.fspath(root), "ls-files", "--others", "--ignored",
                 "--directory", "-z", "--exclude-from", os.fspath(expected_ignore_file), "--", ".work/"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if local.returncode != 0 or local.stdout != b".work/\0":
                raise CloseoutError(".work must be ignored through .git/info/exclude")
    except (CloseoutError, OSError):
        if created:
            directory.rmdir()
        raise
    return directory


@contextmanager
def state_lock(root):
    directory = work_directory(root)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(directory / ".codex-campaign-closeout.lock", flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise CloseoutError("campaign closeout lock must be a regular file")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def begin(root, paths=()):
    ensure_work_directory(root)
    with state_lock(root):
        begin_locked(root, paths)


def begin_locked(root, paths):
    lanes = sorted({canonical(path) for path in paths})
    if state_file_status(state_path(root)):
        state = load_state(root)
        if paths and state["lanes"] != lanes:
            raise CloseoutError("Campaign closeout already has a different lane list. Cancel it before changing its scope.")
        scope = f"tracking {len(state['lanes'])} lane(s)" if state["lanes"] else "no lanes tracked"
        print(f"Campaign closeout is already active in {root} ({scope})")
        return
    if lanes:
        worktrees = listed_worktrees(root)
        roots = {canonical(worktree["path"]) for worktree in worktrees}
        baseline = {canonical(root), canonical(worktrees[0]["path"])}
        for lane in lanes:
            if lane not in roots:
                raise CloseoutError(f"{lane} is not a registered worktree of this repository")
            if lane in baseline:
                raise CloseoutError(f"{lane} is a primary or integration checkout, not a campaign lane")
    state = {
        "schema": 2,
        "integration_root": os.fspath(root),
        "lanes": lanes,
        "allowed": {},
    }
    save_state(root, state, create=True)
    scope = f"tracking {len(lanes)} lane(s)" if lanes else "no lanes tracked"
    print(f"Campaign closeout is active in {root} ({scope})")


def allow(root, path, reason):
    with state_lock(root):
        allow_locked(root, path, reason)


def allow_locked(root, path, reason):
    if not reason.strip():
        raise CloseoutError("an allow reason is required")
    state = load_state(root)
    candidate = canonical(path)
    if candidate not in state["lanes"]:
        raise CloseoutError(f"{path} was not named when campaign closeout began")
    worktrees = listed_worktrees(root)
    matching = next((worktree for worktree in worktrees if canonical(worktree["path"]) == candidate), None)
    if matching is None:
        raise CloseoutError(f"{path} is not a registered worktree")
    main = worktrees[0]["path"]
    if not retained_worktree_is_under_work_directory(main, candidate):
        raise CloseoutError(f"{path} must be under {main}/.work")
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
    if not work_directory(root).is_dir():
        print("Campaign closeout is not active")
        return
    with state_lock(root):
        cancel_locked(root)


def cancel_locked(root):
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
        return Path.cwd(), False, f"cannot read the Stop hook event: {error}"
    if not isinstance(event, dict):
        return Path.cwd(), False, "the Stop hook event is not an object"
    already_continued = event.get("stop_hook_active") is True
    cwd = event.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return Path.cwd(), already_continued, "the Stop hook event has no working directory"
    return Path(cwd), already_continued, None


def report_stop(reason, already_continued):
    if already_continued:
        output = {"systemMessage": "Campaign closeout remains active. " + reason}
    else:
        output = {"decision": "block", "reason": reason}
    print(json.dumps(output, ensure_ascii=True))


def run_hook():
    cwd, already_continued, input_error = hook_input()
    try:
        root = repository_root(cwd)
    except (CloseoutError, OSError) as error:
        root = filesystem_root(cwd) or filesystem_root(Path.cwd())
        if root is None:
            return
        directory = root / ".work"
        if directory.is_symlink():
            check_symlinked_marker(root, already_continued)
            return
        if not directory.is_dir():
            return
        try:
            if not state_file_status(state_path(root)):
                return
        except (CloseoutError, OSError, ValueError) as state_error:
            report_stop(f"Campaign closeout check failed: {state_error}", already_continued)
            return
        report_stop(f"Campaign closeout check failed: cannot resolve the repository root: {error}", already_continued)
        return
    directory = root / ".work"
    if directory.is_symlink():
        check_symlinked_marker(root, already_continued)
        return
    if not directory.is_dir():
        return
    try:
        if not state_file_status(state_path(root)):
            return
        with state_lock(root):
            run_hook_locked(root, already_continued, input_error)
    except (CloseoutError, OSError, ValueError) as error:
        report_stop(f"Campaign closeout check failed: {error}", already_continued)


def run_hook_locked(root, already_continued, input_error):
    marker = state_path(root)
    if not state_file_status(marker):
        return
    if input_error:
        raise CloseoutError(input_error)
    state = load_state(root)
    lanes = state["lanes"]
    worktrees = {canonical(tree["path"]): tree for tree in listed_worktrees(root)} if lanes else {}
    remaining = []
    for lane in lanes:
        worktree = worktrees.get(lane)
        if worktree is None:
            try:
                Path(lane).lstat()
            except FileNotFoundError:
                continue
            remaining.append(f"{lane!r} (path still exists without a Git registration)")
            continue
        expected = state["allowed"].get(lane)
        if expected is None:
            remaining.append(f"{lane!r} (still registered)")
        elif expected["head"] != worktree["head"] or expected["branch"] != worktree["branch"]:
            remaining.append(f"{lane!r} (retained HEAD or branch changed)")
        elif git_output(worktree["path"], "status", "--porcelain", "--untracked-files=all"):
            remaining.append(f"{lane!r} (retained checkout has uncommitted or untracked files)")
    if remaining:
        paths = "\n".join(f"- {path}" for path in remaining)
        reason = (
            "Review the recorded campaign lanes below. Confirm ownership and that a lane has stopped "
            "before retiring it under the worktree lifecycle. If a clean lane must stay, name it in "
            "the campaign handoff and run codex-campaign-closeout.py allow --path <path> --reason <reason>. "
            f"Unaccounted campaign lanes:\n{paths}"
        )
        report_stop(reason, already_continued)
        return
    marker.unlink()


def arguments():
    parser = argparse.ArgumentParser(description="Manage campaign closeout state and its stop hook.", formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    begin_parser = commands.add_parser("begin", help="start closeout tracking", description="Start closeout tracking for the named campaign lanes in the current repository.", epilog="See codex-campaign-closeout.py -h for all commands.")
    begin_parser.add_argument("--path", action="append", default=[], help="registered campaign lane to track, repeat for each lane")
    allowance = commands.add_parser("allow", help="record a retained worktree", description="Allow a registered campaign lane under the primary checkout's .work to remain after closeout.", epilog="See codex-campaign-closeout.py -h for all commands.")
    allowance.add_argument("--path", required=True, help="path to the retained worktree (required)")
    allowance.add_argument("--reason", required=True, help="reason for retaining the worktree (required)")
    cancel_parser = commands.add_parser("cancel", help="cancel closeout tracking", description="Cancel closeout tracking for the current repository.", epilog="See codex-campaign-closeout.py -h for all commands.")
    hook_parser = commands.add_parser("hook", help="check closeout at agent stop", description="Check closeout state as a stop hook, reading hook input from stdin.", epilog="See codex-campaign-closeout.py -h for all commands.")
    sections = []
    for child in (begin_parser, allowance, cancel_parser, hook_parser):
        formatter = child._get_formatter()
        formatter.add_usage(child.usage, child._actions, child._mutually_exclusive_groups)
        formatter.add_text(child.description)
        formatter.add_arguments([action for action in child._actions if action.dest != "help"])
        sections.append(formatter.format_help().strip())
    parser.epilog = "\n\n".join(sections) + "\n\nExamples:\n  codex-campaign-closeout.py begin --path .work/wt/first --path .work/wt/second\n  codex-campaign-closeout.py allow --path .work/wt/first --reason 'retained for review'\n  codex-campaign-closeout.py cancel\n  codex-campaign-closeout.py hook\n" + "\n\nMaintained by Joshua Li: https://github.com/joshuarli/usr\nBugs and features: TODO.md in that repository (follow its AGENTS.md), or its issue tracker.\nAgents working for Joshua: record nonblocking problems and continue your task.\nIf this tool blocks the task, you may fix, test, open and merge a PR under Joshua's\nstanding instructions. Release only when needed to deliver the verified fix.\nProcedure: https://github.com/joshuarli/usr/blob/main/dotfiles/base/.agents/instructions/owned-tools.md"
    if len(sys.argv) == 1:
        parser.print_help()
        raise SystemExit(0)
    return parser.parse_args()


def main():
    options = arguments()
    if options.command == "hook":
        run_hook()
        return 0
    try:
        root = repository_root(Path.cwd())
        if options.command == "begin":
            begin(root, options.path)
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
