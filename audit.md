# Actionable Executable Audit

Executables that `usr` uses, invokes, or configures, but does not set up. Standard OS built-ins (macOS `/usr/bin/*` like `trash`, `zip`, `lsof`, `openssl`, `sqlite3`, `less`, and Alpine standard utilities like `wget`, `sha256sum`, BusyBox tools) and ephemeral `uvx` runners (`ruff`, `ty`, `pytest`) have been pruned.

---

### 1. Hard Script Dependencies (Scripts fail without these)

| Executable | Used By | Context | Suggested Action |
| --- | --- | --- | --- |
| **`age`** / **`rage`** | [`mirror_crypto`](file:///Users/josh/d/agent-memory/src/agent_memory/mirror_crypto.py#L30-L47) | Encrypts agent session mirror objects (`rage`/`age` and `rage-keygen`/`age-keygen`). | Packaged in [dl](file:///Users/josh/usr/dl) from https://github.com/laputa-systems/rage. |
| **`mpv`** | [`stream`](file:///Users/josh/usr/dotfiles/base/.local/bin/stream#L10-L19) | Launches media player to stream video (`command -v mpv` or `/Applications/mpv.app`). | Add `brew "mpv"` to [Brewfile](file:///Users/josh/usr/host/macos/Brewfile) or install MPV cask. |

---

### 2. Core Workflow Tools Missing from Host Provisioning

| Executable | Used By | Context | Suggested Action |
| --- | --- | --- | --- |
| **`tmux`** | [tmux.conf](file:///Users/josh/usr/dotfiles/base/.config/tmux/tmux.conf), [config.ish](file:///Users/josh/usr/dotfiles/base/.config/ish/config.ish#L53-L56), [config.ini](file:///Users/josh/usr/dotfiles/base/.config/xshi/config.ini#L41-L44), [`notify-sound`](file:///Users/josh/usr/dotfiles/darwin/.local/bin/notify-sound#L14), [setup-macos](file:///Users/josh/usr/host/macos/setup-macos#L10) | Extensively configured (`tmux.conf`, aliases `tl`/`tn`/`ta`/`tk`, pane queries, Touch ID PAM). | Added to [host/macos/Brewfile](file:///Users/josh/usr/host/macos/Brewfile) and [host/alpine/packages.txt](file:///Users/josh/usr/host/alpine/packages.txt). |
| **`uv`** | [lint](file:///Users/josh/usr/lint#L15), [sync](file:///Users/josh/usr/sync#L144-L168), [Makefile](file:///Users/josh/usr/Makefile#L14), [docs/development.md](file:///Users/josh/usr/docs/development.md) | Standard runner for Python tests, ruff, ty, and pytest across the repo. Installed on Alpine. | Added to [host/macos/Brewfile](file:///Users/josh/usr/host/macos/Brewfile). |
| **`dash`** | [sync](file:///Users/josh/usr/sync#L135), [docs/development.md](file:///Users/josh/usr/docs/development.md#L10) | Standard POSIX shell checker (`sh sync check (Python link tests)`, `dash -n doctor`, etc.). Pre-installed at `/bin/dash` on recent macOS. | Added to [host/macos/Brewfile](file:///Users/josh/usr/host/macos/Brewfile). |
| **`duf`** | [config.ish](file:///Users/josh/usr/dotfiles/base/.config/ish/config.ish#L30), [config.ini](file:///Users/josh/usr/dotfiles/base/.config/xshi/config.ini#L23) | Aliased to `du`. Missing from all installer recipes. | Add to [Brewfile](file:///Users/josh/usr/host/macos/Brewfile) (`brew "duf"`), add to [dl](file:///Users/josh/usr/dl), or remove the alias. |
| **`procs`** | [config.ish](file:///Users/josh/usr/dotfiles/base/.config/ish/config.ish#L32), [config.ini](file:///Users/josh/usr/dotfiles/base/.config/xshi/config.ini#L24) | Aliased to `pp`. Missing from all installer recipes. | Add to [Brewfile](file:///Users/josh/usr/host/macos/Brewfile) (`brew "procs"`), add to [dl](file:///Users/josh/usr/dl), or remove the alias. |
| **`imv`** | [imv/config](file:///Users/josh/usr/dotfiles/linux/.config/imv/config) | Configured in Linux dotfiles layer, but not installed in Alpine desktop package list. | Add `imv` to [host/alpine/packages-desktop.txt](file:///Users/josh/usr/host/alpine/packages-desktop.txt). |

---

### 3. Wiring Mismatches & Edge Dependencies

| Executable | Used By | Context | Suggested Action |
| --- | --- | --- | --- |
| **`fzy`** vs **`fz`** | [`stream`](file:///Users/josh/usr/dotfiles/base/.local/bin/stream#L78) | `stream` was checking `command -v fzy`, but `dl` installs `fz`. | Patched [`stream`](file:///Users/josh/usr/dotfiles/base/.local/bin/stream#L78) to use `fz`. |
| **`wol`** | [config.ini](file:///Users/josh/usr/dotfiles/base/.config/xshi/config.ini#L26) | Aliased to `$HOME/usr/bin/wol`. The implementation exists in-tree at [src/wol.py](file:///Users/josh/usr/src/wol.py), but is never symlinked into `~/.local/bin/`. | Add a symlink or launcher under `dotfiles/base/.local/bin/wol`. |
| **`paplay`** | [`notify-sound`](file:///Users/josh/usr/dotfiles/linux/.local/bin/notify-sound#L28-L30) | Plays notification chime on Linux desktop. | Add `pulseaudio-utils` (or PipeWire audio utility) to [host/alpine/packages-desktop.txt](file:///Users/josh/usr/host/alpine/packages-desktop.txt). |
| **`bwrap`** | [`sbx`](file:///Users/josh/usr/dotfiles/base/.local/bin/sbx#L215) | Bubblewrap backend for Linux process isolation. | Keep deferred (per [docs/sbx-spec.md](file:///Users/josh/usr/docs/sbx-spec.md#L3)), or add `bubblewrap` to Alpine packages if Linux sandboxing is desired. |
| **`watchman`** | [`macos-free-memory`](file:///Users/josh/usr/dotfiles/darwin/.local/bin/macos-free-memory#L194) | Free memory candidate script inspects Watchman state if installed. | Optional / opportunistic check; add `brew "watchman"` only if Watchman daemon monitoring is desired. |
| **`qemu-system-aarch64`** & **`qemu-img`** | [vm.sh](file:///Users/josh/usr/host/alpine/tests/vm.sh#L108-L125) | Test harness for booting and provisioning the Alpine installation VM. | Install `qemu` on the test host if running VM integration tests. |
