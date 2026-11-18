"""Alpine provisioner: builds the server or desktop task graph and runs it with the sync DAG executor."""

from __future__ import annotations

import argparse
import json
import os
import pwd
import grp
import re
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
USR = HERE.parent.parent
sys.path.insert(0, str(USR / "tools" / "sync"))
sys.path.insert(0, str(HERE))

from dag import Graph, Probe, Result, Task  # noqa: E402
import report  # noqa: E402
import tuning  # noqa: E402

USR_URL = "https://github.com/joshuarli/usr"
USR_ORIGINS = {USR_URL, USR_URL + ".git", "git@github.com:joshuarli/usr", "git@github.com:joshuarli/usr.git"}
DOAS_POLICY = Path("/etc/doas.d/30-home-nopass.conf")
INSTALL_MODE = Path("/etc/home/install-mode")
CLOCKSOURCE = Path("/sys/devices/system/clocksource/clocksource0/current_clocksource")
MODULES = ("tun", "tcp_bbr")
CONGESTION = Path("/proc/sys/net/ipv4/tcp_available_congestion_control")
MODES = ("server", "desktop")


class Refusal(Exception):
    """A precondition the operator must fix; no change has been made for it."""


def run(args: list[str], *, check: bool = True, env: dict[str, str] | None = None,
        interactive: bool = False) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(args, text=True, env=env, cwd=HERE, check=False,
                          capture_output=not interactive, stdin=None if interactive else subprocess.DEVNULL)
    if check and proc.returncode != 0:
        tail = ((proc.stderr or "") + (proc.stdout or "")).strip().splitlines()[-12:]
        raise RuntimeError(f"{args[0]} exited {proc.returncode}" + (": " + " | ".join(tail) if tail else ""))
    return proc


def as_user(user: "User", script: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["su", "-s", "/bin/sh", user.name, "-c", f"cd ~ && {script}"], check=check)


def ok(args: list[str], **kwargs) -> bool:
    return run(args, check=False, **kwargs).returncode == 0


def user_ok(user: "User", script: str) -> bool:
    return as_user(user, script, check=False).returncode == 0


def runs(args: list[str], env: dict[str, str] | None = None) -> Callable[[], None]:
    def effect() -> None:
        run(args, env=env)

    return effect


def user_runs(user: "User", script: str) -> Callable[[], None]:
    def effect() -> None:
        as_user(user, script)

    return effect


def read(path: Path) -> str | None:
    try:
        return path.read_text()
    except (FileNotFoundError, NotADirectoryError):
        return None


