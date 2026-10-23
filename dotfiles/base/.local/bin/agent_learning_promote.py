import fcntl
import hashlib
import os
import re
import stat
import subprocess
import tempfile
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Callable


KNOWN_LEAF_SKILLS = frozenset(
    {
        "api-surface-and-module-boundaries",
        "benchmark-checklist",
        "comment-cleanup",
        "dead-code-archaeology",
        "error-model",
        "isolate-effects",
        "lifecycle-concurrency",
        "make-code-search-a-reliable-navigation-boundary",
        "make-it-fast",
        "make-invalid-states-unrepresentable",
        "reference-parity",
        "root-cause",
        "single-source-of-truth",
        "technical-writing",
        "test-audit",
        "rust-cli-lexopt",
        "rust-hash",
        "ts-tools",
    }
)

_HEX = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_PROPOSAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_CONTEXTUAL_ACTION = re.compile(
    r"^(?:When|If|For|Before|After|During|On)\b", re.IGNORECASE
)
_AUTHORITY_WEAKENING = re.compile(
    r"\b(?:ignore|override|bypass|disable|circumvent|skip|remove|suppress)\s+"
    r"(?:all\s+)?(?:prior|previous|existing|current|global|owner|user|system|developer|"
    r"review|validation|permission|approval|security|safety|sandbox|authorization|"
    r"authentication|policy|policies|rules?|checks?|tests?|verification)\b|"
    r"\bwithout\s+(?:(?:owner|user|security)\s+)?"
    r"(?:asking|approval|permission|review|validation)\b|"
    r"\b(?:never|do\s+not|don't|avoid)\s+(?:ask|request)\s+(?:the\s+)?(?:user|owner)\b|"
    r"\b(?:always\s+approve|approve\s+all|allow\s+all|unrestricted\s+access)\b",
    re.IGNORECASE,
)
_PROTECTED_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{20,}|"
        r"github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{16,})\b",
        r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----",
        r"\bBearer\s+[A-Za-z0-9._~+/-]{12,}={0,2}",
        r"\b(?:api[_ -]?key|access[_ -]?token|password|secret|client[_ -]?secret|"
        r"private[_ -]?key|credential)\b\s*[:=]\s*\S{6,}",
        r"/(?:Users|home)/[^/\s]+(?:/|\b)",
        r"(?:^|\s)~/(?:\.ssh|\.aws|\.gnupg|\.config/(?:gcloud|credentials))\b",
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        r"\b(?:system|developer|global|root|organization|org-wide)\s+"
        r"(?:prompt|instructions?|policy|contract)\b",
        r"\b(?:approval_policy|bypassPermissions|danger-full-access|sandbox_mode)\b",
        r"\b(?:agent|harness|tool)\s+(?:permissions?|approval|sandbox)\s+"
        r"(?:policy|rules?|settings?)\b",
        r"\b(?:global|root|owner|user|system|developer)\s+"
        r"(?:permissions?|approval|sandbox|security)\s+(?:policy|rules?|settings?)\b",
    )
)

_PROPOSAL_FIELDS = frozenset(
    {
        "proposal_id",
        "action",
        "owner",
        "target",
        "target_skill",
        "observation",
        "original_action",
        "better_action",
        "future_action",
        "applicability",
        "alternatives",
        "uncertainty",
        "evidence_refs",
        "edit",
        "independent_review",
    }
)
_REVIEW_FIELDS = frozenset(
    {"approves", "risks", "owner", "does_not_weaken"}
)
_EDIT_FIELDS = frozenset({"old", "new"})
_REF_FIELDS = frozenset({"session", "position", "digest"})
_MAX_TEXT = 1600
_MAX_EDIT = 5000
_MAX_EVIDENCE = 12
_MAX_SKILL_FILE = 8000
_WORKTREE_PREFIXES = (
    "agent-learning-promote-",
    "agent-learning-rollback-",
)


class _PromotionFailure(Exception):
    pass


class _CommandFailure(_PromotionFailure):
    pass


