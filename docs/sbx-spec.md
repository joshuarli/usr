# `sbx`: native process confinement (specification and audit contract)

Status: implemented and validated live on macOS 27 (Seatbelt) and Debian stable-slim (bubblewrap); see Verification status. This document is normative for the CLI contract; the [implementation](../dotfiles/base/.local/bin/sbx) and [tests](../dotfiles/sbx-test.py) are the concrete enforcement. The implementation is not a drop-in replacement for Anthropic's sandbox-runtime and **is not a microVM**.

## Purpose

Run an arbitrary coding-agent process with access to a specific working tree, explicit additional directories, ordinary system executables and libraries, and optionally the checked-in `usr` skills. The same CLI works on macOS and Linux, with no Python packages, daemon, credential proxy, or firewall rules to maintain. Stronger isolation (untrusted binaries, mutually hostile users, hostile root workloads) belongs in `smolvm`/another VM.

## Interface

```console
sbx [--ro DIR]... [--rw DIR]... [--offline] [--no-skills] [--explain] [-- COMMAND [ARG...]]
```

- Default: run an interactive `/bin/zsh` on macOS and `/bin/sh` on Linux. Execute an explicit command with arguments without a shell string or `eval`.
- CWD is implicitly and recursively **read/write**. It stays at its **canonical absolute path** in the child. All edits in it are real host edits. CWD equal to the host home or an ancestor of it is prohibited. A CWD anywhere under the home (including `~/d/project`) is permitted.
- `--ro DIR` and `--rw DIR` each accept an existing **directory**, more than once. They expose those trees at their canonical absolute host paths. They are read-only and read/write, respectively. Source paths are canonicalized before rules/mounts are built, including symlink resolution. No per-file grants or globs. File/dir access within these trees is still limited by normal host identity/permissions.
- Overlapping or duplicate explicit grants (including a parent of the project or an alias that resolves into another grant) are rejected, independently of their modes. The host home and any ancestor of it are never eligible as a grant. Granting another directory deliberately grants all of its contents, including secrets it may contain.
- `--offline` disables direct IP network access. With no flag, network access is unrestricted: there is **no host/domain allowlist**. Offline does not promise that all IPC or all forms of indirect networking are impossible.
- `--no-skills` omits the optional tracked `usr` source mounts and adapters. Otherwise, install the tracked `usr` resources if `~/usr/dotfiles/base` is present, or omit them if that tree is absent. If that tree exists but required skill/instruction paths are malformed or redirect outside it, fail before launching.
- `--explain` prints the canonical grants, network mode, executable argv and a backend plan (full Seatbelt policy on macOS). It exits without running the workload; it is **not** a sandbox penetration test. Flags belong before the command, preferably separated from it with `--`.
- Exit code: propagate the child's exit code when possible; failure to prepare/launch fails nonzero and **never** runs the command outside a sandbox. Command-line help is provided by `argparse`.

### Examples

```sh
cd ~/d/project
sbx                         # isolated shell, edits in cwd land on host
sbx -- codex                 # installed command must be accessible within the sandbox
sbx --ro ~/d/references --rw ~/d/shared -- opencode
sbx --offline -- sh -c 'pwd; ls -la'
sbx --explain -- /bin/sh
```

System-level agent binaries can be resolved from the constrained PATH. If a coding agent binary or its runtime lives elsewhere under the real user home, its **minimal dependency directory** needs an explicit `--ro` grant. Do not grant `~/.config`, `~/.codex`, `~/.claude`, or another credential-bearing directory merely to execute a binary. Move/copy a vetted executable into a dedicated non-secret directory if needed. Authentication is intentionally **not** automatically provided; interactive login tokens stored in the private HOME will be lost when the session exits. Secrets explicitly entered or created during the session are available to the child.

## Threat model

