"""Pure performance policy: kernel boot options, sysctl values and boot-config freshness."""

from __future__ import annotations

from dataclasses import dataclass


class OptionsError(ValueError):
    """The bootloader defaults cannot be edited safely; the operator must resolve it."""


@dataclass(frozen=True)
class Cpu:
    arch: str
    flags: frozenset[str]
    hypervisor: bool

    @property
    def stable_tsc(self) -> bool:
        return self.arch == "x86_64" and {"constant_tsc", "nonstop_tsc"} <= self.flags


def parse_cpuinfo(arch: str, text: str) -> Cpu:
    flags: set[str] = set()
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() in ("flags", "Features"):
            flags.update(value.split())
            break
    return Cpu(arch, frozenset(flags), "hypervisor" in flags)


def keeps_tsc(word: str) -> bool:
    if not word.startswith("tsc="):
        return False
    return bool({"nowatchdog", "reliable"} & set(word[4:].split(",")))


def required_options(cpu: Cpu) -> tuple[str, ...]:
    """Kernel options this CPU needs; tsc=nowatchdog stops the clocksource watchdog from demoting TSC under load."""
    return ("tsc=nowatchdog",) if cpu.stable_tsc else ()


def satisfied(words: list[str], option: str) -> bool:
    if option == "tsc=nowatchdog":
        return any(keeps_tsc(word) for word in words)
    return option in words


def conflicts(words: list[str], cpu: Cpu) -> list[str]:
    if not cpu.stable_tsc:
        return []
    found = []
    for word in words:
        if word == "notsc":
            found.append("notsc disables the TSC")
        elif word.startswith("clocksource=") and word != "clocksource=tsc":
            found.append(f"{word} selects another clocksource")
        elif word.startswith("tsc=") and not keeps_tsc(word):
            found.append(f"{word} is set without nowatchdog or reliable; merge nowatchdog into it")
    return found


@dataclass(frozen=True)
class Options:
    """One KEY="..." line in /etc/default/grub or /etc/update-extlinux.conf."""

    lines: tuple[str, ...]
    index: int
    key: str
    words: tuple[str, ...]

    def missing(self, cpu: Cpu) -> list[str]:
        return [option for option in required_options(cpu) if not satisfied(list(self.words), option)]

    def with_required(self, cpu: Cpu) -> str:
        words = [*self.words, *self.missing(cpu)]
        lines = list(self.lines)
        lines[self.index] = f'{self.key}="{" ".join(words)}"'
        return "".join(line + "\n" for line in lines)


def parse_options(text: str, key: str, cpu: Cpu) -> Options:
    lines = tuple(text.splitlines())
    hits = [i for i, line in enumerate(lines) if line.startswith(key + "=")]
    if not hits:
        raise OptionsError(f"{key} is not set")
    if len(hits) > 1:
        raise OptionsError(f"{key} is set more than once")
    value = lines[hits[0]][len(key) + 1:]
    if len(value) < 2 or value[0] != '"' or value[-1] != '"' or '"' in value[1:-1]:
        raise OptionsError(f"{key} must be a double-quoted string")
    words = tuple(value[1:-1].split())
    problems = conflicts(list(words), cpu)
    if problems:
        raise OptionsError("; ".join(problems))
    return Options(lines, hits[0], key, words)


def boot_config_stale(generated: str, cpu: Cpu, microcode: list[str]) -> list[str]:
    """What the generated boot menu lacks: required kernel options or installed microcode images."""
    lacking = []
    words = generated.split()
    for option in required_options(cpu):
        if not satisfied(words, option):
            lacking.append(option)
    for image in microcode:
        if not any(word == image or word.endswith("/" + image) for word in words):
            lacking.append(image)
    return lacking


def cmdline_missing(cmdline: str, cpu: Cpu) -> list[str]:
    words = cmdline.split()
    return [option for option in required_options(cpu) if not satisfied(words, option)]


def parse_sysctl(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, sep, value = line.partition("=")
        if not sep:
            raise ValueError(f"not a sysctl assignment: {raw!r}")
        values[key.strip()] = " ".join(value.split())
    return values


def sysctl_path(key: str) -> str:
    return "/proc/sys/" + key.replace(".", "/")


def sysctl_drift(wanted: dict[str, str], read: dict[str, str | None]) -> list[str]:
    drift = []
    for key, value in wanted.items():
        actual = read.get(key)
        if actual is None:
            drift.append(f"{key} is unavailable")
        elif " ".join(actual.split()) != value:
            drift.append(f"{key}={' '.join(actual.split())}, want {value}")
    return drift


def modules_missing(text: str, wanted: tuple[str, ...]) -> list[str]:
    present = {line.split("#", 1)[0].strip() for line in text.splitlines()}
    return [module for module in wanted if module not in present]
