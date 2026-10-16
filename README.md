# Dotfiles

This repository installs my home configuration, personal commands, and machine setup. Clone it to `~/usr`.

## Install

On macOS, preview the system setup with `./macos/setup-macos -n`. Run `./macos/setup-macos` to install Homebrew and its package list, configure Touch ID for `sudo`, and start the local DNS resolver. This step changes system settings and uses `sudo`. The DNS list includes `1.1.1.1` as a fallback, so DNS queries may go to Cloudflare without encryption if `unbound` stops.

The service-disabling step is optional. Run `./macos/setup-macos lean --audit`, review the report, then run `./macos/setup-macos lean --dry-run`. Apply it with `./macos/setup-macos lean` only after reviewing the planned changes.

On Linux, skip the macOS setup. On either platform, run `make plan` and resolve any reported conflicts. Then run `make` to download the supported tools, link the current OS layer into your home directory, and install kache if it is missing. On glibc Linux, also run `setup-mold`; musl builds expect mold at `/usr/local/libexec/mold`.

See [sync details](docs/sync.md) for what `make` changes and how the layers work.