- **Defend against:** opportunistic reads of unrelated home files, accidental writes outside explicitly writable trees, host filesystem traversal through symlinks, inherited environment-based secret exposure, accidental access to host agent credentials, and direct network access when `--offline` is set.
- **Do not promise defense against:** kernel/hypervisor escapes, OS bugs, malicious changes to files inside granted writable trees, exfiltration of explicitly granted files when online, terminal escape sequences, hardlinks already present in writable trees, filesystem races by concurrently running host processes, processes invoking host OS services over allowed IPC, or deliberate grants to sensitive directories. The sandbox's host launcher and its external backend are trusted.
- Child processes inherit the OS confinement. This is **not** a different UID on macOS, and Linux user namespaces/mount namespaces do not provide a separate kernel.
- The host OS still has authority over running processes. Root, privileged services, debuggers, endpoint protection and administrators are outside scope. Do not run this as root to sandbox adversarial binaries.
- A path with a symlink **inside the project** is not automatically expanded to its host target in the grant list. On Linux a missing target lies outside the constructed guest mount namespace; on macOS the target must match some other explicit/system read rule or will be denied. A symlink into the deliberately exposed system runtime is readable. This is not a blanket prohibition on all out-of-project path resolutions.

## Common policy construction

1. Read the real account home from `pwd.getpwuid(os.getuid()).pw_dir`, not an inherited `HOME` override. Resolve all user paths and verify directories. Reject control characters, invalid paths, overlapping grants, home-wide grants, and symlinked `.git` entries.
2. Build a **minimal** child environment from scratch: `HOME`, `USER`, `LOGNAME`, a fixed system PATH, private `TMPDIR`, `PYTHONNOUSERSITE=1`, and validated terminal/locale formatting variables (`TERM`, `COLORTERM`, `LANG`, `LC_ALL`, `LC_CTYPE`). Do not inherit SSH_AUTH_SOCK, GIT_ASKPASS, API tokens, `PYTHONPATH`, dynamic-loader override variables, cloud credentials, proxy settings or runtime options.
3. Do not implicitly map the user's real home or browser/coding-agent state. Only the specified project, explicit grants, ordinary system runtime paths, and tracked, read-only skills/instructions are exposed.
4. Do not use the host shell to interpolate command arguments. Invoke a list of argv tokens directly, with standard input/output/error inherited for interactive operation.
5. Do not silently relax a sandbox after backend failure or unsupported machine setup. No `--unsafe`, partial backend, or host-execution fallback.
6. Attempt to protect the initial project's `.git` metadata from writes. This mitigates one persistence vector but **does not constitute comprehensive Git hardening**. A user should inspect all writable results before executing them unsandboxed.

## Tracked `usr` resource preloading

When `~/usr/dotfiles/base` exists, sources are **only**:

| Host-side tracked source | Private child location | Access |
| --- | --- | --- |
| `dotfiles/base/.agents/skills/` | `~/.agents/skills/` | read-only |
| `dotfiles/base/.codex/AGENTS.md` | `~/.codex/AGENTS.md` | read-only |
| `dotfiles/base/.claude/agents/`, if present | `~/.claude/agents/` | read-only |
| `dotfiles/base/.grok/agents/`, if present | `~/.grok/agents/` | read-only |

The private home also receives relative symlink adapters for Claude's `CLAUDE.md` and skills, Grok instructions, Muse/OpenCode/Antigravity instructions and skills, DeepSeek, and Command Code. All adapters refer only to the canonical instruction file or shared skills; they **do not** import normal user-level agent settings, auth, tokens, plugin state, history, logs, hooks, or caches. Other repository files are not mounted solely because `usr` is present. A user's CWD may itself be `~/usr`, in which case its normal writable-project grant encompasses those tracked sources: the read-only *alias* does not make the original project immutable.

The private home is disposable. The host paths of the skills and instructions are validated before constructing the policy: if a checked-in source symlink points beyond the tracked source tree, launching is refused. Symlinks inside a permitted skill tree can point to visible paths or to unavailable paths, but do not independently grant access to their external targets.

## macOS backend

**Requirement:** working `/usr/bin/sandbox-exec` with Seatbelt profile version 1. No other sandboxing helper or Node runtime. Compatibility with **macOS 27** must be checked on a real device; successful policy generation does not prove the kernel honors a rule as intended.

