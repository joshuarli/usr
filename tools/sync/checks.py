"""Repository check registry: the suite, the changed-file planner and the docs table share it."""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Literal, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
DOC = "docs/development.md"
BEGIN = "<!-- checks:begin -->"
END = "<!-- checks:end -->"
TAIL = 4000

Platform = Literal["any", "darwin", "linux"]


@dataclass(frozen=True)
class Area:
    label: str
    note: str = ""


@dataclass(frozen=True)
class Check:
    id: str
    areas: tuple[Area, ...]
    argv: tuple[str, ...]
    covers: tuple[str, ...]
    cwd: str = "."
    tmpdir: bool = False
    needs: tuple[str, ...] = ()
    platform: Platform = "any"
    per_file: bool = False
    sh_shebang: bool = False
    note: str = ""


def py(*args: str) -> tuple[str, ...]:
    return ("python3", "-I", *args)


SBX = Area("`dotfiles/base/.local/bin/sbx` or its policy spec")
LINKS = Area("Python link discovery, planning or apply")
DECIDE = Area("`tools/decide`")
DOCTOR = Area("`sync doctor` and default tool inventory")
GUARD = Area("Pi Git tool-call guard")
PI_RELEASE = Area("Pi release pin, installer, launcher, or SDK closure")
PI_BRIDGE_INSTALL = Area("Pi bridge installation or MCP registration")
COMPANIONS = Area("Intercom companion installation or MCP/plugin registration")
BRIDGE = Area("`tools/pi-subagent-bridge`", "run `./dev-install.sh` once first")
PI_PROFILE = Area("Pi profile and extensions")
DAG = Area("`sync` DAG/bootstrap")
INSTALLER = Area("Private tool installer")
UNINSTALL = Area("`sync uninstall`")
KACHE = Area("`kache` setup")
PINACT = Area("`pinact` and workflow pins")
YTDLP = Area("`yt-dlp` shim")
PK = Area("`pk` process picker")
DSH = Area("DeepSeek launcher")
CLAUDE_API = Area("Claude API launcher")
GHOSTTY = Area("`ghostty-fda-check`")
SKILLS = Area("a skill or agent definition", "`node tools/skills/skills.ts generate` refreshes invocation adapters; use the focused check for other agent configuration")
POLICY = Area("model routes, native Pi policy, or generated policy blocks", "use `make generate` to refresh projections")
ORCHESTRATE = Area("`orchestrate` skill")
INSTRUCTIONS = Area("instruction profiles and their harness adapters")
HOOKS = Area("git hooks and worktree helpers")
ZSH = Area("zsh shim")
MDTOOL = Area("a hook or `mdtool`")
PERF_GATE = Area("`perf-gate-ready`")
SETUP_LINUX = Area("`host/setup-linux`")
MACOS_SYNC = Area("macOS sync side effects")
POWER = Area("Linux `power-policy` or its test harness")
SHELL = Area("a shell script")
PYTHON = Area("a Python script", "both read `ruff.toml` and `ty.toml`")
MACOS_TOOLS = Area("macOS tools")
MARKDOWN = Area("Markdown", "see below for `mdtool refs`, `router`, and `check`")

SKILL_PATHS = ("dotfiles/base/.agents/skills/", ".agents/skills/", "tools/skills/", "SKILLS.md")
CONTRACTS = ("dotfiles/base/.agents/instructions/", "dotfiles/base/.codex/AGENTS.md", "dotfiles/base/.codex/AGENTS.override.md", "dotfiles/base/.claude/CLAUDE.md")
GENERATED_POLICY = ("dotfiles/base/.agents/instructions/lean.md", "dotfiles/base/.codex/AGENTS.md", "dotfiles/base/.agents/skills/orchestrate/SKILL.md",
                    "dotfiles/base/.pi/agent/", "dotfiles/base/.config/opencode/opencode.json", "tools/pi-subagent-bridge/README.md", "docs/pi.md", "docs/agent-setup.md")
LINK_CODE = ("tools/sync/links.py", "tools/sync/link_plan.py", "tools/sync/link_apply.py", "tools/sync/link_recovery.py", "tools/sync/ownership.py")
SYNC_CORE = ("sync", "tools/sync/main.py", "tools/sync/dag.py", "tools/sync/bootstrap.sh")
WORKER_REG = ("tools/sync/claude-worker.py", "tools/sync/pi-worker.py", "tools/sync/opencode-worker.py", "tools/pi/sync_bridge.py")