def write_atomic(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".home-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.chown(tmp, 0, 0)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


@dataclass(frozen=True)
class User:
    name: str
    uid: int
    gid: int
    home: Path

    @property
    def github_key(self) -> Path:
        return self.home / ".ssh" / "github"


@dataclass(frozen=True)
class Context:
    mode: str
    user: User
    arch: str
    cpu: tuning.Cpu
    authkey: str


def in_runlevel(service: str, level: str) -> bool:
    out = run(["rc-update", "show", level], check=False).stdout or ""
    return any(line.split()[:1] == [service] for line in out.splitlines())


def service_started(service: str) -> bool:
    return ok(["rc-service", service, "status"])


def ensure_service(service: str, level: str, start: bool) -> None:
    if not in_runlevel(service, level):
        run(["rc-update", "add", service, level])
    if start:
        run(["rc-service", "--ifstopped", service, "start"])


def service_probe(service: str, level: str, start: bool) -> Probe:
    if not in_runlevel(service, level):
        return Probe(False, f"{service} is not in the {level} runlevel")
    if start and not service_started(service):
        return Probe(False, f"{service} is stopped")
    return Probe(True, f"{service} enabled" + (" and started" if start else ""))


def member(user: User, group: str) -> bool:
    try:
        entry = grp.getgrnam(group)
    except KeyError:
        return False
    return user.name in entry.gr_mem or entry.gr_gid == user.gid


def committed_versions(source: Path) -> Iterable[bytes]:
    git = ["git", "-c", f"safe.directory={USR}", "-C", str(USR)]
    log = run([*git, "log", "--follow", "--format=%H", "--name-only", "--", str(source.relative_to(USR))], check=False).stdout
    rev = ""
    pairs = []
    for line in log.splitlines():
        if re.fullmatch(r"[0-9a-f]{40}", line):
            rev = line
        elif line.strip() and rev:
            pairs.append((rev, line.strip()))
    for rev, path in pairs:
        shown = subprocess.run([*git, "show", f"{rev}:{path}"], capture_output=True, check=False)
        if shown.returncode == 0:
            yield shown.stdout


@dataclass(frozen=True)
class Managed:
    """A root-owned file whose content comes from SOURCE in this checkout or from rendered text."""

    path: Path
    mode: int
    source: Path | None = None
    rendered: bytes | None = None

    def content(self) -> bytes:
        return self.source.read_bytes() if self.source is not None else (self.rendered or b"")

    def probe(self) -> Probe:
        path = self.path
        if not path.exists() and not path.is_symlink():
            return Probe(False, f"{path} is missing")
        if path.is_symlink() or not path.is_file():
            return Probe(False, f"{path} exists and is not a regular file; move it aside", conflict=True)
        actual = path.read_bytes()
        if actual == self.content():
            st = path.stat()
            if (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) != (0, 0, self.mode):
                return Probe(False, f"{path} needs root ownership and mode {self.mode:o}")
            return Probe(True, str(path))
        if self.source is not None and actual in committed_versions(self.source):
            return Probe(False, f"{path} is an older version of {self.source.relative_to(USR)}")
        hint = f"merge it into {self.source.relative_to(USR)}" if self.source is not None else "remove it"
        return Probe(False, f"{path} exists and was not installed by home; move it aside or {hint}", conflict=True)

    def apply(self) -> None:
        write_atomic(self.path, self.content(), self.mode)


def managed_task(name: str, file: Managed, needs: tuple[str, ...] = (), after: Callable[[], None] | None = None) -> Task:
    def apply() -> None:
        file.apply()
        if after is not None:
            after()

    return Task(name, needs, file.probe, apply, file.probe)


def combine(*probes: Callable[[], Probe]) -> Callable[[], Probe]:
    def probe() -> Probe:
        details = []
        for check in probes:
            result = check()
            if result.conflict or not result.current:
                return result
            details.append(result.detail)
        return Probe(True, "; ".join(detail for detail in details if detail))

    return probe


def list_file(name: str) -> list[str]:
    path = HERE / name
    if not path.is_file():
        return []
    return [line.split("#", 1)[0].strip() for line in path.read_text().splitlines() if line.split("#", 1)[0].strip()]


def packages(ctx: Context) -> list[str]:
    return list_file("packages.txt") + list_file(f"packages-{ctx.arch}.txt")


def world() -> set[str]:
    return set((read(Path("/etc/apk/world")) or "").split())


def apk_task(name: str, specs: list[str], needs: tuple[str, ...]) -> Task:
    def probe() -> Probe:
        missing = [spec for spec in specs if spec not in world()]
        return Probe(not missing, "missing: " + " ".join(missing) if missing else f"{len(specs)} packages")

    return Task(name, needs, probe, runs(["apk", "add", "--quiet", *specs]), probe, resources=frozenset({"apk"}))


# ---- server tasks -------------------------------------------------------------------------------


def apk_index_task() -> Task:
    def apply() -> None:
        if not ok(["apk", "update", "--quiet"]):
            raise RuntimeError("apk update failed; check networking and /etc/apk/repositories")

    return Task("apk-index", (), lambda: Probe(False, "refresh"), apply, lambda: Probe(True, "refreshed"),
                resources=frozenset({"apk"}))


def rustup_task(ctx: Context) -> Task:
    rustup = ctx.user.home / ".cargo/bin/rustup"

    def probe() -> Probe:
        return Probe(rustup.is_file() and os.access(rustup, os.X_OK), f"{rustup}")

    def apply() -> None:
        as_user(ctx.user, "rustup-init -y --no-modify-path --default-toolchain none")

    return Task("rustup", ("packages",), probe, apply, probe)


def doas_task(ctx: Context) -> Task:
    policy = Managed(DOAS_POLICY, 0o644, rendered=f"permit nopass {ctx.user.name} as root\n".encode())

    def probe() -> Probe:
        parent = DOAS_POLICY.parent
        if not parent.is_dir() or parent.is_symlink():
            return Probe(False, f"{parent} is missing or is not a regular directory; run setup-user -a", conflict=True)
        result = policy.probe()
        if result.conflict and DOAS_POLICY.is_file() and not DOAS_POLICY.is_symlink():
            return Probe(False, f"{DOAS_POLICY} contains a different rule; move it aside or update it for {ctx.user.name}",
                         conflict=True)
        return result

    def verify() -> Probe:
        result = probe()
        if result.current and not user_ok(ctx.user, "doas -n true"):
            return Probe(False, f"passwordless doas does not work for {ctx.user.name}")
        return result

    return Task("doas", (), probe, policy.apply, verify)


def public_key_matches(private: Path, public: Path) -> bool:
    derived = run(["ssh-keygen", "-y", "-P", "", "-f", str(private)], check=False)
    if derived.returncode != 0:
        return False
    want = derived.stdout.split()[:2]
    have = (read(public) or "").split()[:2]
    return len(want) == 2 and want == have


def github_key_task(ctx: Context) -> Task:
    user = ctx.user
    ssh_dir, key = user.home / ".ssh", user.github_key
    pub = Path(f"{key}.pub")

    def probe() -> Probe:
        if ssh_dir.exists() or ssh_dir.is_symlink():
            if ssh_dir.is_symlink() or not ssh_dir.is_dir():
                return Probe(False, f"{ssh_dir} exists and is not a regular directory", conflict=True)
            if ssh_dir.stat().st_uid != user.uid:
                return Probe(False, f"{ssh_dir} is not owned by {user.name}", conflict=True)
        present = [p for p in (key, pub) if p.exists() or p.is_symlink()]
        if not present:
            return Probe(False, f"{key} will be generated")
        if any(p.is_symlink() or not p.is_file() for p in (key, pub)):
            return Probe(False, f"{key} and {pub} must be regular files; move both aside to generate a new key", conflict=True)
        if any(p.stat().st_uid != user.uid for p in (key, pub)):
            return Probe(False, f"{key} and {pub} must be owned by {user.name}", conflict=True)
        if not public_key_matches(key, pub):
            return Probe(False, f"{key} must be an unencrypted key matching {pub}; move both aside to generate a new key",
                         conflict=True)
        if not run(["ssh-keygen", "-lf", str(pub)], check=False).stdout.rstrip().endswith("(ED25519)"):
            return Probe(False, f"{pub} is not an Ed25519 key; move both aside to generate a new key", conflict=True)
        modes = [(p, m) for p, m in ((ssh_dir, 0o700), (key, 0o600), (pub, 0o644))
                 if (p.stat().st_uid, p.stat().st_gid, stat.S_IMODE(p.stat().st_mode)) != (user.uid, user.gid, m)]
        if modes:
            return Probe(False, f"{modes[0][0]} needs owner {user.name} and mode {modes[0][1]:o}")
        return Probe(True, str(key))

    def apply() -> None:
        ssh_dir.mkdir(mode=0o700, exist_ok=True)
        os.chown(ssh_dir, user.uid, user.gid)
        ssh_dir.chmod(0o700)
        if not key.exists():
            as_user(user, "umask 077 && ssh-keygen -q -t ed25519 -N '' -f .ssh/github </dev/null")
            print(f"home: generated {key}; add this public key to your GitHub account:\n{pub.read_text().strip()}")
        for path, mode in ((key, 0o600), (pub, 0o644)):
            os.chown(path, user.uid, user.gid)
            path.chmod(mode)

    return Task("github-key", (), probe, apply, probe)


def docker_task(ctx: Context) -> Task:
    def probe() -> Probe:
        if not member(ctx.user, "docker"):
            return Probe(False, f"{ctx.user.name} is not in docker")
        return service_probe("docker", "default", True)

    def apply() -> None:
        if not ok(["getent", "group", "docker"]):
            run(["addgroup", "-S", "docker"])
        if not member(ctx.user, "docker"):
            run(["addgroup", ctx.user.name, "docker"])
            print(f"home: added {ctx.user.name} to docker (root-equivalent access); log out and back in to use Docker")
        ensure_service("docker", "default", True)

    def verify() -> Probe:
        result = probe()
        if not result.current:
            return result
        for _ in range(30):
            if user_ok(ctx.user, 'docker info --format "{{.ServerVersion}}"'):
                return result
            time.sleep(1)
        return Probe(False, f"the Docker CLI cannot reach the engine as {ctx.user.name} within 30 seconds")

    return Task("docker", ("packages",), probe, apply, verify)


def clang_major() -> int | None:
    proc = run(["clang", "-dumpversion"], check=False) if Path("/usr/bin/clang").exists() else None
    if proc is None or proc.returncode != 0:
        return None
    return int(proc.stdout.split(".")[0])


def clang_task() -> Task:
    def files() -> list[Managed] | None:
        major = clang_major()
        if major is None:
            return None
        return [Managed(Path(f"/etc/clang{major}/{name}"), 0o644, source=HERE / "config/clang.cfg")
                for name in ("clang.cfg", "clang++.cfg")]

    def probe() -> Probe:
        managed = files()
        if managed is None:
            return Probe(False, "clang is not installed yet")
        return combine(*(m.probe for m in managed))()

    def apply() -> None:
        major = clang_major()
        if major is None or major < 23:
            raise RuntimeError(f"clang {major} is older than 23; check the edge repositories")
        for managed in files() or []:
            managed.apply()

    def verify() -> Probe:
        result = probe()
        if not result.current:
            return result
        for compiler, lang, src in (("clang", "c", "int main(void){return 0;}\n"),
                                    ("clang++", "c++", "#include <cstdio>\nint main(){std::puts(\"\");}\n")):
            with tempfile.TemporaryDirectory() as tmp:
                exe = Path(tmp) / "t"
                built = subprocess.run([compiler, "-x", lang, "-", "-o", str(exe)], input=src, text=True,
                                       capture_output=True, check=False)
                if built.returncode != 0 or not ok([str(exe)]):
                    return Probe(False, f"{compiler} cannot build and run a program with lld and compiler-rt")
        return result

    return Task("clang-config", ("packages",), probe, apply, verify)


def install_mode_task(ctx: Context) -> Task:
    file = Managed(INSTALL_MODE, 0o644, rendered=f"{ctx.mode}\n".encode())

    def probe() -> Probe:
        if INSTALL_MODE.is_file() and not INSTALL_MODE.is_symlink() and (read(INSTALL_MODE) or "").strip() != ctx.mode:
            return Probe(False, f"{INSTALL_MODE} records {(read(INSTALL_MODE) or '').strip()}, not {ctx.mode}")
        result = file.probe()
        return Probe(result.current, f"{INSTALL_MODE} records {ctx.mode}" if result.current else result.detail,
                     result.conflict)

    return Task("install-mode", (), probe, file.apply, probe)


def sync_cmd(ctx: Context, args: str, profile: bool = False) -> str:
    env = f"DL_PROFILE='{ctx.mode}' " if profile else ""
    return f"{env}sh '{USR}/sync' {args}"


def dotfiles_task(ctx: Context) -> Task:
    def probe() -> Probe:
        plan = as_user(ctx.user, sync_cmd(ctx, "plan --json"), check=False)
        try:
            links = next(t for t in json.loads(plan.stdout)["tasks"] if t["name"] == "links")
        except (ValueError, KeyError, StopIteration):
            return Probe(False, f"sh {USR}/sync plan failed: {(plan.stderr or plan.stdout).strip()[-300:]}", conflict=True)
        if links["state"] == "conflict":
            return Probe(False, f"dotfile links conflict with existing files; run sh {USR}/sync plan as {ctx.user.name} "
                         "and resolve each CONFLICT", conflict=True)
        return Probe(links["state"] == "current", links["detail"])

    return Task("dotfiles", ("install-mode",), probe, user_runs(ctx.user, sync_cmd(ctx, "links")), probe)


def missing_tools(ctx: Context) -> list[str]:
    tools = as_user(ctx.user, sync_cmd(ctx, "list", profile=True)).stdout.split()
    if not tools:
        raise RuntimeError(f"sh {USR}/sync list printed no tools for {ctx.user.name}")
    launchers = as_user(ctx.user, f"python3 -I '{USR}/tools/sync/main.py' launchers {' '.join(tools)}").stdout
    if len(launchers.splitlines()) != len(tools):
        raise RuntimeError(f"sync launchers mapped {len(launchers.splitlines())} of {len(tools)} tools")
    missing = []
    for line in launchers.splitlines():
        tool, *names = line.split()
        if tool == "agy":
            continue
        if any(not os.access(ctx.user.home / ".local/bin" / name, os.X_OK) for name in names):
            missing.append(tool)
    return missing


def tools_task(ctx: Context) -> Task:
    def probe() -> Probe:
        missing = missing_tools(ctx)
        return Probe(not missing, "missing: " + " ".join(missing) if missing else "installed")

    def apply() -> None:
        as_user(ctx.user, sync_cmd(ctx, "tools " + " ".join(missing_tools(ctx))))

    def verify() -> Probe:
        result = probe()
        if not result.current:
            return result
        python = ctx.user.home / ".local/bin/python3"
        if not user_ok(ctx.user, f"'{python}' -c 'import sqlite3, ssl'"):
            return Probe(False, f"{python} cannot import sqlite3 and ssl")
        return result

    return Task("tools", ("dotfiles", "rustup", "packages"), probe, apply, verify)


def login_hook_task() -> Task:
    return managed_task("login-hook", Managed(Path("/etc/profile.d/home-session.sh"), 0o644, source=HERE / "config/profile.sh"),
                        ("tools",))


def module_active(module: str) -> bool:
    """Built-in modules may have no /sys/module entry, so check what each one provides."""
    if module == "tun":
        return Path("/dev/net/tun").is_char_device()
    if module == "tcp_bbr":
        return "bbr" in (read(CONGESTION) or "").split()
    return Path("/sys/module", module).exists()


def modules_task() -> Task:
    path = Path("/etc/modules")

    def probe() -> Probe:
        missing = tuning.modules_missing(read(path) or "", MODULES)
        if missing:
            return Probe(False, f"{path} lacks " + " ".join(missing))
        inactive = [m for m in MODULES if not module_active(m)]
        if inactive:
            return Probe(False, "not loaded: " + " ".join(inactive))
        return service_probe("modules", "boot", False)

    def apply() -> None:
        missing = tuning.modules_missing(read(path) or "", MODULES)
        if missing:
            text = read(path) or ""
            with path.open("a") as handle:
                handle.write(("" if not text or text.endswith("\n") else "\n") + "".join(m + "\n" for m in missing))
        ensure_service("modules", "boot", False)
        for module in MODULES:
            if not module_active(module) and not ok(["modprobe", module]):
                raise RuntimeError(f"could not load {module} for the running kernel; reboot after a kernel upgrade")

    return Task("kernel-modules", ("packages",), probe, apply, probe)


def sysctl_task() -> Task:
    file = Managed(Path("/etc/sysctl.d/90-home.conf"), 0o644, source=HERE / "config/sysctl.conf")
    wanted = tuning.parse_sysctl(file.content().decode())

    def live() -> Probe:
        values = {key: read(Path(tuning.sysctl_path(key))) for key in wanted}
        drift = tuning.sysctl_drift(wanted, values)
        return Probe(not drift, "; ".join(drift) if drift else f"{len(wanted)} values live")

    def apply() -> None:
        file.apply()
        ensure_service("sysctl", "boot", False)
        run(["sysctl", "-q", "-p", str(file.path)])

    return Task("sysctl", ("kernel-modules",), combine(file.probe, lambda: service_probe("sysctl", "boot", False), live),
                apply, combine(file.probe, live))


def power_task(ctx: Context) -> Task:
    tool = Managed(Path("/usr/local/sbin/power-policy"), 0o755, source=USR / "dotfiles/linux/.local/bin/power-policy")
    start = Managed(Path("/etc/local.d/home-power-policy.start"), 0o755, source=HERE / "config/power-policy.start")
    has_cpufreq = any(Path("/sys/devices/system/cpu/cpufreq").glob("policy*"))

    def live() -> Probe:
        mode = "auto" if ctx.mode == "desktop" else "performance"
        diff = run([str(tool.path), "diff", mode], check=False)
        changes = [line for line in diff.stdout.splitlines() if " -> " in line]
        if diff.returncode != 0 or changes:
            return Probe(False, "; ".join(changes) or diff.stderr.strip() or f"power-policy diff {mode} failed")
        return Probe(True, f"CPU policy {mode}")

    def probe() -> Probe:
        if not has_cpufreq:
            return Probe(True, "no cpufreq policies")
        return combine(tool.probe, start.probe, lambda: service_probe("local", "default", False), live)()

    def apply() -> None:
        tool.apply()
        start.apply()
        ensure_service("local", "default", False)
        run([str(start.path)])

    return Task("cpu-policy", ("install-mode",), probe, apply, probe)


@dataclass(frozen=True)
class BootLoader:
    defaults: Path
    key: str
    generated: Path
    regenerate: tuple[str, ...]
    microcode: bool


BOOTLOADERS = (
    BootLoader(Path("/etc/default/grub"), "GRUB_CMDLINE_LINUX_DEFAULT", Path("/boot/grub/grub.cfg"),
               ("grub-mkconfig", "-o", "/boot/grub/grub.cfg"), True),
    BootLoader(Path("/etc/update-extlinux.conf"), "default_kernel_opts", Path("/boot/extlinux.conf"),
               ("update-extlinux",), False),
)


def bootloader() -> BootLoader | None:
    return next((loader for loader in BOOTLOADERS if loader.defaults.is_file()), None)


def microcode_images() -> list[str]:
    return sorted(p.name for p in Path("/boot").glob("*-ucode.img"))


def boot_task(ctx: Context) -> Task:
    """Kernel options in the bootloader defaults, then a generated boot menu that carries them and the microcode."""

    def options_probe() -> Probe:
        if not tuning.required_options(ctx.cpu):
            return Probe(True, "no kernel options required")
        loader = bootloader()
        if loader is None:
            return Probe(False, "no /etc/default/grub or /etc/update-extlinux.conf; add "
                         + " ".join(tuning.required_options(ctx.cpu)) + " to the kernel command line by hand", conflict=True)
        try:
            options = tuning.parse_options(loader.defaults.read_text(), loader.key, ctx.cpu)
        except tuning.OptionsError as exc:
            return Probe(False, f"{loader.defaults}: {exc}; fix {loader.key}, then rerun", conflict=True)
        missing = options.missing(ctx.cpu)
        return Probe(not missing, f"{loader.key} lacks " + " ".join(missing) if missing else f"{loader.key} keeps TSC")

    def menu_probe() -> Probe:
        loader = bootloader()
        if loader is None:
            return Probe(True, "no managed bootloader")
        if not loader.generated.is_file():
            return Probe(False, f"{loader.generated} is missing; {loader.defaults} does not configure the installed bootloader",
                         conflict=True)
        lacking = tuning.boot_config_stale(loader.generated.read_text(), ctx.cpu,
                                           microcode_images() if loader.microcode else [])
        return Probe(not lacking, f"{loader.generated} lacks " + " ".join(lacking) if lacking else f"{loader.generated} current")

    def apply() -> None:
        loader = bootloader()
        assert loader is not None
        if not options_probe().current:
            options = tuning.parse_options(loader.defaults.read_text(), loader.key, ctx.cpu)
            mode = stat.S_IMODE(loader.defaults.stat().st_mode)
            write_atomic(loader.defaults, options.with_required(ctx.cpu).encode(), mode)
            print(f"home: added {' '.join(options.missing(ctx.cpu))} to {loader.key} in {loader.defaults}")
        if not menu_probe().current:
            run(list(loader.regenerate))
            print(f"home: regenerated {loader.generated}")

    return Task("boot-config", ("packages",), combine(options_probe, menu_probe), apply,
                combine(options_probe, menu_probe))


def reboot_needed(ctx: Context) -> str:
    """Why the running kernel lacks the boot configuration, or empty when it matches."""
    missing = tuning.cmdline_missing(read(Path("/proc/cmdline")) or "", ctx.cpu)
    if missing:
        return "the running kernel was booted without " + " ".join(missing)
    clock = (read(CLOCKSOURCE) or "").strip()
    if ctx.cpu.stable_tsc and not ctx.cpu.hypervisor and clock != "tsc":
        return f"the kernel clocksource is {clock}, not tsc"
    return ""


def tailscale_task(ctx: Context) -> Task:
    sock = Path("/run/tailscale/tailscaled.sock")

    def state() -> str:
        proc = run(["tailscale", "status", "--json"], check=False)
        try:
            backend = json.loads(proc.stdout or "{}").get("BackendState")
        except ValueError:
            backend = None
        return backend if isinstance(backend, str) else "Unknown"

    def probe() -> Probe:
        service = service_probe("tailscale", "default", True)
        if not service.current:
            return service
        if not sock.is_socket():
            return Probe(False, f"{sock} is missing")
        current = state()
        if current == "Running":
            ssh = run(["tailscale", "get", "ssh"], check=False).stdout.strip()
            return Probe(ssh == "true", "online with Tailscale SSH" if ssh == "true" else "Tailscale SSH is off")
        if current == "NeedsLogin":
            if ctx.authkey or sys.stderr.isatty():
                return Probe(False, "logged out")
            return Probe(True, "logged out; run: doas tailscale up --ssh")
        return Probe(False, f"tailscaled is in state {current}")

    def apply() -> None:
        ensure_service("tailscale", "default", True)
        for _ in range(20):
            if sock.is_socket() and state() in ("Running", "NeedsLogin"):
                break
            time.sleep(1)
        else:
            raise RuntimeError(f"tailscaled is in state {state()}; see /var/log/tailscaled.log")
        if state() == "Running":
            run(["tailscale", "set", "--ssh"])
        elif ctx.authkey:
            run(["tailscale", "up", "--ssh", f"--auth-key={ctx.authkey}", "--timeout=60s"])
        elif sys.stderr.isatty():
            print("home: Tailscale device authorization is required; open the URL printed below", file=sys.stderr)
            if not ok(["tailscale", "up", "--ssh", "--timeout=120s"], interactive=True):
                print("home: Tailscale authorization did not finish; run: doas tailscale up --ssh", file=sys.stderr)

    def verify() -> Probe:
        result = probe()
        if not result.current and state() == "NeedsLogin":
            return Probe(True, "logged out; run: doas tailscale up --ssh")
        return result

    return Task("tailscale", ("kernel-modules", "packages"), probe, apply, verify)


# ---- desktop tasks ------------------------------------------------------------------------------


def desktop_packages_task() -> Task:
    specs = list_file("packages-desktop.txt")
    base = apk_task("desktop-packages", specs, ("packages",))

    def probe() -> Probe:
        foot = [p for p in ("foot", "foot-extra-terminfo") if ok(["apk", "info", "-e", p])]
        if foot:
            return Probe(False, "remove " + " ".join(foot))
        return base.probe()

    def apply() -> None:
        base.apply()
        foot = [p for p in ("foot", "foot-extra-terminfo") if ok(["apk", "info", "-e", p])]
        if foot:
            run(["apk", "del", "--quiet", *foot])

    return Task("desktop-packages", ("packages",), probe, apply, probe, resources=frozenset({"apk"}))


def udev_task() -> Task:
    def probe() -> Probe:
        if not in_runlevel("udev", "sysinit"):
            return Probe(False, "udev does not manage devices")
        if in_runlevel("mdev", "sysinit"):
            return Probe(False, "mdev is still enabled")
        return Probe(True, "udev manages devices")

    return Task("udev", ("desktop-packages",), probe, runs(["setup-devd", "udev"]), probe)


def dwl_task() -> Task:
    dwl = Path("/usr/local/bin/dwl")

    def probe() -> Probe:
        if not dwl.exists():
            return Probe(False, "dwl is not built")
        version = run([str(dwl), "-v"], check=False)
        actual = (version.stdout + version.stderr).strip()
        if not re.match(r"dwl .*-home\.", actual):
            return Probe(False, f"{dwl} was not built by home; move it aside", conflict=True)
        want = run(["sh", "build/dwl.sh", "--version"]).stdout.strip()
        if actual != want:
            return Probe(False, f"{actual} differs from {want}")
        if ok(["apk", "info", "-e", ".home-dwl-build"]):
            return Probe(False, "dwl build dependencies remain")
        return Probe(True, actual)

    return Task("dwl", ("desktop-packages",), probe, runs(["sh", "build/dwl.sh"]), probe,
                resources=frozenset({"apk"}))


def ghostty_task() -> Task:
    binary, tag = Path("/usr/local/bin/ghostty-custom"), Path("/usr/local/share/home/ghostty-custom.tag")

    def probe() -> Probe:
        if binary.exists() or binary.is_symlink():
            if binary.is_symlink() or not binary.is_file():
                return Probe(False, f"{binary} exists and is not a regular file; move it aside", conflict=True)
            if not tag.is_file():
                return Probe(False, f"{binary} was not installed by home; move it aside", conflict=True)
            return Probe(True, (read(tag) or "").strip())
        return Probe(False, "ghostty-custom is not installed")

    def verify() -> Probe:
        result = probe()
        if result.current and not ok([str(binary), "--version"]):
            return Probe(False, "ghostty-custom does not run")
        return result

    return Task("ghostty", ("desktop-packages",), probe, runs(["sh", "build/ghostty.sh"]), verify,
                resources=frozenset({"apk"}), reconcile=True)


def helium_task(ctx: Context) -> Task:
    link, current = Path("/usr/local/bin/helium"), Path("/usr/local/lib/helium/current")

    def probe() -> Probe:
        if (link.exists() or link.is_symlink()) and not (
                link.is_symlink() and os.readlink(link) == str(current / "helium-wrapper")):
            return Probe(False, f"{link} exists and is not a home-managed symlink; move it aside", conflict=True)
        if (current.exists() or current.is_symlink()) and not current.is_symlink():
            return Probe(False, f"{current} exists and is not a home-managed symlink; move it aside", conflict=True)
        if ctx.arch != "x86_64":
            return Probe(True, f"helium is not built for {ctx.arch}")
        return Probe(link.is_symlink(), "installed" if link.is_symlink() else "helium is not installed")

    return Task("helium", ("desktop-packages",), probe,
                runs(["sh", "build/helium.sh"], env={**os.environ, "USER_NAME": ctx.user.name}), probe,
                resources=frozenset({"apk"}), reconcile=True)


def session_tasks(ctx: Context) -> list[Task]:
    conf = Managed(Path("/etc/conf.d/home-runtime"), 0o644, rendered=f'home_user="{ctx.user.name}"\n'.encode())

    def conf_probe() -> Probe:
        result = conf.probe()
        if result.conflict and conf.path.is_file():
            return Probe(False, f"{conf.path} configures a different user or was not written by home; remove it to "
                         f"provision {ctx.user.name}", conflict=True)
        return result

    def seat_probe() -> Probe:
        if not member(ctx.user, "seat"):
            return Probe(False, f"{ctx.user.name} is not in seat")
        return combine(lambda: service_probe("seatd", "default", True),
                       lambda: service_probe("home-runtime", "default", True))()

    def seat_apply() -> None:
        if not member(ctx.user, "seat"):
            run(["addgroup", ctx.user.name, "seat"])
        for service in ("seatd", "home-runtime"):
            ensure_service(service, "default", True)

    return [
        managed_task("volume", Managed(Path("/usr/local/bin/volume"), 0o755, source=HERE / "config/volume"), ("desktop-packages",)),
        managed_task("home-session", Managed(Path("/usr/local/bin/home-session"), 0o755, source=HERE / "config/home-session"),
                     ("desktop-packages",)),
        managed_task("home-runtime", Managed(Path("/etc/init.d/home-runtime"), 0o755, source=HERE / "services/home-runtime"),
                     ("desktop-packages",)),
        Task("home-runtime-conf", ("home-runtime",), conf_probe, conf.apply, conf_probe),
        Task("seat", ("home-runtime-conf", "home-session", "udev", "dwl", "ghostty"), seat_probe, seat_apply, seat_probe),
    ]


def bridge_task(ctx: Context) -> Task:
    def probe() -> Probe:
        configured = user_ok(ctx.user, f"python3 -I '{USR}/tools/sync/claude-worker.py' check")
        return Probe(configured, "Claude MCP bridge configured" if configured else "Claude MCP bridge is not configured")

    return Task("bridge", ("tools",), probe, user_runs(ctx.user, sync_cmd(ctx, "bridge")), probe)


def graph(ctx: Context) -> Graph:
    tasks = [
        apk_index_task(),
        apk_task("packages", packages(ctx), ("apk-index",)),
        rustup_task(ctx),
        doas_task(ctx),
        github_key_task(ctx),
        docker_task(ctx),
        clang_task(),
        install_mode_task(ctx),
        dotfiles_task(ctx),
        tools_task(ctx),
        login_hook_task(),
        modules_task(),
        sysctl_task(),
        power_task(ctx),
        boot_task(ctx),
    ]
    if ctx.mode == "desktop":
        tasks += [desktop_packages_task(), udev_task(), dwl_task(), ghostty_task(), helium_task(ctx),
                  *session_tasks(ctx), bridge_task(ctx)]
    others = tuple(task.name for task in tasks)
    tasks.append(tailscale_task(ctx))
    tailscale = tasks[-1]
    tasks[-1] = Task(tailscale.name, others, tailscale.probe, tailscale.apply, tailscale.verify)
    return Graph([guarded(task) for task in tasks])


def guarded(task: Task) -> Task:
    """A probe or verify that cannot run reports a failed check instead of aborting the whole plan."""

    def wrap(check: Callable[[], Probe]) -> Callable[[], Probe]:
        def probe() -> Probe:
            try:
                return check()
            except Exception as exc:
                return Probe(False, f"{type(exc).__name__}: {exc}")

        return probe

    return Task(task.name, task.needs, wrap(task.probe), task.apply, wrap(task.verify), task.resources, task.reconcile)


# ---- verify-only checks ------------------------------------------------------------------------


def command(name: str) -> bool:
    return any(os.access(Path(d) / name, os.X_OK) for d in os.environ.get("PATH", "/usr/bin:/bin").split(":") + ["/usr/sbin", "/sbin"])


def major_at_least(minimum: int, tool: str) -> bool:
    match = re.search(r"(\d+)\.\d+\.\d+", run([tool, "--version"], check=False).stdout or "")
    return bool(match) and int(match.group(1)) >= minimum


def libraries_resolve(binary: Path, env: dict[str, str] | None = None) -> bool:
    proc = run(["ldd", str(binary)], check=False, env=env)
    return binary.exists() and "not found" not in (proc.stdout + proc.stderr)


def no_extra_nopass(user: User) -> bool:
    texts = [read(Path("/etc/doas.conf")) or ""] + [p.read_text() for p in sorted(Path("/etc/doas.d").glob("*.conf"))]
    for text in texts:
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if "nopass" in line and line != f"permit nopass {user.name} as root" \
                    and "tailscale as root cmd /usr/sbin/resolvconf" not in line:
                return False
    return True


def root_file(path: Path, mode: int) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    st = path.stat()
    return (st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)) == (0, 0, mode)