- A new `0700` temporary directory hosts private `HOME`, private `TMPDIR`, symlink adapters and a mode-`0600` Seatbelt profile. It is deleted after command exit (subject to abrupt process termination). `HOME` is an ephemeral path, so `~` expands there; the **CWD** and explicitly granted absolute paths still match the host.
- The profile begins `(deny default)`. Allow only same-sandbox process execution/forking/observation/signals, limited ordinary Mach services for logging and identity lookups, sysctl reads, POSIX IPC primitives, directory metadata lookups, and pty/stdio operations. **Never** grant wildcard `mach-lookup`, `appleevent-send`, `lsopen`, access to `com.apple.SecurityServer`, or `com.apple.securityd.xpc` in the first-party profile. Online mode additionally allows Mach lookup of `com.apple.SystemConfiguration.configd` and `com.apple.SystemConfiguration.DNSConfiguration`, without which even `localhost` fails to resolve (verified live); offline mode omits them together with `network*`.
- Allow file contents to be read only under explicit grant roots, private scratch, the tracked source roots, and an enumerated set of system/runtime paths: `/`, the standard `/var` symlink (literal, so the resolver can traverse its `/var`-spelled IPC path), `/System`, `/usr`, `/bin`, `/sbin`, `/Library/Frameworks`, `/opt/homebrew`, `/private/etc/ssl`, selected `/private/etc` name-service files, and standard devices. These system paths may themselves contain system-wide files or configuration; this is not a fully hermetic system image. Ordinary file-read access to the host's Keychains or account home is not granted.
- Allow writes only in the project, additional `--rw` roots, private scratch and necessary terminal devices. The initial `.git` metadata present at launch gets granular deny rules (`file-write-data`, `file-write-create`, `file-write-unlink` on its subpath): a blanket `file-write*` deny does not subtract from the parent project's allow on macOS 27 (verified live: writes succeeded regardless of rule order). Because rename and link semantics are complex, test rather than assume complete persistence defense.
- With `--offline`, no network allow operation is emitted. Online emits `(allow network*)`. Denying direct networking does not guarantee the absence of all system-mediated networking on macOS.
- Access to nonstandard executables/frameworks/fonts/services can fail. No automatic fallback to relaxed policies. Use the explain output and add **narrow** explicit grants for nonsecret dependencies.

## Linux backend

**Requirement:** `bwrap` (bubblewrap), installed separately using the OS package manager, and kernel support for its namespace setup (or a distro-provided setuid bubblewrap). No Docker, chroot daemon, systemd, or Python dependency. Rootless execution is preferred.

- Start with a **new, empty tmpfs root**. Use `--unshare-all` to isolate user (where possible), mount, PID, IPC, UTS, cgroup and network namespaces; `--die-with-parent`, `--new-session` (mitigates TIOCSTI), and `--clearenv`. Never fall back to direct execution if namespace creation fails. Online mode adds `--share-net` after `--unshare-all` to retain **unrestricted host network namespace access**; offline retains the private network namespace.
- Mount `/proc` from the new PID namespace, a minimal `/dev`, and ephemeral `/tmp` and `/run`. Make `/etc` a new private directory containing only selected read-only name-service, linker, trust-store and identity files from the host; do **not** bind the host's entire `/etc`, `/run`, `/var`, `/sys`, or home. Read-only bind `/usr`, `/bin`, `/lib`, `/lib64`, `/sbin`, and present CA roots so ordinary host-linked executables and Python can start. These system runtime directories are not filtered internally; any secrets stored there are readable.
- Create an empty guest home **at the same textual path as the account's actual host home**. Unlike macOS, this preserves conventional `~/d/project` paths within the sandbox. Bind the project and explicit grants at identical canonical guest paths, with the requested modes. The host home itself is **never** mounted. A symlink to an unrelated host home path resolves against the guest namespace, so it cannot reach an unmounted host path.
- If `.git` exists at the initial CWD root and is not a symlink, overlay it with a read-only bind. Other existing or newly created nested `.git` directories, hardlinked metadata, and code-edit persistence are **not** comprehensively protected.
- Bind tracked `usr` source directories/files read-only into the private guest home, then create only the documented relative symlink adapters. Reject project or extra grants overlapping any of these guest adapter destinations (otherwise bwrap could create an alias inside a writable host mount). No host credential/SSH-agent/Unix-socket directory grants. Runtime options are passed as argv to bubblewrap, never through a shell.
- Unprivileged user namespaces can be disabled by distribution policy. In that case bubblewrap may fail; **sbx must report the error and refuse to launch**. The restricted PATH may not find binaries installed only under user-specific package stores; use a narrowly scoped `--ro` mount.

## Audit invariants and acceptance tests