REGISTRY: tuple[Check, ...] = (
    Check("sbx", (SBX,), py("dotfiles/sbx-test.py"), ("dotfiles/base/.local/bin/sbx", "dotfiles/sbx-test.py", "docs/sbx-spec.md"), tmpdir=True),
    Check("sbx-live", (SBX,), py("dotfiles/sbx-test.py", "--live"), ("dotfiles/base/.local/bin/sbx", "dotfiles/sbx-test.py", "docs/sbx-spec.md"), tmpdir=True, platform="darwin"),
    Check("sync-links", (LINKS,), py("tools/sync/test_links.py"), (*LINK_CODE, "tools/sync/test_links.py")),
    Check("sync-main", (LINKS, DAG), py("tools/sync/test_main.py"), (*LINK_CODE, *SYNC_CORE, "tools/sync/test_main.py")),
    Check("sync-integration", (LINKS, DAG), py("tools/sync/test_integration.py"), (*LINK_CODE, *SYNC_CORE, "tools/sync/test_integration.py")),
    Check("decide", (DECIDE,), py("tools/decide/tests/test_decide.py"), ("tools/decide/", "dotfiles/base/.local/bin/decide", *CONTRACTS, "dotfiles/base/.agents/skills/do/", "dotfiles/base/.agents/skills/orchestrate/"), tmpdir=True),
    Check("decide-ruff", (DECIDE,), ("uvx", "ruff", "check", "tools/decide/src/decide.py", "tools/decide/tests/test_decide.py"), ("tools/decide/",), needs=("uvx",)),
    Check("doctor", (DOCTOR, DAG), ("sh", "dotfiles/doctor-test.sh"), ("dotfiles/doctor", "dotfiles/doctor-test.sh", "tools/sync/installer.py", "tools/sync/main.py", "sync")),
    Check("doctor-sh-syntax", (DOCTOR,), ("sh", "-n", "dotfiles/doctor"), ("dotfiles/doctor",)),
    Check("doctor-test-sh-syntax", (DOCTOR,), ("sh", "-n", "dotfiles/doctor-test.sh"), ("dotfiles/doctor-test.sh",)),
    Check("doctor-dash-syntax", (DOCTOR,), ("dash", "-n", "dotfiles/doctor"), ("dotfiles/doctor",), needs=("dash",)),
    Check("doctor-test-dash-syntax", (DOCTOR,), ("dash", "-n", "dotfiles/doctor-test.sh"), ("dotfiles/doctor-test.sh",), needs=("dash",)),
    Check("pi-git-guard", (GUARD,), ("node", "dotfiles/pi-git-guard-test.mjs"), ("dotfiles/pi-git-guard-test.mjs", "dotfiles/base/.pi/agent/extensions/git-guard"), needs=("node",), note="no Pi login or network"),
    Check("pi-release-install", (PI_RELEASE,), py("tools/pi/test_release_install.py"), ("tools/pi/",), tmpdir=True),
    Check("pi-offline", (PI_RELEASE,), py("tools/pi/test_offline.py"), ("tools/pi/",), tmpdir=True),
    Check("pi-sync-bridge-offline", (PI_BRIDGE_INSTALL,), py("tools/pi/test_sync_bridge_offline.py"), (*WORKER_REG, "tools/pi/test_sync_bridge_offline.py"), note="in a disposable checkout"),
    Check("claude-worker", (PI_BRIDGE_INSTALL,), py("tools/sync/claude-worker-test.py"), ("tools/sync/claude-worker.py", "tools/sync/claude-worker-test.py")),
    Check("pi-worker", (PI_BRIDGE_INSTALL,), py("tools/sync/pi-worker-test.py"), ("tools/sync/pi-worker.py", "tools/sync/pi-worker-test.py")),
    Check("opencode-worker", (PI_BRIDGE_INSTALL,), py("tools/sync/opencode-worker-test.py"), ("tools/sync/opencode-worker.py", "tools/sync/opencode-worker-test.py")),
    Check("companions", (COMPANIONS,), py("tools/sync/test_companions.py"),
          ("tools/sync/companions.py", "tools/sync/test_companions.py", "tools/sync/pi_release.py",
           "tools/sync/pi_offline.py", "tools/pi/runtime.pin.json"), tmpdir=True),
    Check("bridge", (BRIDGE,), ("npm", "test"), ("tools/pi-subagent-bridge/",), cwd="tools/pi-subagent-bridge", tmpdir=True, needs=("npm",)),
    Check("pi-profile", (PI_PROFILE,), py("dotfiles/pi-test.py"), ("dotfiles/base/.pi/", "dotfiles/pi-test.py", "tools/policy/policy.generated.json", "dotfiles/base/.agents/skills/orchestrate/")),
    Check("pi-extensions", (PI_PROFILE,), py("tools/sync/test_pi_extensions.py"), ("tools/sync/pi_extensions.py", "tools/sync/test_pi_extensions.py", "dotfiles/base/.pi/")),
    Check("sync-dag", (DAG,), py("tools/sync/test_dag.py"), ("tools/sync/dag.py", "tools/sync/test_dag.py")),
    Check("sync-sh-syntax", (DAG,), ("sh", "-n", "sync"), ("sync",)),
    Check("sync-launcher", (DAG,), py("tools/sync/test_launcher.py"), (*SYNC_CORE, "tools/sync/installer.py", "tools/sync/pi_release.py", "tools/sync/test_launcher.py")),
    Check("installer", (INSTALLER,), py("tools/sync/test_installer.py"), ("tools/sync/installer.py", "tools/sync/test_installer.py", "tools/sync/tools.json")),
    Check("ffmpeg-runtime", (INSTALLER,), py("tools/sync/test_ffmpeg_runtime.py"), ("tools/sync/ffmpeg_runtime.py", "tools/sync/test_ffmpeg_runtime.py", "tools/sync/installer.py")),
    Check("bootstrap", (INSTALLER,), ("sh", "tools/sync/bootstrap-test.sh"), ("tools/sync/bootstrap.sh", "tools/sync/bootstrap-test.sh")),
    Check("bootstrap-sh-syntax", (INSTALLER,), ("sh", "-n", "tools/sync/bootstrap.sh"), ("tools/sync/bootstrap.sh",)),
    Check("bootstrap-shellcheck", (INSTALLER,), ("shellcheck", "-s", "sh", "tools/sync/bootstrap.sh"), ("tools/sync/bootstrap.sh",), needs=("shellcheck",)),
    Check("uninstall", (UNINSTALL,), py("tools/sync/test_uninstall.py"), ("tools/sync/uninstall.py", "tools/sync/test_uninstall.py")),
    Check("kache", (KACHE,), py("tools/sync/test_kache.py"), ("tools/sync/test_kache.py", "tools/sync/main.py", "dotfiles/base/.local/bin/setup-kache")),
    Check("pinact", (PINACT,), py("tools/pinact/test_pinact.py"), ("tools/pinact/", "dotfiles/base/.local/bin/pinact"), tmpdir=True),
    Check("pinact-yaml", (PINACT,), py("tools/pinact/tests/test_yaml.py"), ("tools/pinact/",), tmpdir=True),
    Check("pinact-lint-rules", (PINACT,), py("tools/pinact/tests/test_lint_rules.py"), ("tools/pinact/",), tmpdir=True),
    Check("pinact-expressions", (PINACT,), py("tools/pinact/tests/test_expressions.py"), ("tools/pinact/",), tmpdir=True),
    Check("pinact-security", (PINACT,), py("tools/pinact/tests/test_security.py"), ("tools/pinact/",), tmpdir=True),
    Check("pinact-fix", (PINACT,), py("tools/pinact/tests/test_fix.py"), ("tools/pinact/",), tmpdir=True),
    Check("pinact-pins", (PINACT,), py("dotfiles/base/.local/bin/pinact", "--check"), (".github/workflows/", "tools/pinact/", "dotfiles/base/.local/bin/pinact")),
    Check("yt-dlp", (YTDLP,), ("sh", "dotfiles/yt-dlp-shim-test.sh"), ("dotfiles/base/.local/bin/yt-dlp", "dotfiles/yt-dlp-shim-test.sh")),
    Check("yt-dlp-shellcheck", (YTDLP,), ("shellcheck", "-s", "sh", "dotfiles/base/.local/bin/yt-dlp", "dotfiles/yt-dlp-shim-test.sh"), ("dotfiles/base/.local/bin/yt-dlp", "dotfiles/yt-dlp-shim-test.sh"), needs=("shellcheck",)),
    Check("pk", (PK,), py("dotfiles/pk-test.py"), ("dotfiles/base/.local/bin/pk", "dotfiles/pk-test.py")),
    Check("pk-sh-syntax", (PK,), ("sh", "-n", "dotfiles/base/.local/bin/pk"), ("dotfiles/base/.local/bin/pk",)),
    Check("pk-dash-syntax", (PK,), ("dash", "-n", "dotfiles/base/.local/bin/pk"), ("dotfiles/base/.local/bin/pk",), needs=("dash",)),
    Check("pk-shellcheck", (PK,), ("shellcheck", "-s", "sh", "dotfiles/base/.local/bin/pk"), ("dotfiles/base/.local/bin/pk",), needs=("shellcheck",)),
    Check("dsh", (DSH,), ("sh", "dotfiles/dsh-launcher-test.sh"), ("dotfiles/base/.local/bin/dsh", "dotfiles/dsh-launcher-test.sh")),
    Check("dsh-shellcheck", (DSH,), ("shellcheck", "-s", "sh", "dotfiles/base/.local/bin/dsh", "dotfiles/dsh-launcher-test.sh"), ("dotfiles/base/.local/bin/dsh", "dotfiles/dsh-launcher-test.sh"), needs=("shellcheck",)),
    Check("claude-api", (CLAUDE_API,), ("sh", "dotfiles/claude-api-test.sh"), ("dotfiles/base/.local/bin/claude-api", "dotfiles/claude-api-test.sh")),
    Check("claude-api-shellcheck", (CLAUDE_API,), ("shellcheck", "-s", "sh", "dotfiles/base/.local/bin/claude-api", "dotfiles/claude-api-test.sh"), ("dotfiles/base/.local/bin/claude-api", "dotfiles/claude-api-test.sh"), needs=("shellcheck",)),
    Check("ghostty-fda", (GHOSTTY,), ("sh", "dotfiles/ghostty-fda-test.sh"), ("dotfiles/base/.local/bin/ghostty-fda-check", "dotfiles/ghostty-fda-test.sh")),
    Check("ghostty-fda-shellcheck", (GHOSTTY,), ("shellcheck", "-s", "sh", "dotfiles/base/.local/bin/ghostty-fda-check", "dotfiles/ghostty-fda-test.sh"), ("dotfiles/base/.local/bin/ghostty-fda-check", "dotfiles/ghostty-fda-test.sh"), needs=("shellcheck",)),
    Check("skills", (SKILLS,), ("node", "tools/skills/skills.ts", "check"), SKILL_PATHS, needs=("node",)),
    Check("project-skills", (SKILLS,), ("node", "tools/skills/skills.ts", "check", "--root", ".agents/skills"), SKILL_PATHS, needs=("node",)),
    Check("skills-tool", (SKILLS,), ("node", "--test", "tools/skills/skills.test.ts"), ("tools/skills/",), needs=("node",)),
    Check("skills-campaign", (SKILLS,), py("dotfiles/skills-campaign-test.py"), (*SKILL_PATHS, "dotfiles/skills-campaign-test.py", "dotfiles/skill-evals/", "dotfiles/base/.agents/instructions/bootstrap.md")),
    Check("policy-generated", (POLICY,), ("node", "tools/policy/generate.ts", "--check"), ("tools/policy/", "tools/pi-subagent-bridge/src/policy.ts", "tools/pi-subagent-bridge/src/tier-policy.ts", *GENERATED_POLICY), needs=("node",)),
    Check("policy-generator", (POLICY,), ("node", "--test", "tools/policy/generate.test.ts"), ("tools/policy/",), needs=("node",)),
    Check("orchestrate", (ORCHESTRATE,), py("dotfiles/orchestrate-test.py"), ("dotfiles/base/.agents/skills/orchestrate/", "dotfiles/orchestrate-test.py", *CONTRACTS)),
    Check("instructions", (INSTRUCTIONS,), py("dotfiles/instructions-test.py"), (*CONTRACTS, "dotfiles/base/.local/bin/agent-instructions.py", "dotfiles/instructions-test.py"), tmpdir=True),
    Check("reset-agents", (HOOKS,), ("sh", "dotfiles/reset-agents-test.sh"), ("dotfiles/base/.local/bin/reset-agents", "dotfiles/base/.local/bin/reset-agent-home", "dotfiles/reset-agents-test.sh")),
    Check("pre-push", (HOOKS,), ("sh", "pre-push-test.sh"), ("dotfiles/base/.config/git/hooks/", "dotfiles/pre-push-test.sh"), cwd="dotfiles"),
    Check("worktree-remove", (HOOKS,), ("sh", "worktree-remove-test.sh"), ("dotfiles/base/.local/bin/worktree-remove", "dotfiles/worktree-remove-test.sh"), cwd="dotfiles"),
    Check("worktree-retire", (HOOKS,), py("dotfiles/worktree-retire-test.py"), ("dotfiles/base/.local/bin/worktree-retire", "dotfiles/worktree-retire-test.py")),
    Check("zsh-shim", (ZSH,), ("sh", "zsh-shim-test.sh"), ("dotfiles/darwin/.local/bin/zsh", "dotfiles/zsh-shim-test.sh"), cwd="dotfiles"),
    Check("mdtool-selftest", (MDTOOL,), py("tools/mdtool/src/mdtool.py", "selftest"), ("tools/mdtool/", "dotfiles/base/.local/bin/mdtool")),
    Check("mdtool-suite", (MDTOOL,), ("sh", "tools/mdtool/tests/mdtool-test.sh"), ("tools/mdtool/src/", "tools/mdtool/tests/mdtool-test.sh", "dotfiles/base/.local/bin/mdtool")),
    Check("mdtool-hook-test", (MDTOOL,), ("sh", "{file}"), ("tools/mdtool/tests/*-test.sh",), per_file=True),
    Check("perf-gate-ready", (PERF_GATE,), ("sh", "dotfiles/perf-gate-ready-test.sh"), ("dotfiles/base/.local/bin/perf-gate-ready", "dotfiles/perf-gate-ready-test.sh")),
    Check("perf-gate-ready-dash", (PERF_GATE,), ("dash", "dotfiles/perf-gate-ready-test.sh"), ("dotfiles/base/.local/bin/perf-gate-ready", "dotfiles/perf-gate-ready-test.sh"), needs=("dash",)),
    Check("setup-linux", (SETUP_LINUX,), ("sh", "host/setup-linux-test.sh"), ("host/setup-linux", "host/setup-linux-test.sh")),
    Check("setup-linux-shellcheck", (SETUP_LINUX,), ("shellcheck", "-s", "sh", "host/setup-linux", "host/setup-linux-test.sh"), ("host/setup-linux", "host/setup-linux-test.sh"), needs=("shellcheck",)),
    Check("macos-sync", (MACOS_SYNC,), py("host/macos/sync-test.py"), ("host/macos/", "tools/sync/main.py")),
    Check("power-policy", (POWER,), ("sh", "dotfiles/power-policy-test.sh"), ("dotfiles/linux/.local/bin/power-policy", "dotfiles/power-policy-test.sh")),
    Check("power-policy-dash", (POWER,), ("dash", "dotfiles/power-policy-test.sh"), ("dotfiles/linux/.local/bin/power-policy", "dotfiles/power-policy-test.sh"), needs=("dash",)),
    Check("power-policy-busybox", (POWER,), ("busybox", "ash", "dotfiles/power-policy-test.sh"), ("dotfiles/linux/.local/bin/power-policy", "dotfiles/power-policy-test.sh"), needs=("busybox",)),
    Check("power-policy-shellcheck", (POWER,), ("shellcheck", "-s", "sh", "dotfiles/linux/.local/bin/power-policy", "dotfiles/power-policy-test.sh"), ("dotfiles/linux/.local/bin/power-policy", "dotfiles/power-policy-test.sh"), needs=("shellcheck",)),
    Check("shellcheck-sh", (SHELL,), ("shellcheck", "-s", "sh", "{file}"), ("*.sh",), needs=("shellcheck",), per_file=True),
    Check("shellcheck-bin", (SHELL,), ("shellcheck", "-s", "sh", "{file}"), ("dotfiles/*/.local/bin/*",), needs=("shellcheck",), per_file=True, sh_shebang=True),
    Check("ruff", (PYTHON,), ("uvx", "ruff", "check", "{file}"), ("*.py",), needs=("uvx",), per_file=True),
    Check("ty", (PYTHON,), ("uvx", "ty", "check", "{file}"), ("*.py",), needs=("uvx",), per_file=True),
    Check("markdown-links", (MARKDOWN,), py("dotfiles/base/.local/bin/mdtool", "links", "--untracked", "{file}"), ("*.md",), per_file=True),
    Check("macos-tool", (MACOS_TOOLS,), py("host/macos/macos-test.py"), ("host/macos/macos", "host/macos/macos-test.py"), tmpdir=True),
    Check("macos-lean", (MACOS_TOOLS,), py("host/macos/lean-test.py"), ("host/macos/lean.py", "host/macos/lean-test.py"), tmpdir=True),
    Check("macos-ruff", (MACOS_TOOLS,), ("uvx", "ruff", "check", "host/macos/macos", "host/macos/macos-test.py", "host/macos/lean.py", "host/macos/lean-test.py"), ("host/macos/macos", "host/macos/macos-test.py", "host/macos/lean.py", "host/macos/lean-test.py"), needs=("uvx",)),
)