def private_dir(path: Path, uid: int) -> bool:
    if not path.is_dir():
        return False
    st = path.stat()
    return (st.st_uid, stat.S_IMODE(st.st_mode)) == (uid, 0o700)


def checks(ctx: Context) -> list[tuple[str, Callable[[], bool]]]:
    """Runtime properties the task postconditions do not already establish."""
    user, home = ctx.user, ctx.user.home
    found: list[tuple[str, Callable[[], bool]]] = [
        (f"{name} installed", lambda name=name: command(name))
        for name in ("curl", "bash", "jq", "unzip", "zipinfo", "file", "ssh", "uv", "make", "dash", "shellcheck")
    ]
    found += [(f"{tool} is version 23 or newer", lambda tool=tool: major_at_least(23, tool)) for tool in ("clang", "ld.lld", "llc")]
    found += [
        ("no getty autologin", lambda: not re.search(r"--autologin|\s-a\s", read(Path("/etc/inittab")) or "")),
        ("no other passwordless doas rules", lambda: no_extra_nopass(user)),
        ("sudo not installed", lambda: not ok(["apk", "info", "-e", "sudo"])),
    ]
    tools = set(as_user(user, sync_cmd(ctx, "list", profile=True), check=False).stdout.split())
    if "ffmpeg" in tools:
        found += [(f"{b} reports version", lambda b=b: user_ok(user, f"'{home}/.local/bin/{b}' -version")) for b in ("ffmpeg", "ffprobe")]
    if "nodejs" in tools:
        found += [(f"{b} runs", lambda b=b: user_ok(user, f"PATH='{home}/.local/bin':$PATH '{home}/.local/bin/{b}' --version"))
                  for b in ("node", "npm", "pnpm")]
    if ctx.mode != "desktop":
        return found
    ghostty = Path("/usr/local/bin/ghostty-custom")
    found += [
        ("dwl shared libraries resolve", lambda: libraries_resolve(Path("/usr/local/bin/dwl"))),
        ("ghostty-custom release tracked",
         lambda: bool(re.fullmatch(r"release-[0-9a-f]+\n?", read(Path("/usr/local/share/home/ghostty-custom.tag")) or ""))),
        ("ghostty-custom installed, root 0755", lambda: root_file(ghostty, 0o755)),
        ("ghostty-custom shared libraries resolve", lambda: libraries_resolve(ghostty)),
        ("ghostty-custom shows config", lambda: ok([str(ghostty), "+show-config"])),
        ("ghostty terminfo installed", lambda: Path("/usr/share/terminfo/x/xterm-ghostty").is_file()),
        ("ghostty build dependencies removed", lambda: not ok(["apk", "info", "-e", ".home-ghostty-build"])),
        ("amixer installed", lambda: command("amixer")),
        *((f"{name} installed", lambda name=name: command(name)) for name in ("bemenu-run", "grim", "slurp", "wl-copy")),
        ("player shared libraries resolve", lambda: libraries_resolve(home / ".local/bin/player")),
        ("player reports version", lambda: user_ok(user, f"'{home}/.local/bin/player' --version")),
        ("Vulkan ICD installed", lambda: any(Path("/usr/share/vulkan/icd.d").glob("*.json"))),
        ("linux-lts not installed", lambda: not ok(["apk", "info", "-e", "linux-lts"])),
        ("running linux-stable", lambda: os.uname().release.endswith("-stable")),
        (f"/run/user/{user.uid} private to {user.name}", lambda: private_dir(Path(f"/run/user/{user.uid}"), user.uid)),
    ]
    if ctx.arch == "x86_64":
        current = Path("/usr/local/lib/helium/current")
        found += [
            ("helium tag recorded", lambda: bool(re.fullmatch(r"helium-[0-9].*\n?", read(Path("/usr/local/share/home/helium.tag")) or ""))),
            ("helium shared libraries resolve",
             lambda: libraries_resolve(current / "helium", {**os.environ, "LD_LIBRARY_PATH": str(current / "lib")})),
            ("helium reports version", lambda: user_ok(user, "/usr/local/bin/helium --version")),
            ("VA-API Intel driver installed", lambda: Path("/usr/lib/dri/i965_drv_video.so").is_file()),
        ]
        if Path("/dev/dri/renderD128").exists():
            found.append(("VA-API H.264 decode available to user", lambda: user_ok(user, "vainfo 2>/dev/null | grep -q VAProfileH264")))
    return found


