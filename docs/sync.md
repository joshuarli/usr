# Home-directory sync

`sh sync` selects `dotfiles/base` and the matching OS layer, then applies them to `$HOME` with `dotfiles/sym`. Each relative path belongs to one layer. `sh sync layers` rejects duplicate claims. See [`sym`](../dotfiles/sym) for link rules.

Run `sh sync plan` to preview links. Resolve each `CONFLICT` before syncing. `sh sync links` applies only the layer links, without `dl` or host setup, and `sh sync tools ish` runs `dl` for the named tools only. `sh sync` applies links before running `dl`; a failed download leaves the links in place and returns failure. `TARGET` changes the symlink destination, but tools still install under `$HOME/.local/bin`.

`sh sync doctor` inspects the installed environment without changing managed files or host settings. It reuses `sync plan` to report missing, conflicting, or obsolete layer links, checks ownership records and default `dl` launchers (`sh dl --list`), verifies shared agent entry points, and checks Homebrew bundle state on macOS or the installed Unbound configuration on Alpine. It may create temporary scratch files, which it removes. It performs no installation, package upgrade, sudo operation, or intentional network request; a nonzero exit means at least one problem was detected. Use `sh sync plan` to see exact link repairs before applying anything.

`sh sync uninstall` removes recorded layer links and installed tool paths. It leaves unrecorded pre-existing links and native launchers in place. Ownership records live under `${XDG_STATE_HOME:-$HOME/.local/state}/sync`. See [`dl`](../dl) for tool installation and update behavior.

`make` also runs host setup: macOS installs Homebrew packages, while Alpine Linux installs the sync prerequisites and configures Unbound and DNS. These steps can use `sudo`. Other Linux distributions skip Unbound setup. Touch ID and macOS DNS setup are manual. See [`setup-macos`](../host/macos/setup-macos) and [macOS preferences](macos-preferences.md).

On macOS, `sh dl ghostty` downloads the pinned official universal Ghostty release ZIP directly (no Homebrew), verifies the signed app with macOS Gatekeeper, and installs it at `/Applications/Ghostty.app` with a `~/.local/bin/ghostty` symlink. After installing, run `ghostty-fda-check` inside Ghostty to confirm Full Disk Access; it opens System Settings at the Full Disk Access pane when the grant is missing. Set `GHOSTTY_APPLICATIONS_DIR="$HOME/Applications"` if `/Applications` is not writable. It will not overwrite an existing unmanaged app or launcher; `sh sync uninstall` removes a dl-managed installation. Ghostty auto-updates are disabled by the linked config; change `GHOSTTY_VERSION` in `dl` to upgrade.

**Ghostty shader reload:** After `git pull`, run `sh sync links` to link any new shader file. Ghostty only rebuilds a shader on config reload when the configured shader path changes; editing GLSL at the same path alone may leave an existing terminal using cached code. Open a new Ghostty window or fully quit and relaunch for source-only changes. Run `python3 -I dotfiles/ghostty-shader-test.py --demo` in Ghostty to verify the animation.

`sh dl fx` is an optional pinned native install; no-argument `dl` does not install fx. The `~/.fx/AGENTS.md` and `~/.fx/settings.json` files are dotfiles-managed links; fx credentials, sessions, and all other mutable state stay local. fx auto-updates are disabled in the tracked profile. Change `FX_VERSION` and its checksums in `dl` to upgrade.

The `host/macos/` directory is not part of the layer sync. `agent-learn` and its Codex hook come from the base layer; its LaunchAgent template is installed only when you pass `--schedule` to `agent-learn enable` on macOS. See [agent learning](agent-learning.md).

Sync prunes a recorded link that points into a layer whose source is gone; `sh sync plan` lists these as `PRUNE`. A link copied from a layer symlink points elsewhere, so it stays, as do links `sh sync` did not create. Remove those yourself, or run `sh dotfiles/sym -d` on the layer before deleting the source. Test `sym` only with `-t <tmpdir>`; without it, `sym` targets `$HOME`.