SUITE: tuple[str, ...] = (
    "macos-sync", "claude-worker", "pi-worker", "companions", "sync-dag", "sync-main", "pi-extensions", "sync-links",
    "uninstall", "kache", "installer", "ffmpeg-runtime", "bootstrap", "sync-integration", "doctor",
    "pi-git-guard", "pinact", "pinact-yaml", "pinact-lint-rules", "pinact-expressions", "pinact-security",
    "pinact-fix", "pinact-pins", "pi-profile", "policy-generated", "policy-generator", "orchestrate", "sbx",
    "reset-agents", "pre-push", "worktree-remove", "worktree-retire",
    "zsh-shim", "mdtool-suite", "decide", "skills", "project-skills", "skills-campaign",
)

BY_ID = {check.id: check for check in REGISTRY}


@dataclass(frozen=True)
class Change:
    path: str
    deleted: bool = False


@dataclass(frozen=True)
class Host:
    platform: Platform
    commands: frozenset[str]


@dataclass(frozen=True)
class Planned:
    check: Check
    argv: tuple[str, ...]
    reasons: tuple[tuple[str, str], ...]
    skip: Optional[str]


@dataclass(frozen=True)
class Plan:
    checks: tuple[Planned, ...]
    unmapped: tuple[str, ...]
    index_differs: tuple[str, ...] = ()


