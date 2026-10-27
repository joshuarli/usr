# Home-directory sync

`make` selects `dotfiles/base` and the matching OS layer, then applies them to `$HOME` with `dotfiles/sym`. Each relative path belongs to one layer. `make layers` rejects duplicate claims. See [`sym`](../dotfiles/sym) for link rules.

Run `make plan` to preview links. Resolve each `CONFLICT` before syncing. `make links` applies only the layer links, without `dl` or host setup, and `make tools TOOLS="ish"` runs `dl` for the named tools only. `make` applies links before running `dl`; a failed download leaves the links in place and returns failure. `TARGET` changes the symlink destination, but tools still install under `$HOME/.local/bin`.

`make uninstall` removes recorded layer links and installed tool paths. It leaves unrecorded pre-existing links and native launchers in place. Ownership records live under `${XDG_STATE_HOME:-$HOME/.local/state}/make`. See [`dl`](../dl) for tool installation and update behavior.

`make` also runs host setup: macOS installs Homebrew packages, while Alpine Linux configures Unbound and DNS. These steps can use `sudo`. Other Linux distributions skip Unbound setup. Touch ID and macOS DNS setup are manual. See [`setup-macos`](../macos/setup-macos) and [macOS preferences](macos-preferences.md).

On macOS, `sh dl ghostty` downloads the pinned official universal Ghostty release ZIP directly (no Homebrew), verifies the signed app with macOS Gatekeeper, and installs it at `/Applications/Ghostty.app` with a `~/.local/bin/ghostty` symlink. Set `GHOSTTY_APPLICATIONS_DIR="$HOME/Applications"` if `/Applications` is not writable. It will not overwrite an existing unmanaged app or launcher; `make uninstall` removes a dl-managed installation. Ghostty auto-updates are disabled by the linked config; change `GHOSTTY_VERSION` in `dl` to upgrade.

The `macos/` directory is not part of the layer sync. `agent-learn` and its Codex hook come from the base layer; its LaunchAgent template is installed only when you pass `--schedule` to `agent-learn enable` on macOS. See [agent learning](agent-learning.md).

Sync prunes a recorded link that points into a layer whose source is gone; `make plan` lists these as `PRUNE`. A link copied from a layer symlink points elsewhere, so it stays, as do links `make` did not create. Remove those yourself, or run `sh dotfiles/sym -d` on the layer before deleting the source. Test `sym` only with `-t <tmpdir>`; without it, `sym` targets `$HOME`.
