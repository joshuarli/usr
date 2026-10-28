# Dotfiles

This repository installs my home configuration, personal commands, and machine setup. Clone it to `~/usr`.

For native, dependency-free Python process confinement of coding agents, use [`sbx`](docs/sbx-spec.md) on macOS (Seatbelt) or Linux (Bubblewrap). It grants the current project read/write, accepts explicit extra directories, and keeps unrelated home data out of the sandbox. Linux requires `bwrap`; use the full specification and live tests before trusting it with sensitive information.

## Install

On macOS, preview setup with `./macos/setup-macos -n`. Run `./macos/setup-macos` to install Homebrew and its packages, configure Touch ID for `sudo`, and start Unbound. The script changes system settings and uses `sudo`. Unbound listens on loopback and forwards to Cloudflare over authenticated DNS-over-TLS. Its DNS step assigns `127.0.0.1` to every enabled network service, including Tailscale. System DNS then depends on Unbound, with no public fallback if it stops.

The service-disabling step is optional. Run `./macos/macos lean --audit`, review the report, then run `./macos/macos lean --dry-run`. Apply it with `./macos/macos lean` only after reviewing the planned changes. Lean disables IPv6 on non-VPN interfaces, captive-portal probes, mDNS advertisements, and unified logging. Captive Wi-Fi login pages need manual browser navigation, this Mac may stop appearing as an AirPlay target, and Console or `log show` lose unified logs. Lean also uses hibernation mode 0 on battery and removes the sleep image, so unsaved memory state is lost if the battery drains during sleep. `./macos/macos lean --revert` restores the tool's defaults, not the settings that existed before apply.

Use [`macos`](docs/macos-preferences.md) to snapshot, compare, and apply selected macOS user preferences. Raw snapshots include every user and current-host `defaults` domain, so keep them private and out of Git; check in only selected preferences.

On Alpine Linux, run `./setup-linux` for the initial setup. It installs Unbound and its OpenRC service, deploys the shared config, points `/etc/resolv.conf` at Unbound, and verifies localhost and system DNS queries. It leaves `/etc/resolv.conf` writable so Tailscale can apply MagicDNS and split DNS settings. DHCP or Tailscale may replace the localhost entries; Tailscale can route DNS through its own resolver instead of Unbound.

On Linux, skip the macOS setup. Run `make plan` on either platform and resolve any reported conflicts. Then run `make` to link the current OS layer into your home directory, download supported tools, and install kache if it is missing. On macOS, `make` checks Homebrew packages but does not configure system DNS. To configure DNS explicitly, run `./macos/setup-macos dns`. Run `./macos/fix-dns` to restore automatic DNS for Wi-Fi and Tailscale. On Alpine Linux, `make` runs `setup-linux` to install or update Unbound and verify system DNS. Other Linux distributions skip the Unbound setup. On glibc Linux, run `setup-mold`. Musl builds expect mold at `/usr/local/libexec/mold`.

To provision an Alpine edge desktop (dwl + foot) instead, run `doas sh alpine/install.sh` from this checkout as documented in [`alpine/README.md`](alpine/README.md); it links dotfiles and installs ish only, and leaves networking and DNS alone.

See [sync details](docs/sync.md) for what `make` changes and how the layers work.

