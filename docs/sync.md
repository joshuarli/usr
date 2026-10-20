# Home-directory sync

`dotfiles/base` applies on every OS. `dotfiles/darwin` and `dotfiles/linux` add the matching OS layer. `make` selects layers from `uname` and applies them to `$HOME` with `dotfiles/sym`.

Each relative path can belong to one layer. The `layers` target rejects duplicate claims before sync. `sym` creates relative symlinks for files. A directory with a `.sym-dir` marker is linked as one unit. Git ignore rules determine which files `sym` sees.

Run `make plan` to preview the links. It does not run `dl`. A `CONFLICT` means the target contains a path that `sym` cannot safely replace. Resolve it before syncing. `make` applies each layer before running `dl`, so installers see managed configuration in place. If a download fails, the links remain synced and `make` returns a failure. The `TARGET` variable changes the symlink destination; `dl` still installs into `$HOME/.local/bin`.

Run `make uninstall` to remove the layer links and paths recorded by `make` while installing tools. The ownership list lives at `${XDG_STATE_HOME:-$HOME/.local/state}/make/dl-owned`. `make` records layer links and parent directories only when it creates them, along with tool paths it installs or confirms as current from install records. Before uninstalling, `dl` also adopts existing downloads with ETag records. Pre-existing or older unrecorded layer links and older Claude, Muse, or Antigravity launchers without ownership records are left in place; untracked native launchers are reported. If `make` installed kache, the target runs kache's uninstaller with `--purge` to remove its cache and setup.

`dl` installs supported tools into `$HOME/.local/bin`, except package roots that need to keep their own dependencies together. For release-backed downloads, it records each asset's ETag under `${XDG_STATE_HOME:-$HOME/.local/state}/dl` and downloads again when the ETag changes. If a release cannot be checked, `dl` keeps an installed tool and warns. Claude Code, Muse Code, and Antigravity CLI use their official installers; their native launchers handle updates. Grok uses its native `$HOME/.grok` layout, Codex stores standalone packages under `${CODEX_HOME:-$HOME/.codex}/packages/standalone`, and OpenCode 2 uses `$HOME/.opencode/bin`; these are the layouts their update commands expect. OpenCode 2 is exposed as `opencode2` so it can coexist with OpenCode 1. `dl` migrates its previous direct-binary Grok, Muse, Claude, and OpenCode 2 installs, and the previous Codex bundle layout. It installs `@deepseek-ai/dsh` from npm's `next` tag and `@deepseek-harness-tui/dsh-tui` under `${XDG_DATA_HOME:-$HOME/.local/share}/dsh` when their recorded npm versions change. DSH's `next` release includes the DeepSeek Search and Fetch API providers selected by the tracked TUI patch. The tracked launcher supplies `DEEPSEEK_API_KEY` from `vault`; on hosts without `vault`, it uses an exported `DEEPSEEK_API_KEY` and fails with an error if neither source is available. Search and Fetch are billed per successful request ([DeepSeek Search & Fetch docs](https://api-docs.deepseek.com/guides/search/)). The TUI package currently carries a disabled `tool-ralph` row that DSH no longer ships; `dl` removes that exact row and fails if its shape changes. Node.js `^22.19` or `>=24`, npm, Python 3, and pnpm 10 or newer must already be available. The tracked `dsh` launcher starts the `dsh-tui` command and its `dsh-tui` profile; `dsh web` and other explicit profile invocations use the core CLI. Run `dl grok muse dsh codex claude opencode2 antigravity` to install only those tools. Codex uses `jaq` to read release metadata, and `dl` installs `jaq` when a missing or legacy Codex install needs it.

Use each tool's normal updater after installation:

| Tool | Update command or behavior |
| --- | --- |
| Codex | `codex update` |
| Claude Code | `claude update` |
| Grok | `grok update` |
| Muse Code | The official launcher updates itself. |
| OpenCode 2 | `opencode2 upgrade` |
| Antigravity CLI | `agy update`; it also checks for updates in the background. |
| DeepSeek Harness | `dsh update` runs `dl dsh` to update both npm packages. |

`dl` also installs the `mactop` app and LaunchAgent. On Linux, `fd` and `rg` use static musl archives, and `mold` is installed only on x86_64. Codex downloads are checked against vendor SHA-256 values. Grok, OpenCode 2, and the other direct downloads rely on TLS; Claude Code, Muse Code, and Antigravity CLI use their vendor installers.

The repository's `bin` symlink points to `~/.local/bin`, where tracked scripts and downloaded tools live together. Only the scripts under `dotfiles/*/.local/bin` are tracked.

Deleting a source file leaves its home-directory symlink dangling. Remove that link too, or run `sh dotfiles/sym -d` on the layer before deleting the source. To experiment with `sym`, pass a scratch target with `-t`; without it, `sym` targets `$HOME`.

The `macos/` directory is not part of the layer sync. Every macOS run of `make` invokes `macos/setup-macos brew packages dns`, which installs Homebrew and missing packages from `macos/Brewfile`, then applies the shared Unbound config and ensures local DNS answers. On Alpine Linux, `make` runs `setup-linux` to install or update Unbound, configure `/etc/resolv.conf`, and verify local and system DNS. These setup steps can use `sudo`. Other Linux distributions skip the Unbound setup. `make` sets up kache if kache is missing. Run `macos/setup-macos touchid` by hand to configure Touch ID for `sudo`. Run `macos/macos lean` to audit or converge selected system preferences. Lean is never part of the default setup.

