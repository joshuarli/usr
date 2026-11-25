"""Read the repository's single harness switchboard without probing clients."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import sys
from typing import Mapping

ROOT = Path(__file__).resolve().parents[2]
HARNESS_IDS = frozenset({
    "claude", "codex", "command-code", "pi", "opencode", "opencode-go",
    "devin", "antigravity", "copilot", "fx", "muse", "deepseek",
})
CLI_HARNESSES = {
    "claude": "claude", "codex": "codex", "cmd": "command-code",
    "pi": "pi", "opencode": "opencode", "devin": "devin",
    "agy": "antigravity", "antigravity": "antigravity",
    "copilot": "copilot", "fx": "fx", "muse": "muse", "dsh": "deepseek",
}
CONTEXT_HARNESSES = {
    ".claude": "claude", ".codex": "codex", ".commandcode": "command-code",
    ".pi": "pi", ".config/opencode": "opencode", ".config/devin": "devin",
    ".gemini": "antigravity", ".copilot": "copilot", ".fx": "fx",
    ".config/muse": "muse", ".config/dsh": "deepseek", ".dsh": "deepseek",
}


def read_switches(root: Path = ROOT) -> dict[str, bool]:
    path = root / "harnesses.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != HARNESS_IDS:
        raise ValueError(f"{path}: expected exactly the supported harness IDs")
    if any(type(enabled) is not bool for enabled in value.values()):
        raise ValueError(f"{path}: harness switches must be booleans")
    return {key: value[key] is True for key in HARNESS_IDS}


def tool_enabled(tool: str, switches: Mapping[str, bool]) -> bool:
    """Non-harness tools are unaffected by the switchboard."""
    harness = CLI_HARNESSES.get(tool)
    return harness is None or switches[harness]


def install_enabled(tool: str, switches: Mapping[str, bool]) -> bool:
    # Pi Go still needs OpenCode's read-only credential-export command. Keeping
    # that executable does not enable its native configuration or launch path.
    return tool_enabled(tool, switches) or (tool == "opencode" and switches["pi"] and switches["opencode-go"])


def context_enabled(relative: PurePosixPath, switches: Mapping[str, bool]) -> bool:
    # All normal-contract adapters point here, including non-Codex harnesses.
    if relative == PurePosixPath(".codex/AGENTS.md"):
        return True
    for prefix, harness in CONTEXT_HARNESSES.items():
        parent = PurePosixPath(prefix)
        if relative == parent or parent in relative.parents:
            if not switches[harness]:
                return False
            break
    profiles = PurePosixPath(".pi/agent/agents")
    if profiles in relative.parents:
        if relative.name.startswith("devin-"):
            return switches["devin"]
        if relative.stem in {"scout", "mechanic", "worker", "expert"}:
            return switches["opencode-go"]
    return True


PI_PROVIDERS = frozenset({"opencode-go", "devin"})
# Value-taking flags in the pinned Pi parser. A flag-looking value is still a
# value (for example --system-prompt --provider), not a provider override.
PI_VALUE_OPTIONS = frozenset({
    "--provider", "--model", "--api-key", "--system-prompt", "--append-system-prompt",
    "--name", "-n", "--session", "--session-id", "--fork", "--session-dir", "--models",
    "--tools", "-t", "--exclude-tools", "-xt", "--thinking", "--export", "--extension",
    "-e", "--skill", "--prompt-template", "--theme",
})


def pi_launch_error(argv: list[str], switches: Mapping[str, bool]) -> str | None:
    """Check known provider choices before starting Pi; never rewrite its args.

    The native extension checks the actual resolved model for session restores,
    fuzzy models and interactive changes. The shim refuses a disabled default
    until an explicit enabled provider/model has been chosen.
    """
    if argv and argv[0] in {"auth", "install", "remove", "update", "list", "config", "mcp"}:
        return None
    provider = model = None
    maintenance = no_extensions = False
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--":
            break
        if arg in {"--help", "-h", "--version", "-v", "--list-models"}:
            maintenance = True
        if arg in {"--no-extensions", "-ne"}:
            no_extensions = True
        if arg in PI_VALUE_OPTIONS and index + 1 < len(argv):
            index += 1
            if arg == "--provider":
                provider = argv[index].lower()
            elif arg == "--model":
                model = argv[index]
            elif arg == "--export":
                maintenance = True
        index += 1
    if maintenance:
        return None
    disabled = PI_PROVIDERS - {key for key in PI_PROVIDERS if switches[key]}
    if not disabled:
        return None
    if no_extensions:
        return "Pi provider switches require its provider-switches extension; remove --no-extensions/-ne"
    model_provider = model.partition("/")[0].lower() if model and "/" in model else None
    # Either explicit spelling of a disabled provider is refused; contradictory
    # choices are otherwise left for Pi's own model resolver to diagnose.
    for selected in (provider, model_provider):
        if selected in disabled:
            return f"Pi provider {selected!r} is disabled in {ROOT / 'harnesses.json'}; choose an enabled --provider with --model"
    if model and (provider or model_provider):
        return None
    settings: dict[str, object] = {}
    agent_dir = Path(os.environ.get("PI_CODING_AGENT_DIR") or Path.home() / ".pi/agent").expanduser()
    paths = (ROOT / "dotfiles/base/.pi/agent/settings.json", agent_dir / "settings.json", Path.cwd() / ".pi/settings.json")
    for path in paths:
        if path.is_file():
            value = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(value, dict):
                raise ValueError(f"{path}: expected Pi settings object")
            settings.update(value)
    selected = settings.get("defaultProvider")
    if selected is not None and not isinstance(selected, str):
        raise ValueError("Pi defaultProvider must be a string")
    if selected in disabled:
        return f"Pi default provider {selected!r} is disabled in {ROOT / 'harnesses.json'}; choose an enabled --provider with --model (no automatic model substitution)"
    if model:
        return "Pi cannot preflight an unqualified --model while a provider is disabled; choose an enabled --provider with --model"
    return None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="harness-enabled", allow_abbrev=False,
        description="Check the current usr checkout's harness switches without starting or probing clients.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Aliases:
  cmd = command-code; agy = antigravity; dsh = deepseek.

Inputs:
  The current checkout's harnesses.json is the only enable/disable source.
  Pi launch checks read its tracked defaults, HOME/.pi/agent/settings.json
  (or PI_CODING_AGENT_DIR/settings.json), and the current directory's
  .pi/settings.json. Environment variables cannot enable a disabled harness.

Exit status:
  0  Enabled, permitted credential dependency, help or version.
  1  Disabled harness/provider or blocked Pi launch.
  2  Invalid arguments or malformed/unreadable configuration.

Examples:
  harness-enabled cmd
  harness-enabled opencode --auth-export
  harness-enabled pi --launch --provider devin --model MODEL
  harness-enabled pi --launch -- --literal-prompt

Bare invocation prints this help. After --launch, all arguments belong to Pi,
including --help and --; they are checked without being rewritten.""",
    )
    parser.add_argument("harness", nargs="?", metavar="HARNESS",
                        choices=sorted(HARNESS_IDS | CLI_HARNESSES.keys()),
                        help="switch ID: " + ", ".join(sorted(HARNESS_IDS)) + "; aliases listed below")
    parser.add_argument("--version", action="version", version="%(prog)s 1.0")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--auth-export", action="store_true",
                      help="for opencode: also permit the enabled Pi/OpenCode Go credential dependency")
    mode.add_argument("--launch", nargs=argparse.REMAINDER, metavar="PI_ARG",
                      help="for pi: check its provider choice; remaining arguments are opaque Pi arguments")
    if not argv:
        parser.print_help()
        return 0
    args, remaining = parser.parse_known_args(argv)
    if args.harness is None:
        parser.error("HARNESS is required")
    # argparse stops even REMAINDER at a standalone --. Restore that boundary
    # and its following tokens without interpreting or rewriting Pi's argv.
    if remaining and (args.launch is None or remaining[0] != "--"):
        parser.error("unrecognized arguments: " + " ".join(remaining))
    name = CLI_HARNESSES.get(args.harness, args.harness)
    if args.auth_export and name != "opencode":
        parser.error("--auth-export requires opencode")
    if args.launch is not None and name != "pi":
        parser.error("--launch requires pi")
    try:
        switches = read_switches()
        enabled = switches[name] or (args.auth_export and switches["pi"] and switches["opencode-go"])
        if enabled and args.launch is not None:
            error = pi_launch_error([*args.launch, *remaining], switches)
            if error:
                print(error, file=sys.stderr)
                return 1
    except (OSError, ValueError) as error:
        print(f"harness-enabled: {error}", file=sys.stderr)
        return 2
    if not enabled:
        print(f"{args.harness} is disabled in {ROOT / 'harnesses.json'}; enable {name!r} and run make generate", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
