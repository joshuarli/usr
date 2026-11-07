# Dotfiles

This repository installs my home configuration, personal commands, and machine setup. Clone it to `~/usr`.

## Install

On macOS, preview setup with `./host/macos/setup-macos -n`. Run `./host/macos/setup-macos` to install Homebrew and its packages, configure Touch ID for `sudo`, and start Unbound. The script changes system settings and uses `sudo`. Unbound listens on loopback and forwards to Cloudflare over authenticated DNS-over-TLS. Its DNS step assigns `127.0.0.1` to every enabled network service, including Tailscale. System DNS then depends on Unbound, with no public fallback if it stops.

Tailscale SSH is the one part the GUI app cannot do, so it is a separate step: `./host/macos/setup-macos tailscale` runs Homebrew's `tailscaled`, the only macOS variant that serves Tailscale SSH, and enables `--ssh` on it. It refuses while `/Applications/Tailscale.app` exists; remove that app, empty the Trash, and reboot first, because the two variants cannot share the tunnel. `tailscaled` also leaves DNS alone on macOS, so tailnet names resolve by `100.x` address rather than by MagicDNS name while every service points at Unbound.

The service-disabling step is optional. Run `./host/macos/macos lean --audit`, review the report, then run `./host/macos/macos lean --dry-run`. Apply it with `./host/macos/macos lean` only after reviewing the planned changes. Lean disables IPv6 on non-VPN interfaces, captive-portal probes, mDNS advertisements, and unified logging. Captive Wi-Fi login pages need manual browser navigation, this Mac may stop appearing as an AirPlay target, and Console or `log show` lose unified logs. Lean also uses hibernation mode 0 on battery and removes the sleep image, so unsaved memory state is lost if the battery drains during sleep. `./host/macos/macos lean --revert` restores the tool's defaults, not the settings that existed before apply.

Use [`macos`](docs/macos-preferences.md) to snapshot, compare, and apply selected macOS user preferences. Raw snapshots include every user and current-host `defaults` domain, so keep them private and out of Git; check in only selected preferences.

On Alpine Linux, run `./host/setup-linux` for the initial setup. It installs Unbound and its OpenRC service, the sync prerequisites (`curl`, bash, jq, unzip, libgcc, OpenSSH client, uv), deploys the shared config, points `/etc/resolv.conf` at Unbound, and verifies localhost and system DNS queries. It leaves `/etc/resolv.conf` writable so Tailscale can apply MagicDNS and split DNS settings. DHCP or Tailscale may replace the localhost entries; Tailscale can route DNS through its own resolver instead of Unbound.

On Linux, skip the macOS setup. The agent hooks also need the `agent-memory` package; `sh sync` installs it into `~/.local/share/agent-memory/venv`, from `~/d/agent-memory` when checked out and otherwise from the pinned commit in `tools/sync/agent-memory.pin`. Run `sh sync plan` on either platform and resolve any reported conflicts. Then run `sh sync` to link the current OS layer into your home directory, download supported tools, and install kache if it is missing. On macOS, `sh sync` checks Homebrew packages but does not configure system DNS. To configure DNS explicitly, run `./host/macos/setup-macos dns`. Run `./host/macos/fix-dns` to restore automatic DNS for Wi-Fi and Tailscale. On Alpine Linux, `sh sync` runs `host/setup-linux` first to install or update Unbound, the sync prerequisites, and system DNS. Other Linux distributions skip the Unbound setup. On glibc Linux, run `setup-mold`. Musl builds expect mold at `/usr/local/libexec/mold`.

To provision a fresh Alpine edge machine instead, bootstrap it with the one-liner in [`host/alpine/README.md`](host/alpine/README.md), or run `doas sh host/alpine/install.sh` from this checkout and choose a headless server or a dwl + ghostty-custom desktop; both link dotfiles, install the default tool set except `agy`, and leave networking and DNS alone.

Run `sh sync doctor` to inspect installed links, tools, agent configuration, and relevant platform dependencies without applying repairs. See [sync details](docs/sync.md) for what `sh sync` changes and how the layers work, and [AGENTS.md](AGENTS.md) for the repository map and development checks.


## Linux CPU power policy

`power-policy` is a daemonless POSIX shell tool installed by the Linux dotfile layer. Run `power-policy status`, preview with `power-policy diff auto`, and apply with `doas "$HOME/.local/bin/power-policy" auto` or `doas "$HOME/.local/bin/power-policy" performance`. It supports Intel N100 (`intel_pstate`/`intel_cpufreq`), AMD Ryzen 2400GE (`acpi-cpufreq`), and modern AMD P-State/EPP. It replaces `threadripper-tune`; boot/event hooks are opt-in. See [Linux CPU power policy](docs/power-policy.md).