# ---- preflight ----------------------------------------------------------------------------------


def os_release() -> dict[str, str]:
    values = {}
    for line in (read(Path("/etc/os-release")) or "").splitlines():
        key, sep, value = line.partition("=")
        if sep:
            values[key] = value.strip().strip('"')
    return values


def resolve_user(name: str) -> User:
    if name == "root":
        raise Refusal("USER_NAME must be a regular user, not root")
    try:
        entry = pwd.getpwnam(name)
    except KeyError:
        raise Refusal(f"user {name} does not exist; create it with setup-user or adduser") from None
    if entry.pw_uid < 1000:
        raise Refusal(f"user {name} has uid {entry.pw_uid}; a regular login (uid >= 1000) is required")
    home = Path(entry.pw_dir)
    if not home.is_dir() or home.stat().st_uid != entry.pw_uid:
        raise Refusal(f"home directory {home} of {name} is missing or not owned by {name}")
    return User(name, entry.pw_uid, entry.pw_gid, home)


def preflight(mode: str, user_name: str) -> Context:
    if os.geteuid() != 0:
        raise Refusal("run as root, for example: doas sh usr/host/alpine/install.sh")
    release = os_release()
    if release.get("ID") != "alpine":
        raise Refusal("this provisioner supports only Alpine Linux")
    version = release.get("VERSION_ID", "unknown")
    if "_alpha" not in version and "_git" not in version:
        raise Refusal(f"Alpine {version} is a stable release; this provisioner targets edge (see README)")
    arch = run(["apk", "--print-arch"]).stdout.strip()
    if arch not in ("x86_64", "aarch64"):
        raise Refusal(f"architecture {arch} is not supported")
    rootfs = ""
    for line in (read(Path("/proc/mounts")) or "").splitlines():
        fields = line.split()
        if len(fields) > 2 and fields[1] == "/":
            rootfs = fields[2]
    if rootfs in ("tmpfs", "ramfs", ""):
        raise Refusal(f"root filesystem is {rootfs}; install Alpine to disk (sys mode) first")
    git = ["git", "-c", f"safe.directory={USR}", "-C", str(USR)]
    if run([*git, "rev-parse", "--is-shallow-repository"], check=False).stdout.strip() != "false":
        raise Refusal("this checkout is shallow; home recognizes its installed files from full history: git fetch --unshallow")
    user = resolve_user(user_name)
    shadow = {line.split(":")[0]: line.split(":")[1] for line in (read(Path("/etc/shadow")) or "").splitlines() if ":" in line}
    if not shadow.get(user.name, "").startswith("$"):
        raise Refusal(f"user {user.name} has no usable password; set one with: passwd {user.name}")
    repos = [line.split("#", 1)[0].strip() for line in (read(Path("/etc/apk/repositories")) or "").splitlines()]
    repos = [repo for repo in repos if repo]
    if not repos:
        raise Refusal("/etc/apk/repositories is empty; run setup-apkrepos")
    if any(not re.search(r"/edge/(main|community)/*$", repo) for repo in repos):
        raise Refusal("only edge main and community repositories are supported; remove the others from /etc/apk/repositories")
    if not any(re.search(r"/edge/community/*$", repo) for repo in repos):
        raise Refusal("enable the edge community repository in /etc/apk/repositories")
    if mode == "server" and not list_file("tools-server.txt"):
        raise Refusal("tools-server.txt is missing or empty; the server tool profile cannot be selected")
    if not (USR / "sync").is_file() or not (USR / "tools/sync/links.py").is_file():
        raise Refusal(f"{USR} is not the usr checkout; clone {USR_URL} and run usr/host/alpine/install.sh from it")
    origin = as_user(user, f"git -C '{USR}' remote get-url origin", check=False)
    if origin.returncode != 0:
        raise Refusal(f"{USR} is not a git checkout")
    if origin.stdout.strip() not in USR_ORIGINS:
        raise Refusal(f"{USR} is a checkout of {origin.stdout.strip()}, not {USR_URL}")
    if mode == "desktop":
        if ok(["apk", "info", "-e", "linux-lts"]):
            raise Refusal("linux-lts is installed; this desktop runs linux-stable: apk add linux-stable && apk del linux-lts, then reboot")
        for line in (read(Path("/etc/inittab")) or "").splitlines():
            fields = line.split(":")
            if len(fields) > 2 and fields[0] == "tty0" and fields[2] == "respawn":
                raise Refusal("a getty on tty0 shares the tty1 console with the desktop login; comment out the tty0 line "
                              "in /etc/inittab and run: kill -HUP 1")
    cpu = tuning.parse_cpuinfo(arch, read(Path("/proc/cpuinfo")) or "")
    return Context(mode, user, arch, cpu, os.environ.get("TS_AUTHKEY", ""))


