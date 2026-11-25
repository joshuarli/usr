# Dotfiles

This repository installs my home configuration, personal commands, and machine setup. Clone it to `~/usr`.

## Harness switches

[`harnesses.json`](harnesses.json) is the single on/off configuration for every
harness and provider. Change one boolean, then run `make generate` to refresh
the checked-in agent instructions, routing summaries and visualization.
`make check-generated` checks that they agree. Command Code is off; the
previously disabled DeepSeek Harness also remains off.

The bridge and managed launch shims read these switches before new work,
including resume and steering. Disabled backends are omitted from route probes
and login checks. Default installs omit their tools unless an enabled provider
needs them. `sh sync plan` previews which owned harness
configuration and native-agent links the next sync will remove or restore;
credentials, transcripts and vendor binaries are retained. Start a fresh agent
session after generation so its context uses the new instructions.

Harnesses and subscription providers have separate switches: `opencode` controls
the native CLI; `opencode-go` controls that provider through Pi, which also
requires `pi`. An enabled Pi Go provider keeps OpenCode installed for credential
export even when native OpenCode sessions are disabled. Turning a harness back
on restores its existing model pins and
instructions. See [policy generation](tools/policy/README.md) for ownership and
verification.

## Install

On macOS, preview setup with `./host/macos/setup-macos -n`. Run `./host/macos/setup-macos` to install Homebrew and its packages, configure Touch ID for `sudo`, and start Unbound. The script changes system settings and uses `sudo`. Unbound listens on loopback and forwards to Cloudflare over authenticated DNS-over-TLS. Its DNS step assigns `127.0.0.1` to every enabled network service, including Tailscale. System DNS then depends on Unbound, with no public fallback if it stops.

Tailscale SSH is the one part the GUI app cannot do, so it is a separate step: `./host/macos/setup-macos tailscale`. If `/Applications/Tailscale.app` is present it removes it, then asks you to reboot to clear its system extension; run `./host/macos/setup-macos tailscale` again after reboot and it starts Homebrew's `tailscaled` and enables `--ssh`. `tailscaled` also leaves DNS alone on macOS, so tailnet names resolve by `100.x` address rather than by MagicDNS name while every service points at Unbound.

The service-disabling step is optional. Run `./host/macos/macos lean --audit`, review the report, then run `./host/macos/macos lean --dry-run`. Apply it with `./host/macos/macos lean` only after reviewing the planned changes. Lean disables IPv6 on non-VPN interfaces, captive-portal probes, mDNS advertisements, and unified logging. Captive Wi-Fi login pages need manual browser navigation, this Mac may stop appearing as an AirPlay target, and Console or `log show` lose unified logs. Lean also uses hibernation mode 0 on battery and removes the sleep image, so unsaved memory state is lost if the battery drains during sleep. `./host/macos/macos lean --revert` restores the tool's defaults, not the settings that existed before apply.

Use [`macos`](docs/macos-preferences.md) to snapshot, compare, and apply selected macOS user preferences. Raw snapshots include every user and current-host `defaults` domain, so keep them private and out of Git; check in only selected preferences.

On Alpine Linux, run `./host/setup-linux` for the initial setup. It installs Unbound, its OpenRC service, and the prerequisites declared in [setup-linux](host/setup-linux). It deploys the shared config, points `/etc/resolv.conf` at Unbound, and verifies localhost and system DNS queries. It leaves `/etc/resolv.conf` writable so Tailscale can apply MagicDNS and split DNS settings. DHCP or Tailscale may replace the localhost entries; Tailscale can route DNS through its own resolver instead of Unbound.

On Linux, skip the macOS setup. Run `sh sync plan` on either platform and resolve any reported conflicts. Then run `sh sync` to link the current OS layer into your home directory, download supported tools, and install kache if it is missing. On macOS, `sh sync` checks Homebrew packages but does not configure system DNS. To configure DNS explicitly, run `./host/macos/setup-macos dns`. Run `./host/macos/fix-dns` to restore automatic DNS for Wi-Fi and Tailscale. On Alpine Linux, `sh sync` runs `host/setup-linux` first to install or update Unbound, the sync prerequisites, and system DNS. Other Linux distributions skip the Unbound setup. On glibc Linux, run `setup-mold`. On Debian or Ubuntu, first install `python3`, `curl`, `xz-utils`, `libatomic1` (Node.js needs it), and rustup before `sh sync`. The linked `~/.cargo/config.toml` runs rustc through `~/.cargo/bin/kache` directly, because a shell launcher would drop Cargo's hyphenated `CARGO_BIN_EXE_*` variables; sync installs kache whenever rustup is present, so rerun `sh sync` after installing rustup, or set `CARGO_BUILD_RUSTC_WRAPPER=` to build without it. Host C/C++ go through `cargo-wrapper-cc` and `cargo-wrapper-cxx` in `~/.local/bin`, which use `kache` and `clang` when installed and otherwise fall back to plain `cc` and `c++`. Without musl's `/lib/ld-musl-<arch>.so.1`, sync installs CPython with the managed `uv` and leaves `ffmpeg` and `player` out of the defaults, because their Linux builds link musl. Musl builds expect mold at `/usr/local/libexec/mold`.

To provision a fresh Alpine edge machine instead, bootstrap it with the one-liner in [`host/alpine/README.md`](host/alpine/README.md), or run `doas sh host/alpine/install.sh` from this checkout and choose a headless server or a dwl + ghostty-custom desktop; both link dotfiles, install the default tool set except `agy`, and leave networking and DNS alone.

Run `sh sync doctor` to inspect installed links, tools, agent configuration, and relevant platform dependencies without applying repairs. Run `sh sync hosts` to see every usr machine in the tailnet policy at once, `sh sync hosts pull` to fast-forward their checkouts, and `sh sync hosts apply` to pull and sync them all. See [sync details](docs/sync.md) for what `sh sync` changes and how the layers work, and [AGENTS.md](AGENTS.md) for the repository map and development checks.
