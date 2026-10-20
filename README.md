# Dotfiles

This repository installs my home configuration, personal commands, and machine setup. Clone it to `~/usr`.

## Install

On macOS, preview setup with `./macos/setup-macos -n`. Run `./macos/setup-macos` to install Homebrew and its packages, configure Touch ID for `sudo`, and start Unbound. The script changes system settings and uses `sudo`. Unbound listens on loopback and forwards to Cloudflare over authenticated DNS-over-TLS. System DNS has no public fallback when Unbound stops.

The service-disabling step is optional. Run `./macos/macos lean --audit`, review the report, then run `./macos/macos lean --dry-run`. Apply it with `./macos/macos lean` only after reviewing the planned changes.

Use [`macos`](docs/macos-preferences.md) to snapshot, compare, and apply selected macOS user preferences. Raw snapshots include every user and current-host `defaults` domain, so keep them private and out of Git; check in only selected preferences.

On Alpine Linux, run `./setup-linux` for the initial setup. It installs Unbound and its OpenRC service, deploys the shared config, points `/etc/resolv.conf` at Unbound, and verifies localhost and system DNS queries. It leaves `/etc/resolv.conf` writable so Tailscale can apply MagicDNS and split DNS settings. DHCP or Tailscale may replace the localhost entries; Tailscale can route DNS through its own resolver instead of Unbound.

On Linux, skip the macOS setup. Run `make plan` on either platform and resolve any reported conflicts. Then run `make` to link the current OS layer into your home directory, download supported tools, and install kache if it is missing. On macOS, `make` runs `macos/setup-macos brew packages dns` each time. It installs missing packages and applies the shared Unbound config, restarting the service only when needed. On Alpine Linux, `make` runs `setup-linux` to install or update Unbound and verify system DNS. Both DNS setup steps can use `sudo`. Other Linux distributions skip the Unbound setup. On glibc Linux, run `setup-mold`. Musl builds expect mold at `/usr/local/libexec/mold`.

See [sync details](docs/sync.md) for what `make` changes and how the layers work.