# ---- commands -----------------------------------------------------------------------------------


def lines_for(pairs: Iterable[tuple[str, str, str]]) -> list[report.TaskLine]:
    return [report.TaskLine(name, state, detail) for name, state, detail in pairs]


def render(title: str, lines: list[report.TaskLine], unhealthy: tuple[str, ...], show_all: bool) -> bool:
    color = report.use_color(sys.stdout)
    print(report.paint(f"home {title}", "1", color))
    for row in report.task_rows(lines, show_all, color):
        print(row)
    states = report.counts(lines, report.APPLY_STATES + report.PLAN_STATES)
    healthy = bool(report.healthy(states, unhealthy))
    mark = report.paint("✓", "32", color) if healthy else report.paint("✗", "31", color)
    print(f"  {mark} {report.summary({k: v for k, v in states.items() if v}, color)}")
    return healthy


def plan_lines(g: Graph) -> list[report.TaskLine]:
    return lines_for((task.name, "conflict" if probe.conflict else "current" if probe.current else "apply", probe.detail)
                     for task, probe in g.inspect())


def choose_mode(given: str | None) -> str:
    if given:
        if given not in MODES:
            raise Refusal(f"INSTALL_MODE must be server or desktop, not {given}")
        return given
    try:
        tty = open("/dev/tty", "r+")
    except OSError:
        raise Refusal("no terminal for the install type prompt; set INSTALL_MODE=server or INSTALL_MODE=desktop") from None
    with tty:
        while True:
            tty.write("home: install type, server or desktop: ")
            tty.flush()
            answer = tty.readline()
            if not answer:
                raise Refusal("no install type chosen; set INSTALL_MODE=server or INSTALL_MODE=desktop")
            choice = {"s": "server", "d": "desktop"}.get(answer.strip(), answer.strip())
            if choice in MODES:
                return choice
            tty.write("home: answer server or desktop\n")


