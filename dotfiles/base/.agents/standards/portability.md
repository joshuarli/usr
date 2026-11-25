+++
name = "portability"
summary = "Shared scripts and code run unchanged on macOS and Linux (glibc and Alpine's BusyBox and musl): POSIX tools and options plus a short verified list, no BSD-only or GNU-only commands or flags, and no single-platform paths or APIs outside platform-specific locations."

[[trigger]]
paths = ["*.sh", "*.bash", "Makefile", "GNUmakefile", "*.mk", "!darwin/", "!macos/", "!linux/", "!alpine/", "!*_darwin.*", "!*_macos.*", "!*_linux.*", "!*-macos", "!*-linux"]

[[trigger]]
paths = ["*", "!*.md", "!*.txt", "!darwin/", "!macos/", "!linux/", "!alpine/", "!*_darwin.*", "!*_macos.*", "!*_linux.*", "!*-macos", "!*-linux"]
shebang = ['^#!\s*\S*/(env\s+(-S\s+)?)?(sh|bash|dash|ash|ksh|zsh)\b']

[[trigger]]
paths = ["*.py", "*.rs", "*.zig", "*.go", "*.ts", "*.mts", "*.js", "*.mjs", "*.swift", "!darwin/", "!macos/", "!linux/", "!alpine/", "!*_darwin.*", "!*_macos.*", "!*_linux.*", "!*-macos", "!*-linux"]
content = ['/proc/', '/sys/(class|fs|devices|kernel)', '/dev/shm', '\b(sched_getaffinity|posix_fadvise|epoll|kqueue|inotify|FSEvents)\b', '\b(sysctl|launchctl|systemctl|rc-service|apk\s+add|brew\s+install|pbcopy|pbpaste|xdg-open)\b', '/opt/homebrew|/usr/local/(bin|opt|Cellar)', '\b(shasum|md5sum|nproc|flock|gsed|gstat)\b', '"(stat|sed|date|readlink)",\s*"-[a-zA-Z]']

[examples]
match = [
  "tools/sync/bootstrap.sh",
  "pkg/Makefile",
  { path = "dotfiles/base/.local/bin/encode", text = "#!/bin/sh\nset -eu\n" },
  { path = "tools/cpu.py", text = "cpus = len(os.sched_getaffinity(0))\n" },
  { path = "src/hash.rs", text = "Command::new(\"shasum\").arg(\"-a\").arg(\"256\")\n" },
]
skip = [
  "host/macos/setup.sh",
  "README.md",
  { path = "dotfiles/linux/.local/bin/setup-mold", text = "#!/bin/sh\n" },
  { path = "dotfiles/darwin/.local/bin/clip", text = "#!/bin/sh\npbcopy\n" },
  { path = "host/alpine/provision.py", text = "open('/proc/cmdline')\n" },
  { path = "src/watch_linux.rs", text = "inotify_init1(0)\n" },
  { path = "bin/report", text = "#!/usr/bin/env python3\n" },
]
+++

# Portability

Shared code runs on every host in the fleet: macOS (BSD userland), glibc Linux (GNU coreutils), and Alpine (BusyBox and musl). Write to their lowest common denominator. A command or flag that exists on only one of them is a bug in shared code, even when it works on the machine you tested on; some differences do not fail but silently do the wrong thing, such as `sed 's/\s/_/'`, which matches nothing on macOS.

Platform-specific code is allowed where its location says so: a directory named `darwin`, `macos`, `linux`, or `alpine`; a file named `*_linux.*`, `*_darwin.*`, `*_macos.*`, `*-linux`, or `*-macos`; and Dockerfiles, container-only scripts, and CI steps pinned to one runner OS. Rust, Zig, Go, and Swift platform code behind `cfg`, `builtin.os`, or build tags follows the `os-boundaries` standard, which owns how supported targets and per-OS mechanisms are declared; the supported set here is macOS and Linux, both glibc and musl.

## Code

### Shell commands