def matches(pattern: str, path: str) -> bool:
    if pattern.endswith("/"):
        return path.startswith(pattern)
    if any(c in pattern for c in "*?["):
        return fnmatch.fnmatchcase(path, pattern) or ("/" not in pattern and fnmatch.fnmatchcase(path.rsplit("/", 1)[-1], pattern))
    return path == pattern


def unmet(check: Check, host: Host) -> Optional[str]:
    if check.platform != "any" and check.platform != host.platform:
        return f"requires {check.platform}"
    missing = [c for c in check.needs if c not in host.commands]
    return f"requires {', '.join(missing)} on PATH" if missing else None


def plan(changes: Sequence[Change], host: Host, first_line: Callable[[str], str],
         registry: Sequence[Check] = REGISTRY, index_differs: tuple[str, ...] = ()) -> Plan:
    planned: list[Planned] = []
    covered: set[str] = set()
    for check in registry:
        hits = [(c, p) for c in changes for p in check.covers if matches(p, c.path)]
        if check.per_file:
            hits = [(c, p) for c, p in hits if not c.deleted and (not check.sh_shebang or first_line(c.path).startswith("#!/bin/sh"))]
        if not hits:
            continue
        covered.update(c.path for c, _ in hits)
        skip = unmet(check, host)
        if check.per_file:
            for change, pattern in hits:
                argv = tuple(change.path if a == "{file}" else a for a in check.argv)
                planned.append(Planned(check, argv, ((change.path, pattern),), skip))
        else:
            reasons = tuple(dict.fromkeys((c.path, p) for c, p in hits))
            planned.append(Planned(check, check.argv, reasons, skip))
    unmapped = tuple(sorted({c.path for c in changes} - covered))
    return Plan(tuple(planned), unmapped, index_differs)


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-c", "core.fsmonitor=false", *args], cwd=root, check=True, capture_output=True).stdout