Use `TMPDIR="$PWD/.work/tmp" python3 -I dotfiles/sbx-test.py` for unit/policy checks, and opt in to `--live` on a supported host. Tests in the checked-in suite are intended to demonstrate all of the following; missing backend tools or privileges should fail a live test, not result in host execution:

| ID | Invariant / acceptance |
| --- | --- |
| P01 | CWD gets one read/write grant and a canonical, unchanged child absolute path |
| P02 | Extra read-only roots cannot be written; read/write roots can be written |
| P03 | `HOME`, `/`, ancestors of `HOME`, duplicate and overlapping grants are rejected |
| P04 | Symlinks into **unmounted/unauthorized sensitive trees** do not escape the read policy |
| P05 | No normal host home, `~/.ssh`, agent cache, credential environment, or host SSH agent is injected |
| P06 | Global instructions and shared skills are discoverable using regular harness aliases without exposing harness credentials |
| P07 | Linux namespace construction excludes host `/run`, home, and full `/etc`; environment is cleared; host network is shared only when online |
| P08 | macOS starts deny-default with explicit system/skill/grant reads, does not grant Keychain services or AppleEvents, and denies direct network access in offline mode |
| P09 | Plain shell command arguments are passed as argv, without shell expansion by the wrapper |
| P10 | Missing backend, invalid profile, or failed setup never executes the original command without isolation |
| P11 | Existing initial `.git` metadata is read-only on Linux, and write-denied by explicit rules on macOS; more complicated persistence is outside the guarantee |
| P12 | `--explain` only explains; it never runs the command |

### Manual adversarial review checklist

On **each target OS**, using only throwaway directories and throwaway credentials:

1. Test a project at `~/d/project`, `--ro`, `--rw`, an offline request, interactive shell/pty, subprocess fork/exec, non-ASCII/quote/bracket paths, and a project with both a `.git` directory and a Git linked worktree.
2. Add symlinks from project to unrelated home secrets, sibling directories, `..`, an allowed runtime root, and a relative path outside the project. Check attempted reads/writes by absolute and symlinked spelling.
3. Test moving/renaming `.git` and writable subdirectories, hardlink aliases, and creating new nested `.git` trees; record every bypass that persists beyond the sandbox. Do not declare full Git persistence protection on the strength of simple read-only tests.
4. Verify that an agent cannot retrieve a **dummy** Keychain item on macOS, launch another unsandboxed app using `open`/Apple Events, or use an unauthorized Unix socket. Account for OS-level prompts and persistent TCC grants.
5. Verify that on Linux the guest sees its own `/proc`, fails to access real host home and `/run` sockets, and cannot escape via symlinks. Check the UID/GID mapping, actual mount flags and rootless namespace creation on the chosen distribution.
6. Confirm that `--offline` prevents TCP to a known loopback server. Explicitly test IPC sockets created inside a granted directory because those may remain reachable despite `--offline`.
7. Use a clean test account to verify dynamic-loader, CA trust, DNS, shell interactivity and one representative coding agent. The entire flow must fail closed if a required system path is missing.

## Deliberate omissions

No domain-specific network allowlists, proxy/CONNECT/SOCKS server, TLS interception, credential substitution, file masking or redaction, dynamic policy changes, daemon, telemetry/violation log parser, config language, persistent sandbox home, shell integration, container image management, Windows support, automated agent installation, or invisible access to real agent authentication state. The project opts for a small auditable core rather than unverified parity with Anthropic SRT.

## Verification status and upstream reference

Static Python unit/policy tests validate construction of grants, mount arguments, environment and profile clauses; they cannot prove host-kernel isolation. Live validation (`--live`) was run on macOS 27 (Seatbelt) and Debian stable-slim with bubblewrap in a privileged container: CWD/rw/ro enforcement, symlink-escape denial, private-home and credential isolation, offline network denial with online loopback connectivity, `localhost` resolution, initial-`.git` write/rename denial, argv passthrough, and fail-closed behavior all passed. Findings confirmed live and encoded above: the macOS `.git` protection needs granular deny operations, and macOS DNS resolution needs the configd Mach lookups.

Implementation references: [Anthropic Sandbox Runtime](https://github.com/anthropics/sandbox-runtime), especially `macos-sandbox-utils.ts` and symlink/move tests; [Bubblewrap](https://github.com/containers/bubblewrap), for mount namespace and argv semantics. This is an independently scoped implementation, not a line-for-line port of either project.