def apply(mode: str, user: str, show_all: bool) -> int:
    print(f"home: installing {mode}")
    ctx = preflight(mode, user)
    g = graph(ctx)
    planned = plan_lines(g)
    conflicts = [line for line in planned if line.state == "conflict"]
    if conflicts:
        render("plan", planned, report.UNHEALTHY, show_all)
        print("home: resolve each conflict, then rerun; nothing was changed", file=sys.stderr)
        return 1
    results: list[Result] = g.run(jobs=1)
    healthy = render("apply", lines_for((r.name, r.state, r.detail) for r in results), report.UNHEALTHY, show_all)
    if not healthy:
        return 1
    reason = reboot_needed(ctx)
    if reason:
        print(f"home: {reason}; reboot to apply the boot configuration")
    if mode == "server":
        print(f"home: provisioned server for {ctx.user.name}. Run: doas sh usr/host/alpine/verify.sh server")
    else:
        print(f"home: provisioned desktop. Log out, then log in as {ctx.user.name} on tty1. Run: doas sh usr/host/alpine/verify.sh")
    return 0


def verify(mode: str, user: str, show_all: bool) -> int:
    ctx = preflight(mode, user)
    g = graph(ctx)
    lines = []
    for task in g.order():
        try:
            probe = task.verify()
        except Exception as exc:  # a verification command that cannot run is a failed check
            probe = Probe(False, f"{type(exc).__name__}: {exc}")
        lines.append((task.name, "conflict" if probe.conflict else "current" if probe.current else "failed", probe.detail))
    for label, check in checks(ctx):
        try:
            passed = check()
        except Exception as exc:
            passed, label = False, f"{label}: {type(exc).__name__}: {exc}"
        lines.append((label, "current" if passed else "failed", ""))
    reason = reboot_needed(ctx)
    if reason:
        lines.append(("reboot", "failed", f"{reason}; reboot to apply the boot configuration"))
    healthy = render(f"verify {mode}", lines_for(lines), report.UNHEALTHY, show_all)
    return 0 if healthy else 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="provision", description="Provision or verify an Alpine edge host.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("apply", "plan", "verify"):
        cmd = sub.add_parser(name)
        cmd.add_argument("mode", nargs="?", choices=MODES)
        cmd.add_argument("--all", action="store_true", help="show up-to-date tasks too")
    args = parser.parse_args(argv)
    user = os.environ.get("USER_NAME", "josh")
    try:
        if args.command == "apply":
            return apply(choose_mode(args.mode or os.environ.get("INSTALL_MODE")), user, args.all)
        mode = args.mode or (read(INSTALL_MODE) or "").strip() or "desktop"
        if args.command == "verify":
            return verify(mode, user, args.all)
        ctx = preflight(mode, user)
        return 0 if render(f"plan {mode}", plan_lines(graph(ctx)), report.UNHEALTHY, True) else 1
    except Refusal as exc:
        print(f"home: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