def parse_name_status(diff: bytes, untracked: bytes) -> list[Change]:
    fields = diff.split(b"\0")
    result: list[Change] = []
    i = 0
    while i < len(fields) and fields[i]:
        status = fields[i].decode()
        if status[0] in "RC":
            old, new = fields[i + 1].decode(), fields[i + 2].decode()
            if status[0] == "R":
                result.append(Change(old, deleted=True))
            result.append(Change(new))
            i += 3
        else:
            result.append(Change(fields[i + 1].decode(), deleted=status[0] == "D"))
            i += 2
    result.extend(Change(path.decode()) for path in untracked.split(b"\0") if path)
    return result


def changed(root: Path, base: Optional[str]) -> list[Change]:
    sources = [
        git(root, "diff", "--cached", "-M", "--name-status", "-z", "HEAD"),
        git(root, "diff", "-M", "--name-status", "-z"),
    ]
    if base:
        sources.append(git(root, "diff", "-M", "--name-status", "-z", base, "HEAD"))
    untracked = git(root, "ls-files", "--others", "--exclude-standard", "-z")
    paths = {change.path for source in sources for change in parse_name_status(source, b"")}
    paths.update(change.path for change in parse_name_status(b"", untracked))
    return [Change(path, deleted=not os.path.lexists(root / path)) for path in sorted(paths)]


