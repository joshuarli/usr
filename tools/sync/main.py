"""Reconcile the usr home as a graph of typed tasks."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dag import Graph, GraphError, Probe, Task

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "tools/sync/install.sh"
BRIDGE = ROOT / "tools/sync/claude-worker.py"

NPM_TOOLS = frozenset({"cmd", "pnpm", "cf", "agent-browser", "pi", "dsh"})
JQ_TOOLS = frozenset({"python3", "codex", "node-build"})
TOOL_EXECUTABLES = {
    "nodejs": ("node", "npm"), "ffmpeg": ("ffmpeg", "ffprobe"),
    "shuck": ("shellcheck",), "opencode2": ("opencode2",),
    "ghostty": ("ghostty-custom",), "ghostty-custom": ("ghostty-custom",),
    "player": ("player",), "antigravity": ("agy",),
    "python3": ("python3",), "ssh": ("ssh",),
}


@dataclass(frozen=True)
class Context:
    root: Path
    home: Path
    platform: str
    profile: str
    env: dict[str, str]
    target: Path | None = None

    @property
    def link_target(self) -> Path:
        return self.target or self.home

    @property
    def state(self) -> Path:
        return Path(self.env.get("DL_OWNED_FILE", str(self.link_target / ".local/state/sync/dl-owned")))


def context() -> Context:
    home = Path(os.environ["HOME"])
    target = Path(os.environ.get("TARGET", str(home)))
    if not home.is_absolute() or not target.is_absolute():
        raise GraphError("HOME and TARGET must be absolute paths")
    platform = subprocess.check_output(["uname", "-s"], text=True).strip().lower()
    profile = os.environ.get("DL_PROFILE", "")
    if not profile:
        mode = Path("/etc/home/install-mode")
        if mode.is_file():
            profile = mode.read_text().strip()
    return Context(ROOT, home, platform, profile, dict(os.environ), target)


def command(ctx: Context, *args: str, capture: bool = False, extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = ctx.env.copy()
    env.update(extra or {})
    env["HOME"] = str(ctx.home)
    env.setdefault("TMPDIR", str(ctx.root / ".work/tmp"))
    return subprocess.run(args, cwd=ctx.root, env=env, text=True, capture_output=capture, check=False)


def required(result: subprocess.CompletedProcess[str], what: str) -> None:
    if result.returncode:
        raise RuntimeError(f"{what} failed with status {result.returncode}")


def tool_list(ctx: Context) -> list[str]:
    result = command(ctx, "sh", str(ctx.root / "tools/sync/install.sh"), "--list", capture=True)
    if result.returncode:
        raise RuntimeError(f"unable to list default tools: {result.stderr.strip()}")
    return list(dict.fromkeys(result.stdout.split()))


def link_status(ctx: Context) -> Probe:
    output = []
    for layer in ["base", ctx.platform]:
        source = ctx.root / "dotfiles" / layer
        if not source.is_dir():
            continue
        response = command(ctx, "sh", str(ctx.root / "dotfiles/sym"),
                           "--dry-run", "-t", str(ctx.link_target), str(source), capture=True,
                           extra={"SYM_OWNED_FILE": str(ctx.state)})
        lines = response.stdout + response.stderr
        output.extend(line for line in lines.splitlines() if line.startswith(("LINK:", "CONFLICT:", "PRUNE:")))
        if response.returncode and not any(line.startswith("CONFLICT:") for line in lines.splitlines()):
            return Probe(False, f"link planner failed: {lines.strip()}", True)
    if any(line.startswith("CONFLICT:") for line in output):
        return Probe(False, "; ".join(output), True)
    return Probe(not output, "; ".join(output) if output else "links match")


def apply_links(ctx: Context) -> None:
    ctx.state.parent.mkdir(parents=True, exist_ok=True)
    scratch = ctx.root / ".work/tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    required(command(ctx, "sh", str(ctx.root / "dotfiles/migrate-pinact.sh"),
                     str(ctx.link_target), str(ctx.state)), "pinact migration")
    for layer in ["base", ctx.platform]:
        source = ctx.root / "dotfiles" / layer
        if source.is_dir():
            required(command(ctx, "sh", str(ctx.root / "dotfiles/sym"), "-v",
                             "-t", str(ctx.link_target), str(source),
                             extra={"SYM_OWNED_FILE": str(ctx.state)}), f"{layer} links")


def installed(ctx: Context, tool: str) -> Probe:
    names = TOOL_EXECUTABLES.get(tool, (tool,))
    missing = [name for name in names if not os.access(ctx.home / ".local/bin" / name, os.X_OK)]
    return Probe(not missing, "installed" if not missing else "missing " + ", ".join(missing))


def apply_tool(ctx: Context, tool: str) -> None:
    ctx.state.parent.mkdir(parents=True, exist_ok=True)
    (ctx.root / ".work/tmp").mkdir(parents=True, exist_ok=True)
    required(command(ctx, "sh", str(ctx.root / "tools/sync/install.sh"), tool,
                     extra={"DL_OWNED_FILE": str(ctx.state)}), f"install {tool}")


def bridge_status(ctx: Context) -> Probe:
    r = command(ctx, sys.executable, "-I", str(BRIDGE), "check", capture=True)
    return Probe(r.returncode == 0, "bridge registered" if r.returncode == 0 else (r.stderr.strip() or "bridge missing"))


def bridge_apply(ctx: Context) -> None:
    required(command(ctx, sys.executable, "-I", str(BRIDGE), "install"), "Claude MCP registration")


def mac_packages_status(ctx: Context) -> Probe:
    brew = next((str(path) for path in (Path("/opt/homebrew/bin/brew"), Path("/usr/local/bin/brew")) if path.is_file()), None) or shutil.which("brew")
    if brew is None:
        return Probe(False, "Homebrew absent")
    r = command(ctx, brew, "bundle", "check", "--file=" + str(ctx.root / "host/macos/Brewfile"), capture=True)
    return Probe(r.returncode == 0, "Brewfile packages installed" if r.returncode == 0 else "Brewfile packages missing")


def mac_packages_apply(ctx: Context) -> None:
    required(command(ctx, "sh", str(ctx.root / "host/macos/setup-macos"), "brew", "packages"), "Homebrew setup")


def alpine_status(ctx: Context) -> Probe:
    file = Path("/etc/unbound/unbound.conf")
    if not file.is_file() or not shutil.which("unbound-checkconf"):
        return Probe(False, "Alpine Unbound not configured")
    r = command(ctx, "unbound-checkconf", str(file), capture=True)
    return Probe(r.returncode == 0, "Unbound config valid" if r.returncode == 0 else "Unbound config invalid")


def alpine_apply(ctx: Context) -> None:
    required(command(ctx, "sh", str(ctx.root / "host/setup-linux")), "Alpine host setup")


def kache_status(ctx: Context) -> Probe:
    binary = Path(ctx.env.get("KACHE", str(ctx.home / ".cargo/bin/kache")))
    return Probe(os.access(binary, os.X_OK), "kache installed" if binary.is_file() else "kache missing")


def kache_apply(ctx: Context) -> None:
    if ctx.platform == "linux" and not (shutil.which("rustup") or os.access(ctx.home / ".cargo/bin/rustup", os.X_OK)):
        raise RuntimeError("rustup is required for kache; install it before enabling this task")
    required(command(ctx, "sh", str(ctx.root / "dotfiles/base/.local/bin/setup-kache")), "kache setup")


def is_alpine() -> bool:
    file = Path("/etc/os-release")
    return file.is_file() and any(line.strip() == "ID=alpine" for line in file.read_text().splitlines())


def graph(ctx: Context, names: list[str], *, setup: bool) -> Graph:
    nodes: list[Task] = [Task("links", (), lambda: link_status(ctx),
                              lambda: apply_links(ctx), lambda: link_status(ctx),
                              frozenset({"home-links"}))]
    has_alpine = ctx.platform == "linux" and is_alpine()
    if has_alpine:
        nodes.append(Task("host:alpine", (), lambda: alpine_status(ctx),
                          lambda: alpine_apply(ctx), lambda: alpine_status(ctx),
                          frozenset({"host:packages"}), reconcile=True))
    if ctx.platform == "darwin":
        nodes.append(Task("host:mac-packages", (), lambda: mac_packages_status(ctx),
                          lambda: mac_packages_apply(ctx), lambda: mac_packages_status(ctx),
                          frozenset({"host:packages"})))

    all_tools = set(names)
    if ctx.profile != "server":
        all_tools.update({"nodejs", "claude", "opencode2", "cmd"})
    pending = list(all_tools)
    while pending:
        tool = pending.pop()
        prerequisites = set()
        if tool in NPM_TOOLS:
            prerequisites.add("nodejs")
        if tool in JQ_TOOLS:
            prerequisites.add("jaq")
        if tool == "dsh":
            prerequisites.add("pnpm")
        for dependency in prerequisites - all_tools:
            all_tools.add(dependency)
            pending.append(dependency)

    for tool in sorted(all_tools):
        dependencies = ["links"] if setup else []
        if has_alpine and setup:
            dependencies.append("host:alpine")
        if tool in NPM_TOOLS:
            dependencies.append("tool:nodejs")
        if tool in JQ_TOOLS:
            dependencies.append("tool:jaq")
        if tool == "dsh":
            dependencies.append("tool:pnpm")
        nodes.append(Task("tool:" + tool, tuple(dependencies),
                          lambda t=tool: installed(ctx, t),
                          lambda t=tool: apply_tool(ctx, t),
                          lambda t=tool: installed(ctx, t),
                          frozenset({"legacy-installer"}), reconcile=True))
    if ctx.profile != "server":
        nodes.append(Task("claude-mcp", ("links", "tool:nodejs", "tool:claude", "tool:cmd", "tool:opencode2"),
                          lambda: bridge_status(ctx), lambda: bridge_apply(ctx),
                          lambda: bridge_status(ctx), frozenset({"claude-config"})))
    deps = ("links",)
    if ctx.platform == "darwin":
        deps = ("links", "host:mac-packages")
    nodes.append(Task("kache", deps, lambda: kache_status(ctx),
                      lambda: kache_apply(ctx), lambda: kache_status(ctx),
                      frozenset({"toolchain"})))
    return Graph(nodes)


def main(argv: list[str]) -> int:
    ctx = context()
    command_name = argv.pop(0) if argv else "apply"
    if ctx.link_target.resolve() != ctx.home.resolve() and command_name in {"apply", "tools", "bridge", "uninstall"}:
        raise GraphError(f"{command_name} cannot mutate host tools with TARGET different from HOME; use sync links")
    if command_name == "list":
        if argv:
            raise GraphError("sync list does not take arguments")
        print("\n".join(tool_list(ctx)))
        return 0
    if command_name == "uninstall":
        from uninstall import uninstall
        uninstall(ctx)
        return 0
    if command_name == "check":
        required(command(ctx, "sh", str(ctx.root / "tools/sync/check.sh")), "repository checks")
        return 0
    if command_name == "check-parallel":
        required(command(ctx, "sh", "-c", "uvx --python 3.15 --with joshuarli-pytest-parallel==0.4.0 pytest tools dotfiles host/macos"), "parallel checks")
        return 0
    if command_name == "layers":
        all_layers = [ctx.root / "dotfiles/base", ctx.root / "dotfiles" / ctx.platform]
        observed: set[str] = set()
        for layer in all_layers:
            if layer.is_dir():
                r = command(ctx, "git", "ls-files", "--", str(layer.relative_to(ctx.root)), capture=True)
                required(r, "layer listing")
                for line in r.stdout.splitlines():
                    relative = str(Path(line).relative_to(layer.relative_to(ctx.root)))
                    if relative in observed:
                        raise GraphError(f"duplicate link owner: {relative}")
                    observed.add(relative)
        return 0
    if command_name not in {"apply", "plan", "doctor", "links", "tools", "bridge"}:
        raise GraphError("usage: sync [plan|doctor|links|tools NAME...|list|bridge|uninstall|check|check-parallel|layers]")
    defaults = tool_list(ctx) if command_name in ("apply", "plan", "doctor") or (command_name == "tools" and not argv) else []
    chosen = argv if command_name == "tools" and argv else defaults
    full = graph(ctx, chosen, setup=command_name in {"apply", "plan", "doctor", "bridge"})
    if command_name == "links":
        selected = full.select(["links"])
    elif command_name == "bridge":
        selected = full.select(["claude-mcp"])
    elif command_name == "tools":
        selected = full.select(["tool:" + name for name in chosen])
    elif command_name in {"apply", "plan", "doctor"}:
        goals = ["links"] + ["tool:" + name for name in defaults]
        if ctx.platform == "darwin":
            goals.append("host:mac-packages")
        if ctx.profile != "server":
            goals.append("claude-mcp")
        if ctx.platform == "darwin" or os.access(ctx.home / ".cargo/bin/rustup", os.X_OK):
            goals.append("kache")
        selected = full.select(goals)
    else:
        raise AssertionError(command_name)
    if command_name in {"plan", "doctor"}:
        failures = 0
        for task, probe in selected.inspect():
            state = "CONFLICT" if probe.conflict else "APPLY" if not probe.current else "CHECK" if task.reconcile else "CURRENT"
            print(f"{state:8} {task.name}: {probe.detail}")
            if command_name == "plan" and task.name == "links":
                for line in probe.detail.split("; "):
                    if line.startswith(("LINK:", "CONFLICT:", "PRUNE:")):
                        print(line)
            if command_name == "doctor" and (not probe.current or probe.conflict):
                failures += 1
            if command_name == "plan" and probe.conflict:
                failures += 1
        if command_name == "doctor":
            legacy = command(ctx, "sh", str(ctx.root / "dotfiles/doctor"))
            failures += int(legacy.returncode != 0)
        return 1 if failures else 0
    results = selected.run(jobs=int(ctx.env.get("SYNC_JOBS", "4")))
    for result in results:
        print(f"{result.state.upper():8} {result.name}: {result.detail}")
    return 1 if any(r.state in ("failed", "blocked") for r in results) else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (GraphError, OSError, RuntimeError, ValueError) as exc:
        print(f"sync: {exc}", file=sys.stderr)
        raise SystemExit(1)
