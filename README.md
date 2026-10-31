# Dotfiles

This repository installs my home configuration, personal commands, and machine setup. Clone it to `~/usr`.

For native, dependency-free Python process confinement of coding agents, use [`sbx`](docs/sbx-spec.md) on macOS (Seatbelt) or Linux (Bubblewrap). It grants the current project read/write, accepts explicit extra directories, and keeps unrelated home data out of the sandbox. Linux requires `bwrap`; use the full specification and live tests before trusting it with sensitive information.

## Process picker

`pk <query>` is an interactive process killer built on [fz](https://github.com/laputa-systems/fz).
Type to fuzzy-filter your own processes, press Down to focus the list, and
press Space to mark or unmark individual processes. Enter sends SIGTERM to all
marked processes (or the focused process if none are marked). Esc cancels.
`pk -9 <query>` explicitly sends SIGKILL instead. The command never
automatically escalates, searches processes belonging to other users, or kills
all query matches without selection. Before signaling, it checks that each
selected PID still matches the original process record.

Requires a recent `fz` supporting `--multi`; `sh dl fz` installs the
managed binary where available, or build it from the fz repository. Run
`python3 -I dotfiles/pk-test.py` for disposable-process tests.

## Install

On macOS, preview setup with `./host/macos/setup-macos -n`. Run `./host/macos/setup-macos` to install Homebrew and its packages, configure Touch ID for `sudo`, and start Unbound. The script changes system settings and uses `sudo`. Unbound listens on loopback and forwards to Cloudflare over authenticated DNS-over-TLS. Its DNS step assigns `127.0.0.1` to every enabled network service, including Tailscale. System DNS then depends on Unbound, with no public fallback if it stops.

The service-disabling step is optional. Run `./host/macos/macos lean --audit`, review the report, then run `./host/macos/macos lean --dry-run`. Apply it with `./host/macos/macos lean` only after reviewing the planned changes. Lean disables IPv6 on non-VPN interfaces, captive-portal probes, mDNS advertisements, and unified logging. Captive Wi-Fi login pages need manual browser navigation, this Mac may stop appearing as an AirPlay target, and Console or `log show` lose unified logs. Lean also uses hibernation mode 0 on battery and removes the sleep image, so unsaved memory state is lost if the battery drains during sleep. `./host/macos/macos lean --revert` restores the tool's defaults, not the settings that existed before apply.

Use [`macos`](docs/macos-preferences.md) to snapshot, compare, and apply selected macOS user preferences. Raw snapshots include every user and current-host `defaults` domain, so keep them private and out of Git; check in only selected preferences.

On Alpine Linux, run `./host/setup-linux` for the initial setup. It installs Unbound and its OpenRC service, deploys the shared config, points `/etc/resolv.conf` at Unbound, and verifies localhost and system DNS queries. It leaves `/etc/resolv.conf` writable so Tailscale can apply MagicDNS and split DNS settings. DHCP or Tailscale may replace the localhost entries; Tailscale can route DNS through its own resolver instead of Unbound.

On Linux, skip the macOS setup. Run `sh sync plan` on either platform and resolve any reported conflicts. Then run `sh sync` to link the current OS layer into your home directory, download supported tools, and install kache if it is missing. On macOS, `sh sync` checks Homebrew packages but does not configure system DNS. To configure DNS explicitly, run `./host/macos/setup-macos dns`. Run `./host/macos/fix-dns` to restore automatic DNS for Wi-Fi and Tailscale. On Alpine Linux, `sh sync` runs `host/setup-linux` to install or update Unbound and verify system DNS. Other Linux distributions skip the Unbound setup. On glibc Linux, run `setup-mold`. Musl builds expect mold at `/usr/local/libexec/mold`.

To provision a fresh Alpine edge machine instead, bootstrap it with the one-liner in [`host/alpine/README.md`](host/alpine/README.md), or run `doas sh host/alpine/install.sh` from this checkout and choose a headless server or a dwl + ghostty-custom desktop; both link dotfiles and install ish, and leave networking and DNS alone.

Run `sh sync doctor` to inspect installed links, tools, agent configuration, and relevant platform dependencies without applying repairs. See [sync details](docs/sync.md) for what `make` changes and how the layers work.