def index_differs(root: Path) -> tuple[str, ...]:
    output = git(root, "diff", "--no-renames", "--name-only", "-z")
    return tuple(sorted(os.fsdecode(path) for path in output.split(b"\0") if path))


def host_facts(registry: Iterable[Check] = REGISTRY) -> Host:
    platform: Platform = "darwin" if sys.platform == "darwin" else "linux" if sys.platform.startswith("linux") else "any"
    needed = {c for check in registry for c in check.needs}
    return Host(platform, frozenset(c for c in needed if shutil.which(c)))


def first_line_of(root: Path) -> Callable[[str], str]:
    def read(path: str) -> str:
        try:
            with open(root / path, "rb") as handle:
                return handle.readline().decode(errors="replace")
        except OSError:
            return ""
    return read


def plan_json(result: Plan) -> dict[str, object]:
    return {
        "checks": [{
            "id": p.check.id, "argv": list(p.argv), "cwd": p.check.cwd,
            "why": [{"path": path, "pattern": pattern} for path, pattern in p.reasons],
            "runnable": p.skip is None, "skip_reason": p.skip,
        } for p in result.checks],
        "unmapped": list(result.unmapped),
        "index_differs": list(result.index_differs),
    }


def environment(root: Path, check: Check) -> dict[str, str]:
    env = dict(os.environ)
    if check.tmpdir:
        tmp = Path(os.environ.get("TMPDIR") or root / ".work/tmp")
        tmp.mkdir(parents=True, exist_ok=True)
        env["TMPDIR"] = str(tmp.resolve())
    return env


def fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    def add(data: bytes) -> None:
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)

    add(git(root, "rev-parse", "HEAD"))
    add(git(root, "status", "--porcelain=v1", "-z"))
    add(git(root, "diff", "HEAD", "--binary"))
    add(git(root, "diff", "--cached", "--binary"))
    paths = git(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    for raw_path in sorted(path for path in paths if path):
        path = root / os.fsdecode(raw_path)
        mode = path.lstat().st_mode
        add(raw_path)
        add(str(stat.S_IFMT(mode)).encode())
        if stat.S_ISLNK(mode):
            add(os.fsencode(os.readlink(path)))
        elif stat.S_ISREG(mode):
            add(path.read_bytes())
    return digest.hexdigest()


def execute(root: Path, check: Check, argv: Sequence[str]) -> dict[str, object]:
    head = git(root, "rev-parse", "HEAD").decode().strip()
    tree = fingerprint(root)
    started = time.time()
    try:
        proc = subprocess.run(list(argv), cwd=root / check.cwd, env=environment(root, check),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        exit_code, output = proc.returncode, proc.stdout.decode(errors="replace")
    except OSError as error:
        exit_code, output = 127, str(error)
    finished = time.time()
    return {
        "id": check.id, "argv": list(argv), "cwd": check.cwd, "head": head, "tree_fingerprint": tree,
        "started_at": iso(started), "finished_at": iso(finished), "exit_code": exit_code, "output_tail": output[-TAIL:],
    }


def iso(seconds: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds))


def run_suite(root: Path) -> int:
    for check_id in SUITE:
        check = BY_ID[check_id]
        if subprocess.run(list(check.argv), cwd=root / check.cwd, env=environment(root, check)).returncode:
            print(f"check failed: {check.id}: {render_argv(check, check.argv)}", file=sys.stderr)
            return 1
    return 0


def run_changed(root: Path, base: Optional[str], as_json: bool) -> int:
    result = plan(changed(root, base), host_facts(), first_line_of(root), index_differs=index_differs(root))
    records: list[dict[str, object]] = []
    for p in result.checks:
        if p.skip:
            records.append({"id": p.check.id, "argv": list(p.argv), "skipped": p.skip})
            continue
        records.append(execute(root, p.check, p.argv))
    if as_json:
        print(json.dumps({"results": records, "unmapped": list(result.unmapped)}, indent=2))
    else:
        for r in records:
            if "skipped" in r:
                print(f"skipped {r['id']}: {r['skipped']}")
            else:
                print(f"{r['id']}: exit {r['exit_code']}")
                if r["exit_code"]:
                    print(r["output_tail"])
        for path in result.unmapped:
            print(f"unmapped: {path}")
    return 1 if any(r.get("exit_code") for r in records) else 0


def show_plan(root: Path, base: Optional[str], as_json: bool) -> int:
    result = plan(changed(root, base), host_facts(), first_line_of(root), index_differs=index_differs(root))
    if as_json:
        print(json.dumps(plan_json(result), indent=2))
        return 0
    for p in result.checks:
        paths = sorted({path for path, _ in p.reasons})
        why = ", ".join(paths[:3]) + (f", and {len(paths) - 3} more" if len(paths) > 3 else "")
        state = f" (skipped: {p.skip})" if p.skip else ""
        print(f"{p.check.id}: {' '.join(p.argv)}{state}\n  because {why}")
    for path in result.unmapped:
        print(f"unmapped: {path}")
    for path in result.index_differs:
        print(f"index differs from working tree: {path}")
    return 0


def render_argv(check: Check, argv: Sequence[str]) -> str:
    text = " ".join("FILE" if a == "{file}" else a for a in argv)
    if check.cwd != ".":
        tmp = 'export TMPDIR="$PWD/.work/tmp"; ' if check.tmpdir else ""
        return f"({tmp}cd {check.cwd} && {text})"
    if check.tmpdir:
        text = 'TMPDIR="$PWD/.work/tmp" ' + text
    return text


def render_check(check: Check) -> str:
    text = f"`{render_argv(check, check.argv)}`"
    if check.platform == "darwin":
        text = "on macOS " + text
    elif check.platform == "linux":
        text = "on Linux " + text
    if check.per_file:
        text += " for each changed match"
    if check.note:
        text += f" ({check.note})"
    return text


def join_words(items: list[str]) -> str:
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + ", and " + items[-1]


def render_table(registry: Sequence[Check] = REGISTRY) -> str:
    areas: dict[Area, list[Check]] = {}
    for check in registry:
        for area in check.areas:
            areas.setdefault(area, []).append(check)
    lines = [BEGIN, "| Changed | Run |", "| --- | --- |"]
    for area, checks in areas.items():
        cell = join_words([render_check(c) for c in checks])
        if area.note:
            cell += "; " + area.note
        lines.append(f"| {area.label} | {cell} |")
    lines.append(END)
    return "\n".join(lines)


def render_doc(text: str, registry: Sequence[Check] = REGISTRY) -> str:
    start, end = text.find(BEGIN), text.find(END)
    if start < 0 or end < start or text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError(f"{DOC} needs exactly one {BEGIN} ... {END} region")
    return text[:start] + render_table(registry) + text[end + len(END):]


def docs(root: Path, check_only: bool) -> int:
    path = root / DOC
    current = path.read_text(encoding="utf-8")
    rendered = render_doc(current)
    if rendered == current:
        return 0
    if check_only:
        print(f"{DOC} is stale; run python3 -I tools/sync/checks.py docs", file=sys.stderr)
        return 1
    path.write_text(rendered, encoding="utf-8")
    return 0


USAGE = "usage: sync check [--plan|--changed] [--json] [--base REV]"


def main(argv: list[str], root: Path = ROOT) -> int:
    if argv[:1] == ["docs"]:
        rest = argv[1:]
        if rest not in ([], ["--check"]):
            raise SystemExit("usage: checks.py docs [--check]")
        return docs(root, bool(rest))
    mode, as_json, base = "suite", False, None
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg in ("--plan", "--changed") and mode == "suite":
            mode = arg[2:]
        elif arg == "--json":
            as_json = True
        elif arg == "--base" and args:
            base = args.pop(0)
        else:
            raise SystemExit(USAGE)
    if mode == "suite":
        if as_json or base:
            raise SystemExit(USAGE)
        return run_suite(root)
    if mode == "plan":
        return show_plan(root, base, as_json)
    return run_changed(root, base, as_json)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