- Use POSIX utilities with POSIX options (the [POSIX.1-2024 utilities](https://pubs.opengroup.org/onlinepubs/9799919799/idx/utilities.html)), plus only these widely shared extensions: `sha256sum FILE` and `sha256sum -c FILE` (discard the output instead of `--status` or `-s`); `mktemp` and `mktemp -d` with an explicit template such as `"$dir/name.XXXXXX"`; `readlink -f` and `realpath`; `timeout SECONDS command`; `base64 -d`; `head -c`; `find -maxdepth`; `grep -E`, `-F`, `-o`, and `-q`; `sed -E`; `tar -C DIR -xzf`; `install -m`; `cp -a`; `ln -sfn`; `xargs -r`; `getconf _NPROCESSORS_ONLN`.
- Anything else must be verified on macOS, GNU, and BusyBox before use, or moved into a standard-library Python script. Do not detect the platform and switch between two single-platform spellings when one portable spelling or a Python script exists.
- These are not allowed in shared code, with the portable replacement:

| Instead of | Use |
| --- | --- |
| `shasum`, `md5`, `md5sum`, `openssl dgst` for checksums | `sha256sum` |
| `stat -c` or `stat -f` | `wc -c < FILE` for size (strip the padding macOS adds), `find FILE -newer REF` for time order, Python for owners, modes, and times |
| `sed -i` (GNU and BSD spell it differently) | write to a temp file in the same directory, then `mv` |
| GNU regex escapes `\s`, `\w`, `\+`, `\?`, `\|` in `sed` or `grep` | `[[:space:]]`, `[[:alnum:]_]`, and `-E` with `+`, `?`, `\|` written as `|` |
| `grep -P` | `grep -E`, or Python |
| `date -d`, `date -j`, `date -v`, `date +%N` | `date -u +%s` and `date -u +%Y-%m-%dT%H:%M:%SZ`; Python for arithmetic and parsing |
| `nproc`, `sysctl -n hw.ncpu`, `/proc/cpuinfo` | `getconf _NPROCESSORS_ONLN`, or `os.cpu_count()` |
| `flock` | a `mkdir` lock directory, or Python `fcntl.flock` |
| `getopt` | the `getopts` builtin |
| `find -printf`, `-regextype`, `sort -V`, `du -b`, `readlink -e` or `-m`, `cp --reflink`, `cp -T`, `mv -T`, `ln -r`, `install -D`, `tac`, `tail -r` | POSIX equivalents (`find -exec`, `wc -c`, `mkdir -p` then `install`, `awk` to reverse), or Python |
| `echo -e`, `echo -n`, `which` | `printf`, `command -v` |
| GNU-only long options on core tools (`--null-data`, `--parents`, `--no-dereference`) | the short POSIX option, or Python |

- Write `awk` for POSIX awk (macOS ships the one-true-awk): no `gawk` functions such as `gensub`, `strftime`, or `asort`.
- Strip the leading spaces macOS adds to `wc` output before comparing or doing arithmetic on it.

### Paths and environment

- Never assume `/proc`, `/sys`, `/dev/shm`, or `/run` (Linux), or `/private`, `/Volumes`, or `~/Library` (macOS), in shared code.
- Never hardcode `/home`, `/Users`, `/opt/homebrew`, or `/usr/local`. Use `$HOME`, `command -v`, and the XDG variables with their documented defaults.
- Use `$TMPDIR` (or the repository's scratch directory), not a literal `/tmp`; on macOS `/tmp` is a symlink to `/private/tmp`, which breaks path comparisons.
- Shebangs are `#!/bin/sh` or `#!/usr/bin/env NAME`. Alpine has no `/bin/bash` by default, and macOS's `/bin/bash` is 3.2.
- Filenames must not differ only by case, because macOS volumes are case-insensitive by default. Do not rely on a filename's Unicode normalization form.
- Do not call a platform's service or package manager (`systemctl`, `rc-service`, `launchctl`, `apk`, `brew`) or clipboard and opener tools (`pbcopy`, `xdg-open`) from shared code; put that code in a platform-specific location.

### Language APIs

- Python: use `os.cpu_count()` (or `os.process_cpu_count()` on 3.13+), not `os.sched_getaffinity`; `selectors.DefaultSelector`, not `select.epoll` or `select.kqueue`; skip `os.posix_fadvise` and other APIs the `os` module documents as Linux-only or macOS-only unless a platform branch implements both.
- Subprocess calls follow the shell rules above: `["shasum", ...]` in Python or `Command::new("stat")` in Rust is as unportable as in a script. Prefer the language's standard library (`hashlib`, `os.stat`, `std::fs::metadata`) over shelling out.
- Compiled code that needs a per-OS mechanism, such as `inotify` versus FSEvents or `epoll` versus `kqueue`, implements both behind one interface, as `os-boundaries` requires.

### Verify

- Run changed shell scripts under `dash` and, where available, `busybox ash`, in addition to the default `/bin/sh`. Exercise the script on both macOS and Linux; use the repository's container or VM journey (for example `linux-capsule`) when you are on only one of them.
- When a command or flag is not on the allowed list, show that it works on macOS, GNU, and BusyBox, or replace it.

## Adoption

Apply these only when bringing a whole repository up to this standard with `/standardize`, not at the completion gate.

- Search shared code for each command and flag in the table and replace it. Remove `uname`-based branches that only choose between two single-platform spellings of the same operation.
- Move genuinely single-platform scripts into a platform-specific location instead of guarding them inline.
- Add a check that runs the repository's shell tests under `dash` and `busybox ash`, and a Linux run on macOS-developed repositories. Prefer a command-audit lint that rejects the table's commands mechanically; this prose covers what such a lint cannot.

**Report:** commands and flags replaced, scripts moved to platform locations, and hosts or shells each script was verified on.