def protected_text(text):
    if not isinstance(text, str) or len(text) > 16000:
        return True
    return bool(_AUTHORITY_WEAKENING.search(text)) or any(
        pattern.search(text) for pattern in _PROTECTED_PATTERNS
    )


def safe_action(text):
    if (
        not isinstance(text, str)
        or not text.strip()
        or len(text) > _MAX_TEXT
        or not _CONTEXTUAL_ACTION.match(text.strip())
        or not text.strip().endswith((".", "!", "?"))
        or any(unicodedata.category(char) in ("Cc", "Cf", "Zl", "Zp") for char in text)
    ):
        return False
    return not protected_text(text)


def _result(status, commit=None, reason=None):
    return {"status": status, "commit": commit, "reason": reason}


def _blocked(reason):
    return _result("blocked", reason=reason)


def _environment(overrides=None):
    env = os.environ.copy()
    for key in tuple(env):
        if key in {
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_COMMON_DIR",
            "GIT_INDEX_FILE",
            "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_PREFIX",
            "GIT_CONFIG_PARAMETERS",
        } or key.startswith(("GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            env.pop(key, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    if overrides:
        env.update(overrides)
    return env


def _command(args, cwd, *, input_bytes=None, env=None, check=True, timeout=60):
    try:
        result = subprocess.run(
            args,
            cwd=os.fspath(cwd),
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_environment(env),
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _CommandFailure("command could not complete") from exc
    if check and result.returncode != 0:
        stderr = result.stderr.decode("utf-8", "replace").strip()
        detail = stderr[:300] if stderr else "command failed"
        raise _CommandFailure(detail)
    return result


def _git(repository, *args, config=(), check=True, timeout=60):
    full = ["git", "-C", os.fspath(repository)]
    for key, value in config:
        full.extend(("-c", "{}={}".format(key, value)))
    full.extend(args)
    result = _command(full, repository, check=check, timeout=timeout)
    return result.stdout.decode("utf-8", "surrogateescape").strip()


def _git_bytes(repository, *args, config=(), check=True, timeout=60):
    full = ["git", "-C", os.fspath(repository)]
    for key, value in config:
        full.extend(("-c", "{}={}".format(key, value)))
    full.extend(args)
    return _command(full, repository, check=check, timeout=timeout).stdout


def _repository_root(repository):
    try:
        root = Path(repository).resolve(strict=True)
        prefix = _git_bytes(root, "rev-parse", "--show-prefix")
    except (OSError, _PromotionFailure) as exc:
        raise _PromotionFailure("repository is unavailable") from exc
    if prefix != b"\n":
        raise _PromotionFailure("repository must name its Git worktree root")
    return root


def _head(repository):
    value = _git(repository, "rev-parse", "--verify", "HEAD^{commit}")
    if not _HEX.fullmatch(value):
        raise _PromotionFailure("Git returned an invalid commit identifier")
    return value


def _expected_head(repository, expected_head):
    if not isinstance(expected_head, str) or not _HEX.fullmatch(expected_head):
        raise _PromotionFailure("expected_head must be a full commit identifier")
    actual = _head(repository)
    if actual != expected_head:
        raise _PromotionFailure("repository HEAD changed")
    return actual


def _worktree_clean(repository):
    result = _git_bytes(
        repository,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        config=(("core.fsmonitor", "false"), ("core.untrackedCache", "false")),
    )
    if result:
        raise _PromotionFailure("repository has local or staged changes")


def _current_branch(repository):
    branch = _git(repository, "symbolic-ref", "--quiet", "HEAD", check=False)
    if not branch.startswith("refs/heads/"):
        raise _PromotionFailure("repository HEAD is not on a branch")
    return branch


def _common_git_dir(repository):
    return Path(
        _git(repository, "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).resolve(strict=True)


@contextmanager
def _promotion_lock(repository):
    common = _common_git_dir(repository)
    lock_path = common / "agent-learning-promote.lock"
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(os.fspath(lock_path), flags, 0o600)
    except OSError as exc:
        raise _PromotionFailure("could not open promotion lock") from exc
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise _PromotionFailure("promotion lock is not a regular file")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise _PromotionFailure("another promotion is active") from exc
        yield
    finally:
        os.close(descriptor)


def _validate_proposal(proposal):
    if not isinstance(proposal, dict) or proposal.keys() - _PROPOSAL_FIELDS:
        raise _PromotionFailure("proposal has an unsupported shape")
    if proposal.get("action") != "improve":
        return None
    proposal_id = proposal.get("proposal_id")
    if not isinstance(proposal_id, str) or not _PROPOSAL_ID.fullmatch(proposal_id):
        raise _PromotionFailure("proposal_id is invalid")
    owner = proposal.get("owner")
    if (
        not isinstance(owner, str)
        or owner not in KNOWN_LEAF_SKILLS
        or proposal.get("target") != "skill"
    ):
        raise _PromotionFailure("target is outside the promotion allowlist")
    if proposal.get("target_skill") != owner:
        raise _PromotionFailure("target_skill must equal the owner skill")
    for field in (
        "observation",
        "original_action",
        "better_action",
        "future_action",
        "applicability",
        "uncertainty",
    ):
        value = proposal.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > _MAX_TEXT:
            raise _PromotionFailure("proposal is missing a bounded {}".format(field))
        if protected_text(value):
            raise _PromotionFailure("proposal narrative contains protected text")
    alternatives = proposal.get("alternatives")
    if not isinstance(alternatives, str) or not alternatives.strip() or len(alternatives) > _MAX_TEXT:
        raise _PromotionFailure("alternatives must be bounded text")
    if protected_text(alternatives):
        raise _PromotionFailure("proposal alternatives contain protected text")
    review = proposal.get("independent_review")
    if (
        not isinstance(review, dict)
        or review.keys() != _REVIEW_FIELDS
        or review.get("approves") is not True
        or review.get("risks") != []
        or review.get("owner") != owner
        or review.get("does_not_weaken") is not True
    ):
        raise _PromotionFailure("independent review did not approve the edit")
    edit = proposal.get("edit")
    if not isinstance(edit, dict) or edit.keys() != _EDIT_FIELDS:
        raise _PromotionFailure("edit must contain only old and new text")
    old = edit.get("old")
    new = edit.get("new")
    if (
        not isinstance(old, str)
        or not isinstance(new, str)
        or not old.strip()
        or len(old) > _MAX_EDIT
        or len(new) > _MAX_EDIT
    ):
        raise _PromotionFailure("edit text is empty or too large")
    if old.startswith("description: ") and new.startswith("description: "):
        added = _description_insertion(old, new)
        mode = "description"
        if len(added) > 120:
            raise _PromotionFailure("description trigger changes are limited to 120 characters")
    else:
        if new.startswith(old + "\n") or new.startswith(old + " "):
            added = new[len(old) + 1 :]
        else:
            raise _PromotionFailure("edit may only append one contextual action to existing guidance")
        mode = "paragraph"
        if "\n" in added:
            raise _PromotionFailure("appended guidance must be one line")
    if (
        not added.strip()
        or added.strip() != proposal["future_action"].strip()
        or not safe_action(added.strip())
    ):
        raise _PromotionFailure("added guidance failed the narrow safety gate")
    refs = _validate_evidence_refs(proposal.get("evidence_refs"))
    return proposal_id, owner, old, new, added, mode, refs


def _description_insertion(old, new):
    if "\n" in old or "\n" in new or "\r" in old or "\r" in new:
        raise _PromotionFailure("description edits must stay on one frontmatter line")
    prefix = "description: "
    old_value = old[len(prefix) :]
    new_value = new[len(prefix) :]
    if old_value[:1] in ('"', "'"):
        if not old_value.endswith(old_value[0]) or new_value[:1] != old_value[:1] or not new_value.endswith(old_value[0]):
            raise _PromotionFailure("description quoting must remain unchanged")
        quote = old_value[0]
        old_inner = old_value[1:-1]
        new_inner = new_value[1:-1]
    else:
        raise _PromotionFailure("description trigger edits require quoted metadata")
    if old_inner.count("Skip") != 1:
        raise _PromotionFailure("description must retain one existing Skip clause")
    skip = old_inner.index("Skip")
    before_skip = old_inner[:skip]
    skip_clause = old_inner[skip:]
    if not new_inner.startswith(before_skip) or not new_inner.endswith(skip_clause):
        raise _PromotionFailure("description refinement must preserve its existing wording")
    added = new_inner[len(before_skip) : len(new_inner) - len(skip_clause)]
    if not added or before_skip + added + skip_clause != new_inner:
        raise _PromotionFailure("description refinement must insert before Skip")
    if quote in added or "\\" in added or re.search(r"\bSkip\b", added):
        raise _PromotionFailure("description insertion contains metadata syntax")
    return added


def _validate_evidence_refs(refs):
    if not isinstance(refs, list) or len(refs) < 2 or len(refs) > _MAX_EVIDENCE:
        raise _PromotionFailure("promotion requires two or more evidence references")
    seen = set()
    for ref in refs:
        if not isinstance(ref, dict) or ref.keys() != _REF_FIELDS:
            raise _PromotionFailure("evidence reference has an unsupported shape")
        session = ref.get("session")
        position = ref.get("position")
        digest = ref.get("digest")
        if (
            not isinstance(session, str)
            or not session
            or len(session) > 256
            or type(position) is not int
            or position < 0
            or not isinstance(digest, str)
            or not _DIGEST.fullmatch(digest)
        ):
            raise _PromotionFailure("evidence reference is invalid")
        key = (session, position)
        if key in seen:
            raise _PromotionFailure("evidence references must be distinct")
        seen.add(key)
    return refs


def _verify_evidence(refs, evidence, verifier):
    if (
        not callable(verifier)
        or not isinstance(evidence, list)
        or len(evidence) != len(refs)
        or len(evidence) > _MAX_EVIDENCE
    ):
        raise _PromotionFailure("verified original evidence is required")
    records = {}
    for record in evidence:
        if not isinstance(record, dict):
            raise _PromotionFailure("evidence record has an unsupported shape")
        session = record.get("session")
        position = record.get("position")
        root_session = record.get("root_session")
        if (
            not isinstance(session, str)
            or type(position) is not int
            or not isinstance(root_session, str)
            or not root_session
            or len(root_session) > 256
        ):
            raise _PromotionFailure("evidence records need session, position, and root_session")
        key = (session, position)
        if key in records:
            raise _PromotionFailure("evidence contains duplicate session positions")
        records[key] = root_session
    root_sessions = set()
    for ref in refs:
        key = (ref["session"], ref["position"])
        if key not in records:
            raise _PromotionFailure("an evidence reference did not resolve to an original record")
        root_sessions.add(records[key])
    if len(root_sessions) < 2:
        raise _PromotionFailure("evidence must come from two independent root sessions")
    try:
        valid = verifier(refs, evidence)
    except Exception as exc:
        raise _PromotionFailure("original evidence verification failed") from exc
    if valid is not True:
        raise _PromotionFailure("original evidence verification failed")


def _ignored_worktree_path(repository, relative):
    ignored = _command(
        [
            "git",
            "-C",
            os.fspath(repository),
            "check-ignore",
            "--verbose",
            "--no-index",
            "-z",
            "--stdin",
        ],
        repository,
        input_bytes=os.fsencode(relative) + b"\0",
        check=False,
    )
    if ignored.returncode != 0:
        raise _PromotionFailure(".work/wt is not ignored by .git/info/exclude")
    fields = ignored.stdout.split(b"\0")
    if len(fields) < 4 or not os.fsdecode(fields[0]).replace("\\", "/").endswith("/info/exclude"):
        raise _PromotionFailure(".work/wt must be ignored by .git/info/exclude")


def _safe_worktree_root(repository):
    relative = Path(".work") / "wt" / (_WORKTREE_PREFIXES[0] + "check")
    _ignored_worktree_path(repository, relative.as_posix())
    root = repository / ".work"
    for path in (root, root / "wt"):
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            path.mkdir(mode=0o700)
            mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise _PromotionFailure(".work/wt must contain real directories")
    return root / "wt"


def _registered_worktree(repository, path):
    try:
        top = Path(_git(path, "rev-parse", "--show-toplevel")).resolve(strict=True)
        git_dir = Path(
            _git(path, "rev-parse", "--path-format=absolute", "--git-dir")
        ).resolve(strict=True)
        common = _common_git_dir(repository)
        managed_root = common / "worktrees"
        git_dir.relative_to(managed_root.resolve(strict=True))
        return top == path.resolve(strict=True)
    except (OSError, ValueError, _PromotionFailure):
        return False


def _remove_worktree(repository, path):
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise _PromotionFailure("promotion worktree path is not a real directory")
    if _registered_worktree(repository, path):
        _git(repository, "worktree", "remove", "--force", "--", os.fspath(path))
    else:
        try:
            path.rmdir()
        except OSError as exc:
            raise _PromotionFailure("unrecognized data occupies a promotion worktree path") from exc


def _cleanup_stale_worktrees(repository, worktree_root):
    for path in worktree_root.iterdir():
        if path.name.startswith(_WORKTREE_PREFIXES):
            _remove_worktree(repository, path)


def _staging_worktree(repository, expected_head, worktree_root, operation, identity):
    prefix = "agent-learning-{}-".format(operation)
    if operation not in ("promote", "rollback"):
        raise _PromotionFailure("unsupported staging operation")
    _cleanup_stale_worktrees(repository, worktree_root)
    path = worktree_root / (prefix + identity)
    if path.exists() or path.is_symlink():
        raise _PromotionFailure("promotion worktree path is occupied")
    try:
        _git(
            repository,
            "worktree",
            "add",
            "--detach",
            os.fspath(path),
            expected_head,
            config=(("core.hooksPath", "/dev/null"),),
        )
    except _PromotionFailure:
        if path.exists():
            _remove_worktree(repository, path)
        raise
    if not _registered_worktree(repository, path):
        _remove_worktree(repository, path)
        raise _PromotionFailure("Git did not register the promotion worktree")
    return path


def _skill_file(worktree, skill):
    relative = Path("dotfiles/base/.agents/skills") / skill / "SKILL.md"
    current = worktree
    for component in relative.parts:
        current = current / component
        try:
            mode = current.lstat().st_mode
        except OSError as exc:
            raise _PromotionFailure("target skill file is missing") from exc
        if stat.S_ISLNK(mode):
            raise _PromotionFailure("target skill path contains a symlink")
    if not stat.S_ISREG(mode):
        raise _PromotionFailure("target skill file is not regular")
    return relative, current


def _edit_is_paragraph(text, old):
    if text.count(old) != 1:
        raise _PromotionFailure("old guidance must match exactly once")
    start = text.index(old)
    end = start + len(old)
    if (start and text[max(0, start - 2) : start] != "\n\n") or (
        end < len(text) and not text[end:].startswith("\n\n")
    ):
        raise _PromotionFailure("edit must select a complete paragraph")
    if "\n\n" in old or "\r" in old or "\x00" in old:
        raise _PromotionFailure("edit paragraph has unsupported boundaries")
    for line in old.splitlines():
        if line.startswith(("#", "- ", "* ", ">", "|")) or re.match(r"^\d+\. ", line):
            raise _PromotionFailure("headings, lists, and tables are protected")
    if text.startswith("---\n"):
        frontmatter_end = text.find("\n---\n", 4)
        if frontmatter_end < 0 or start < frontmatter_end + 5:
            raise _PromotionFailure("frontmatter is protected")
    return start


def _edit_is_description(text, old):
    if not text.startswith("---\n"):
        raise _PromotionFailure("description frontmatter is missing")
    frontmatter_end = text.find("\n---\n", 4)
    if frontmatter_end < 0:
        raise _PromotionFailure("description frontmatter is malformed")
    end = frontmatter_end + 1
    frontmatter = text[:end]
    if frontmatter.count(old) != 1:
        raise _PromotionFailure("old description must match exactly once in frontmatter")
    start = frontmatter.index(old)
    if (start and text[start - 1] != "\n") or (start + len(old) < end and text[start + len(old)] != "\n"):
        raise _PromotionFailure("description edit must select the complete metadata line")
    return start


def _replace_atomically(path, contents):
    original_stat = path.lstat()
    if stat.S_ISLNK(original_stat.st_mode) or not stat.S_ISREG(original_stat.st_mode):
        raise _PromotionFailure("target skill file changed type")
    descriptor, temporary = tempfile.mkstemp(prefix=".agent-learning-", dir=os.fspath(path.parent))
    try:
        os.fchmod(descriptor, stat.S_IMODE(original_stat.st_mode))
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _run_skill_check(worktree):
    checker = worktree / "dotfiles/skills-check.sh"
    skills = worktree / "dotfiles/base/.agents/skills"
    try:
        checker_mode = checker.lstat().st_mode
        skills_mode = skills.lstat().st_mode
        mdtool_mode = (worktree / "dotfiles/base/.local/bin/mdtool").lstat().st_mode
        if (
            stat.S_ISLNK(checker_mode)
            or not stat.S_ISREG(checker_mode)
            or stat.S_ISLNK(skills_mode)
            or not stat.S_ISDIR(skills_mode)
            or stat.S_ISLNK(mdtool_mode)
            or not stat.S_ISREG(mdtool_mode)
        ):
            raise _PromotionFailure("trusted skill checker paths are not regular project files")
    except OSError as exc:
        raise _PromotionFailure("trusted skill checker is unavailable") from exc
    result = _command(
        ["sh", os.fspath(checker), os.fspath(skills)],
        worktree,
        check=False,
        timeout=60,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout).decode("utf-8", "replace").strip()
        raise _PromotionFailure(
            "trusted skill checker rejected the candidate"
            + (": " + message[:240] if message else "")
        )


def _edit_digest(old, new):
    return hashlib.sha256((old + "\0" + new).encode("utf-8")).hexdigest()


def _commit_message(repository, commit):
    return _git(repository, "show", "-s", "--format=%B", commit)


def _promotion_commit_for(repository, proposal_id, edit_digest, skill, new):
    search = "Learning-Proposal: " + proposal_id
    output = _git(
        repository,
        "log",
        "HEAD",
        "--format=%H%x00%B",
        "--fixed-strings",
        "--grep=" + search,
        check=True,
    )
    pieces = output.split("\0")
    matches = []
    for index in range(0, len(pieces) - 1, 2):
        commit = pieces[index].strip()
        message = pieces[index + 1]
        if any(line.strip() == search for line in message.splitlines()):
            matches.append((commit, message))
    if len(matches) > 1:
        raise _PromotionFailure("proposal provenance is ambiguous")
    if not matches:
        return None
    commit, message = matches[0]
    if "Learning-Edit: " + edit_digest not in message.splitlines():
        raise _PromotionFailure("proposal ID already belongs to a different edit")
    parents = _git(repository, "rev-list", "--parents", "-n", "1", commit).split()
    if len(parents) != 2:
        raise _PromotionFailure("promotion provenance is not a single-parent commit")
    changed = _git_bytes(
        repository,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        "-z",
        commit,
    ).split(b"\0")
    paths = [item.decode("utf-8", "surrogateescape") for item in changed if item]
    expected_path = "dotfiles/base/.agents/skills/{}/SKILL.md".format(skill)
    if paths != [expected_path]:
        raise _PromotionFailure("proposal provenance does not match its skill target")
    _relative, current_path = _skill_file(repository, skill)
    current = current_path.read_text(encoding="utf-8")
    if new not in current:
        raise _PromotionFailure("promotion guidance is no longer present at HEAD")
    rollback_search = "Reverts-Learning-Promotion: " + commit
    reverted = _git(
        repository,
        "log",
        "HEAD",
        "--format=%H%x00%B",
        "--fixed-strings",
        "--grep=" + rollback_search,
        check=True,
    )
    if any(line.strip() == rollback_search for line in reverted.splitlines()):
        raise _PromotionFailure("proposal has already been rolled back")
    return commit


def _commit_candidate(worktree, message, trailers):
    config = (
        ("core.hooksPath", "/dev/null"),
        ("core.fsmonitor", "false"),
        ("commit.gpgsign", "false"),
        ("user.name", "Learning Promotion"),
        ("user.email", "agent-learning-promotion@localhost"),
    )
    _git(worktree, "add", "--", message[1], config=config)
    staged = _git_bytes(worktree, "diff", "--cached", "--name-only", "-z", config=config)
    paths = [item.decode("utf-8", "surrogateescape") for item in staged.split(b"\0") if item]
    if paths != [message[1]]:
        raise _PromotionFailure("candidate index contains an unexpected path")
    if _git_bytes(worktree, "diff", "--name-only", "-z", config=config):
        raise _PromotionFailure("candidate has unstaged changes")
    args = ["commit", "--no-gpg-sign", "-m", message[0]]
    for trailer in trailers:
        args.extend(("-m", trailer))
    _git(worktree, *args, config=config)
    return _head(worktree)


def _integrate(repository, candidate_commit, expected_head, branch):
    if _head(repository) != expected_head:
        raise _PromotionFailure("repository HEAD changed before integration")
    if _current_branch(repository) != branch:
        raise _PromotionFailure("repository branch changed before integration")
    _worktree_clean(repository)
    _git(
        repository,
        "merge",
        "--ff-only",
        "--no-edit",
        candidate_commit,
        config=(("core.hooksPath", "/dev/null"),),
    )
    if _head(repository) != candidate_commit:
        raise _PromotionFailure("fast-forward integration did not reach the candidate commit")


def promote(
    repository: Path,
    proposal: dict,
    evidence: list,
    expected_head: str,
    *,
    verify_evidence: Callable[[list, list], bool],
) -> dict:
    if not isinstance(proposal, dict):
        return _blocked("proposal has an unsupported shape")
    action = proposal.get("action")
    if proposal.get("target") == "memory":
        return _result("not_applicable", reason="memory targets use the parent memory path")
    if action in ("defer", "reject", "supersede"):
        return _result("not_applicable", reason="proposal action is not improve")
    if action != "improve":
        return _blocked("proposal action is unsupported")
    try:
        proposal_id, skill, old, new, _added, edit_mode, refs = _validate_proposal(proposal)
        _verify_evidence(refs, evidence, verify_evidence)
        root = _repository_root(repository)
        with _promotion_lock(root):
            _worktree_clean(root)
            _current_branch(root)
            existing = _promotion_commit_for(
                root,
                proposal_id,
                _edit_digest(old, new),
                skill,
                new,
            )
            if existing:
                return _result("promoted", existing, "proposal was already integrated")
            head = _expected_head(root, expected_head)
            branch = _current_branch(root)
            worktree_root = _safe_worktree_root(root)
            worktree = _staging_worktree(
                root, head, worktree_root, "promote", proposal_id
            )
            try:
                relative, path = _skill_file(worktree, skill)
                original = path.read_bytes()
                if len(original) > _MAX_SKILL_FILE:
                    raise _PromotionFailure("skill file exceeds the promotion size limit")
                try:
                    text = original.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise _PromotionFailure("skill file is not UTF-8") from exc
                if edit_mode == "description":
                    start = _edit_is_description(text, old)
                else:
                    start = _edit_is_paragraph(text, old)
                updated = text[:start] + new + text[start + len(old) :]
                encoded = updated.encode("utf-8")
                if len(encoded) > _MAX_SKILL_FILE:
                    raise _PromotionFailure("candidate skill file exceeds the size limit")
                _replace_atomically(path, encoded)
                _run_skill_check(worktree)
                edit_digest = _edit_digest(old, new)
                candidate_commit = _commit_candidate(
                    worktree,
                    ("docs(skills): improve skill guidance", relative.as_posix()),
                    (
                        "Learning-Proposal: " + proposal_id,
                        "Learning-Edit: " + edit_digest,
                    ),
                )
                parents = _git(worktree, "rev-list", "--parents", "-n", "1", candidate_commit).split()
                if parents != [candidate_commit, head]:
                    raise _PromotionFailure("candidate commit does not directly follow expected_head")
                _integrate(root, candidate_commit, head, branch)
                return _result("promoted", candidate_commit)
            finally:
                _remove_worktree(root, worktree)
    except _PromotionFailure as exc:
        return _blocked(str(exc))
    except (OSError, ValueError, UnicodeError) as exc:
        return _blocked("promotion failed: {}".format(type(exc).__name__))


def rollback(repository: Path, commit: str, expected_head: str) -> dict:
    try:
        if not isinstance(commit, str) or not _HEX.fullmatch(commit):
            raise _PromotionFailure("promotion commit is invalid")
        root = _repository_root(repository)
        with _promotion_lock(root):
            head = _expected_head(root, expected_head)
            if commit != head:
                raise _PromotionFailure("rollback is allowed only for the current HEAD commit")
            branch = _current_branch(root)
            _worktree_clean(root)
            message = _commit_message(root, commit)
            proposal_lines = [
                line.partition(": ")[2]
                for line in message.splitlines()
                if line.startswith("Learning-Proposal: ")
            ]
            edit_lines = [
                line.partition(": ")[2]
                for line in message.splitlines()
                if line.startswith("Learning-Edit: ")
            ]
            if (
                len(proposal_lines) != 1
                or not _PROPOSAL_ID.fullmatch(proposal_lines[0])
                or len(edit_lines) != 1
                or not _DIGEST.fullmatch(edit_lines[0])
            ):
                raise _PromotionFailure("current HEAD is not a learning promotion commit")
            changed = _git_bytes(
                root,
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                "-z",
                commit,
            ).split(b"\0")
            paths = [item.decode("utf-8", "surrogateescape") for item in changed if item]
            if len(paths) != 1:
                raise _PromotionFailure("promotion commit changed an unexpected number of paths")
            target = paths[0]
            match = re.fullmatch(
                r"dotfiles/base/\.agents/skills/([a-z0-9][a-z0-9-]*)/SKILL\.md",
                target,
            )
            if not match or match.group(1) not in KNOWN_LEAF_SKILLS:
                raise _PromotionFailure("promotion commit target is outside the rollback allowlist")
            parents = _git(root, "rev-list", "--parents", "-n", "1", commit).split()
            if len(parents) != 2:
                raise _PromotionFailure("promotion commit is not a single-parent commit")
            worktree_root = _safe_worktree_root(root)
            worktree = _staging_worktree(
                root,
                head,
                worktree_root,
                "rollback",
                commit[:16],
            )
            try:
                _git(
                    worktree,
                    "revert",
                    "--no-commit",
                    commit,
                    config=(("core.hooksPath", "/dev/null"), ("user.name", "Learning Promotion"), ("user.email", "agent-learning-promotion@localhost")),
                )
                _run_skill_check(worktree)
                _git(worktree, "add", "--", target)
                staged = _git_bytes(worktree, "diff", "--cached", "--name-only", "-z")
                paths = [item.decode("utf-8", "surrogateescape") for item in staged.split(b"\0") if item]
                if paths != [target] or _git_bytes(worktree, "diff", "--name-only", "-z"):
                    raise _PromotionFailure("rollback candidate has unexpected changes")
                _git(
                    worktree,
                    "-c",
                    "core.hooksPath=/dev/null",
                    "-c",
                    "commit.gpgsign=false",
                    "-c",
                    "user.name=Learning Promotion",
                    "-c",
                    "user.email=agent-learning-promotion@localhost",
                    "commit",
                    "--no-gpg-sign",
                    "-m",
                    "revert(skills): restore prior skill guidance",
                    "-m",
                    "Reverts-Learning-Promotion: " + commit,
                )
                revert_commit = _head(worktree)
                parents = _git(worktree, "rev-list", "--parents", "-n", "1", revert_commit).split()
                if parents != [revert_commit, head]:
                    raise _PromotionFailure("rollback commit does not directly follow expected_head")
                _integrate(root, revert_commit, head, branch)
                return _result("reverted", revert_commit)
            finally:
                _remove_worktree(root, worktree)
    except _PromotionFailure as exc:
        return _blocked(str(exc))
    except (OSError, ValueError, UnicodeError) as exc:
        return _blocked("rollback failed: {}".format(type(exc).__name__))
