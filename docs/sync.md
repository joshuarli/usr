# Home-directory sync

`dotfiles/base` applies on every OS. `dotfiles/darwin` and `dotfiles/linux` add the matching OS layer. `make` selects layers from `uname` and applies them to `$HOME` with `dotfiles/sym`.

Each relative path can belong to one layer. The `layers` target rejects duplicate claims before sync. `sym` creates relative symlinks for files. A directory with a `.sym-dir` marker is linked as one unit. Git ignore rules determine which files `sym` sees.

Run `make plan` to preview the links. It does not run `dl`. A `CONFLICT` means the target contains a path that `sym` cannot safely replace. Resolve it before syncing. `make` runs `dl` and then applies each layer. If a download fails, sync still runs and `make` returns a failure. The `TARGET` variable changes the symlink destination; `dl` still installs into `$HOME/.local/bin`.

`dl` installs supported tools from their latest release assets into `$HOME/.local/bin`. It records each installed asset's ETag under `${XDG_STATE_HOME:-$HOME/.local/state}/dl` and downloads again when the ETag changes. If a release cannot be checked, `dl` keeps an installed tool and warns. It also installs the `mactop` app and LaunchAgent. On Linux, `fd` and `rg` use static musl archives, and `mold` is installed only on x86_64. Other release downloads use TLS without an additional signature or checksum check.

The repository's `bin` symlink points to `~/.local/bin`, where tracked scripts and downloaded tools live together. Only the scripts under `dotfiles/*/.local/bin` are tracked.

Deleting a source file leaves its home-directory symlink dangling. Remove that link too, or run `sh dotfiles/sym -d` on the layer before deleting the source. To experiment with `sym`, pass a scratch target with `-t`; without it, `sym` targets `$HOME`.

The `macos/` directory is not part of the layer sync. Run its setup scripts by hand. `macos/setup-macos` provisions Homebrew, packages, Touch ID for `sudo`, and local DNS. `macos/macos-lean.py` disables selected services and is never part of the default setup.

