"""Reconcile the usr home as a graph of typed tasks."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dag import Graph, GraphError, Probe, Result, Task, default_jobs
from links import LinkError, discover
from link_plan import plan_links
from link_apply import LinkApplyError, apply as apply_link_plan
from installer import Installer, SkipInstall, default_tools
from pi_extensions import missing as missing_pi_extensions
from ownership import capture_new, claims_lock, merge_claims, records, ownership_lock, fingerprint, read_manifest

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "tools/sync/claude-worker.py"
PI_BRIDGE = ROOT / "tools/sync/pi-worker.py"
OPENCODE_BRIDGE = ROOT / "tools/sync/opencode-worker.py"

NPM_TOOLS = frozenset({"cmd", "pnpm", "cf", "agent-browser", "pi", "dsh"})
JQ_TOOLS = frozenset({"codex", "node-build"})
TOOL_EXECUTABLES = {
    "nodejs": ("node", "npm"), "ffmpeg": ("ffmpeg", "ffprobe"),
    "shuck": ("shellcheck",), "opencode2": ("opencode2",),
    "ghostty": ("ghostty-custom",), "ghostty-custom": ("ghostty-custom",),
    "player": ("player",), "antigravity": ("agy",), "gluon": ("meson", "ninja", "gluon-build"),
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
    arch = subprocess.check_output(["uname", "-m"], text=True).strip()
    if arch == "arm64":
        arch = "aarch64"
    return default_tools(ctx.platform, arch, ctx.profile,
                         ctx.root / "host/alpine/tools-server.txt")


def _link_plan(ctx: Context):
    return plan_links(discover(ctx.root, ctx.link_target, ctx.platform), ctx.state)


def link_status(ctx: Context) -> Probe:
    try:
        planned = _link_plan(ctx)
    except (LinkError, OSError, ValueError) as exc:
        return Probe(False, str(exc), True)
    return Probe(planned.converged, "; ".join(planned.lines()) or "links match",
                 bool(planned.conflicts))


def apply_links(ctx: Context) -> None:
    # The retired pinact launcher is the only pre-link migration; do not run
    # unrelated host setup from the filesystem link task.
    with ownership_lock(ctx.state), claims_lock():
        required(command(ctx, "sh", str(ctx.root / "dotfiles/migrate-pinact.sh"),
                         str(ctx.link_target), str(ctx.state)), "pinact migration")
        plan = _link_plan(ctx)
        if plan.conflicts:
            raise LinkApplyError("link conflicts: " + "; ".join(plan.conflicts))
        for line in apply_link_plan(plan, ctx.state):
            print(line)


def installed(ctx: Context, tool: str) -> Probe:
    names = TOOL_EXECUTABLES.get(tool, (tool,))
    missing = [name for name in names if not os.access(ctx.home / ".local/bin" / name, os.X_OK)]
    return Probe(not missing, "installed" if not missing else "missing " + ", ".join(missing))


def apply_tool(ctx: Context, tool: str) -> None:
    (ctx.root / ".work/tmp").mkdir(parents=True, exist_ok=True)
    with ownership_lock(ctx.state):
        before = records(ctx.state)
    leaf = Installer(ctx.home, env=ctx.env)
    try:
        leaf.install(tool)
    except SkipInstall as exc:
        raise RuntimeError(f"install {tool} skipped: {exc.reason}") from exc
    if leaf.changed:
        with ownership_lock(ctx.state), claims_lock():
            merge_claims(ctx.state, set(leaf.claims), set(leaf.removed))
            capture_new(ctx.state, before, set(leaf.claims))



def pi_extensions_status(ctx: Context) -> Probe:
    try:
        missing = missing_pi_extensions(ctx.root / "dotfiles/base/.pi/agent/settings.json", ctx.home)
    except (OSError, ValueError, TypeError) as exc:
        return Probe(False, "Invalid Pi package profile: " + str(exc), True)
    detail = "; ".join(f"{name}@{version} (installed: {actual or 'missing'})"
                       for _, name, version, actual in missing)
    return Probe(not missing, detail or "Pi extensions are bundled locally (no npm)")


def pi_extensions_apply(ctx: Context) -> None:
    # No package download, registry probe or Pi updater is permitted by sync.
    missing_pi_extensions(ctx.root / "dotfiles/base/.pi/agent/settings.json", ctx.home)


def bridge_status(ctx: Context) -> Probe:
    r = command(ctx, sys.executable, "-I", str(BRIDGE), "check", capture=True)
    return Probe(r.returncode == 0, "bridge registered" if r.returncode == 0 else (r.stderr.strip() or "bridge missing"))


def bridge_apply(ctx: Context) -> None:
    required(command(ctx, sys.executable, "-I", str(BRIDGE), "install"), "Claude MCP registration")


def pi_bridge_status(ctx: Context) -> Probe:
    r = command(ctx, sys.executable, "-I", str(PI_BRIDGE), "check", capture=True)
    return Probe(r.returncode == 0, "bridge registered" if r.returncode == 0 else (r.stderr.strip() or "bridge missing"))


def pi_bridge_apply(ctx: Context) -> None:
    required(command(ctx, sys.executable, "-I", str(PI_BRIDGE), "install"), "Pi MCP registration")


def opencode_bridge_status(ctx: Context) -> Probe:
    r = command(ctx, sys.executable, "-I", str(OPENCODE_BRIDGE), "check", capture=True)
    return Probe(r.returncode == 0, "bridge registered" if r.returncode == 0 else (r.stderr.strip() or "bridge missing"))


def opencode_bridge_apply(ctx: Context) -> None:
    required(command(ctx, sys.executable, "-I", str(OPENCODE_BRIDGE), "install"), "OpenCode MCP registration")


def mac_packages_status(ctx: Context) -> Probe:
    brew = next((str(path) for path in (Path("/opt/homebrew/bin/brew"), Path("/usr/local/bin/brew")) if path.is_file()), None) or shutil.which("brew")
    if brew is None:
        return Probe(False, "Homebrew absent")
    r = command(ctx, brew, "bundle", "check", "--file=" + str(ctx.root / "host/macos/Brewfile"), capture=True)
    return Probe(r.returncode == 0, "Brewfile packages installed" if r.returncode == 0 else "Brewfile packages missing")


def mac_packages_apply(ctx: Context) -> None:
    required(command(ctx, "sh", str(ctx.root / "host/macos/setup-macos"), "brew", "packages"), "Homebrew setup")


def _unbound_validator() -> Path | None:
    found = shutil.which("unbound-checkconf")
    if found:
        return Path(found)
    for candidate in (Path("/usr/sbin/unbound-checkconf"), Path("/sbin/unbound-checkconf"),
                      Path("/usr/local/sbin/unbound-checkconf")):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def alpine_status(ctx: Context) -> Probe:
    file = Path("/etc/unbound/unbound.conf")
    validator = _unbound_validator()
    if not file.is_file() or validator is None:
        return Probe(False, "Alpine Unbound not configured")
    r = command(ctx, str(validator), str(file), capture=True)
    return Probe(r.returncode == 0, "Unbound config valid" if r.returncode == 0 else "Unbound config invalid")


def alpine_apply(ctx: Context) -> None:
    required(command(ctx, "sh", str(ctx.root / "host/setup-linux")), "Alpine host setup")


def kache_install_path(ctx: Context) -> Path:
    cargo_home = Path(ctx.env.get("CARGO_HOME", str(ctx.home / ".cargo")))
    if not cargo_home.is_absolute():
        raise ValueError("CARGO_HOME must be an absolute path")
    binary = cargo_home / "bin/kache"
    if not binary.is_relative_to(ctx.home):
        raise ValueError("managed kache must be installed beneath HOME")
    return binary


def kache_status(ctx: Context) -> Probe:
    binary = Path(ctx.env.get("KACHE", str(kache_install_path(ctx))))
    return Probe(os.access(binary, os.X_OK), "kache installed" if binary.is_file() else "kache missing")


def kache_apply(ctx: Context) -> None:
    if ctx.platform == "linux" and not (shutil.which("rustup") or os.access(ctx.home / ".cargo/bin/rustup", os.X_OK)):
        raise RuntimeError("rustup is required for kache; install it before enabling this task")
    binary = kache_install_path(ctx)
    if "KACHE" in ctx.env and Path(ctx.env["KACHE"]) != binary:
        raise RuntimeError("KACHE override differs from the managed kache install path")
    with ownership_lock(ctx.state), claims_lock():
        before = records(ctx.state)
        existed = binary.exists() or binary.is_symlink()
        if existed:
            proof = read_manifest(ctx.state).get(str(binary))
            identity = fingerprint(binary, "K")
            if ("K", binary) not in before or identity is None or proof != {"kind": "K", "fingerprint": identity}:
                raise RuntimeError(f"refusing to adopt pre-existing or modified kache: {binary}")
    result = command(ctx, "sh", str(ctx.root / "dotfiles/base/.local/bin/setup-kache"))
    required(result, "kache setup")
    if not binary.is_file() or binary.is_symlink() or not os.access(binary, os.X_OK):
        raise RuntimeError(f"kache setup did not install a regular executable: {binary}")
    with ownership_lock(ctx.state), claims_lock():
        ctx.state.parent.mkdir(parents=True, exist_ok=True)
        if ("K", binary) not in before:
            with ctx.state.open("a") as stream:
                stream.write(f"K\t{binary}\n")
                stream.flush()
                os.fsync(stream.fileno())
        capture_new(ctx.state, before, {("K", binary)})


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

    all_tools = set(names) | {"uv", "nodejs", "claude", "opencode2", "cmd", "pi"}
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
        if tool == "player":
            prerequisites.add("ffmpeg")
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
        if tool == "player":
            dependencies.append("tool:ffmpeg")
        nodes.append(Task("tool:" + tool, tuple(dependencies),
                          lambda t=tool: installed(ctx, t),
                          lambda t=tool: apply_tool(ctx, t),
                          lambda t=tool: installed(ctx, t),
                          frozenset({f"tool:{tool}"}), reconcile=True))
    nodes.append(Task("pi-extensions", ("links", "tool:pi"),
                      lambda: pi_extensions_status(ctx), lambda: pi_extensions_apply(ctx),
                      lambda: pi_extensions_status(ctx), frozenset({"pi-config"}), reconcile=True))
    nodes.append(Task("claude-mcp", ("pi-extensions", "tool:nodejs", "tool:pi"),
                      lambda: bridge_status(ctx), lambda: bridge_apply(ctx),
                      lambda: bridge_status(ctx), frozenset({"claude-config", "pi-sdk-install"})))
    nodes.append(Task("pi-mcp", ("pi-extensions", "tool:nodejs", "tool:pi"),
                      lambda: pi_bridge_status(ctx), lambda: pi_bridge_apply(ctx),
                      lambda: pi_bridge_status(ctx), frozenset({"pi-config", "pi-sdk-install"})))
    nodes.append(Task("opencode-mcp", ("pi-extensions", "tool:nodejs", "tool:pi"),
                      lambda: opencode_bridge_status(ctx), lambda: opencode_bridge_apply(ctx),
                      lambda: opencode_bridge_status(ctx), frozenset({"opencode-config", "pi-sdk-install"})))
    deps = ("links",)
    if ctx.platform == "darwin":
        deps = ("links", "host:mac-packages")
    nodes.append(Task("kache", deps, lambda: kache_status(ctx),
                      lambda: kache_apply(ctx), lambda: kache_status(ctx),
                      frozenset({"toolchain"})))
    return Graph(nodes)


def default_goals(ctx: Context) -> list[str]:
    goals = ["links"] + ["tool:" + name for name in tool_list(ctx)]
    if ctx.platform == "darwin":
        goals.append("host:mac-packages")
    if ctx.profile != "server":
        goals.extend(["claude-mcp", "pi-mcp", "opencode-mcp"])
    if ctx.platform == "darwin" or os.access(ctx.home / ".cargo/bin/rustup", os.X_OK):
        goals.append("kache")
    return goals


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
    full = graph(ctx, chosen, setup=command_name in {"apply", "plan", "doctor"})
    if command_name == "links":
        selected = full.select(["links"])
    elif command_name == "bridge":
        selected = full.select(["claude-mcp", "pi-mcp", "opencode-mcp"])
    elif command_name == "tools":
        selected = full.select(["tool:" + name for name in chosen])
    elif command_name in {"apply", "plan", "doctor"}:
        selected = full.select(default_goals(ctx))
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
    jobs = int(ctx.env["SYNC_JOBS"]) if "SYNC_JOBS" in ctx.env else default_jobs()
    try:
        with ownership_lock(ctx.state):
            results = selected.run(jobs=jobs)
    except OSError as exc:
        results = [Result(task.name, "failed", f"{type(exc).__name__}: {exc}")
                   for task in selected.order()]
    for result in results:
        print(f"{result.state.upper():8} {result.name}: {result.detail}")
    return 1 if any(r.state in ("failed", "blocked") for r in results) else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (GraphError, OSError, RuntimeError, ValueError) as exc:
        print(f"sync: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
