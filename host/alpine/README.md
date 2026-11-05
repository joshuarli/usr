# home

Post-install provisioner for a stock Alpine Linux edge install with
`linux-stable`. It installs a headless server base and, layered on top, a
minimal dwl + ghostty-custom desktop with LLVM/clang 23 or newer. It is not an
installer, image, or distribution.
It lives at `host/alpine/` in the [usr](https://github.com/joshuarli/usr) checkout; clone that one repository to get it.
The target is a Dell XPS 13 9343 (x86_64); aarch64 is supported for VM testing.

## 1. Install Alpine

Alpine publishes no edge ISO. Boot the official Alpine 3.24 `standard` ISO and
install edge with the `linux-stable` kernel directly:

```sh
edge=https://dl-cdn.alpinelinux.org/alpine/edge
APKREPOSOPTS="$edge/main $edge/community" DISKOPTS="-m sys -k stable" setup-alpine
```

Choose:

- a disk for the `sys` install (diskless and data modes are rejected),
- networking, which this project never touches,
- an admin user with a password (`setup-user -a`), which configures password-required doas for `wheel`. Provisioning grants passwordless doas only to the configured user.
- no getty on `tty0` in `/etc/inittab` for a desktop install (installs booted
  with a VT `console=`, such as the virt ISO, add one, and it splits tty1
  keystrokes with the login).

Reboot into the installed system and log in as that user.

Installing edge this way means `setup.sh` does not convert the system or
require a reboot before provisioning. A stable install is converted first and
stops for a reboot.

If Alpine is already installed from a stable release, `setup.sh` converts it
to edge, then stops so the new kernel can boot before provisioning. Reboot and
run the same setup command again. When running `install.sh` by hand, make the
same change first: replace both repository lines in `/etc/apk/repositories`
with `edge/main` and `edge/community`, run `doas apk update` and
`doas apk upgrade --available`, and use `linux-stable` instead of `linux-lts`
(`doas apk add linux-stable && doas apk del linux-lts`). Reboot with
`doas reboot` before running `install.sh`. The switch to edge is one-way, and
packages follow the rolling branch.

## 2. Provision

```sh
wget -O - https://17166969.xyz/setup.sh | sh
```

`setup.sh` detects Alpine and refuses anywhere else. On a stable release it
switches the repositories to edge, upgrades the system, and replaces
`linux-lts` with `linux-stable` where needed, then stops and asks you to reboot
and rerun the command. Repeat any `INSTALL_MODE`, `USER_NAME`, or `TS_AUTHKEY`
assignments on that second run. Once booted into edge, it installs `git` if
missing, clones this repository over HTTPS to `~/usr` (or updates and reuses
that checkout), and runs `install.sh` as root through `doas` or `sudo`.

`install.sh` first asks for the install type:

- `server` installs the headless base: `packages.txt` (and
  `packages-x86_64.txt` on x86_64) with the clang toolchain, Docker, Tailscale,
  the dotfile links, and the minimal server tool profile in
  `tools-server.txt`. It installs no Wayland, graphics, or seatd packages.
- `desktop` runs the server install first, then layers `packages-desktop.txt`,
  udev, dwl, ghostty-custom, seatd, and the tty1 session on top of it. It also
  installs the full default `dl` tool set.

The server profile installs `fd`, `rg`, `jaq`, `fastermod`, `tm`, `ish`,
`stuff`, `e`, `fz`, `fdu`, `fs`, `srv`, `git`, `python3`, `gh`, and `zzz`. The heavy
agent, media, sync, and build extras (`codex`, `claude`, `opencode2`, `pi`,
`agent-browser`, `cf`, `ffmpeg`, `nodejs`, `pnpm`, `syncthing`, `player`, `mold`)
are opt-in on a server with `sh dl TOOL...`. The full set is installed by default
in desktop mode. `dl`, `sync`, and `doctor` follow the profile recorded in
`/etc/home/install-mode`.

Answer the prompt, or skip it with `INSTALL_MODE=server` or
`INSTALL_MODE=desktop`, for example:

```sh
wget -O - https://17166969.xyz/setup.sh | INSTALL_MODE=server sh
```

For a fully unattended server install, pass a Tailscale auth key and a GitHub
token with the `admin:public_key` scope:

```sh
wget -O - https://17166969.xyz/setup.sh | \
  INSTALL_MODE=server \
  TS_AUTHKEY=tskey-auth-... \
  GH_TOKEN=github_pat_... \
  sh
```

Without the bootstrap, do it by hand instead. If the system needed edge
conversion, reboot before running these commands:

```sh
doas apk add git && git clone https://github.com/joshuarli/usr
doas env INSTALL_MODE=server sh usr/host/alpine/install.sh
doas env INSTALL_MODE=desktop sh usr/host/alpine/install.sh
```

Provisioning defaults to user `josh` (`USER_NAME`); override with
`wget -O - https://17166969.xyz/setup.sh | USER_NAME=other sh`
for the bootstrap, or
`doas env USER_NAME=other sh usr/host/alpine/install.sh` by hand, if needed.

`install.sh` checks the system before changing anything and stops with an
explanation if a check fails. The server install then:

- installs the packages in `packages.txt` (and `packages-x86_64.txt` on x86_64),
  including `make`, `rustup`, `dash`, and `shellcheck`,
- initializes rustup for the user from the `rustup` package, before any tool
  install, so `sh sync` can install kache,
- makes `clang` and `clang++` link with lld, compiler-rt and LLVM libunwind by
  default through `/etc/clang<major>/clang.cfg` and `clang++.cfg`, so no gcc or
  binutils is needed (there is no `cc`; use `CC=clang`),
- links the enclosing checkout's dotfiles and installs the server tool profile
  as the user. It does not run the rest of `dl` or `host/setup-linux`; install
  other tools later with `sh dl TOOL`, and makes interactive logins start ish.

The server base grants the configured user passwordless root access through
`doas` and installs Docker Engine and its CLI. It enables and starts the
`docker` OpenRC service and adds the user to the `docker` group. Both the doas
rule and Docker group grant full root access to the host. Log out and back in
to use Docker without `doas` or `sudo`.

Provisioning creates an unencrypted Ed25519 GitHub key at `~/.ssh/github` when
that path is unused. It prints the public key for you to add to GitHub and never
prints or uploads the private key. Existing matching key pairs are preserved.
The `setup.sh` bootstrap logs in with `gh` when needed and uploads the public
key as an authentication key. Set `GH_TOKEN` to a token with the
`admin:public_key` scope to skip the device login. GitHub CLI stores its token
in `~/.config/gh/hosts.yml` with mode `0600`; without a credential store, the
token is plain text. A setup run without a terminal prints the login command
instead.

The server base also installs Tailscale. It loads `tun` through Alpine's
`modules` OpenRC service at boot, enables and starts the `tailscale` service,
and enables Tailscale SSH on a logged-in node. For an unattended install,
create a reusable auth key in the Tailscale admin console and pass it during
provisioning:

```sh
wget -O - https://17166969.xyz/setup.sh | TS_AUTHKEY=tskey-auth-... sh
```

Without `TS_AUTHKEY`, an install with a terminal requests device authorization:
it prints the device authorization URL to open and waits up to two minutes for
you to finish.
A run with output redirected leaves Tailscale logged out and prints
`doas tailscale up --ssh` instead. The node name comes from the machine
hostname. Tailscale SSH also needs an `ssh` rule for the node in the tailnet
policy, which the provisioner does not change. Once logged in, tailscaled
manages `/etc/resolv.conf` through the `resolvconf` dependency, so MagicDNS
names resolve on the machine.

The desktop layer runs its own preflight checks before the first change, then:

- installs the packages in `packages-desktop.txt` (including the Vulkan, font,
  and ALSA runtime that Player needs) and removes `foot` if an older install
  left it behind,
- switches the device manager to udev with `setup-devd udev`,
- builds the pinned dwl 0.9 with clang and lld using `config/dwl.h`, then removes
  the build-only headers,
- downloads the newest `release-*` ghostty-custom Wayland binary for the
  machine architecture with `build/ghostty.sh`, verifies its SHA256SUMS and
  installs it to `/usr/local/bin/ghostty-custom` with its terminfo,
- downloads the newest `helium-*` prerelease for x86_64 with
  `build/helium.sh`, verifies its SHA-256 and acceptance sidecar, and installs
  it under `/usr/local/lib/helium` with `/usr/local/bin/helium`; the same step
  installs the Intel i965 VA-API driver for hardware H.264 and VP8 decode on
  Broadwell-class graphics, while VP9 and HEVC stay on software,
- installs `home-session` and the `home-runtime` service; the profile hook from
  the server base starts the desktop on tty1,
- adds the user to the `seat` group and starts `seatd` and `home-runtime`.

Log out, then log in on tty1. dwl starts with a ghostty-custom terminal running
ish. Interactive logins for the provisioned user also hand off to ish after
profile startup. The account shell stays `/bin/ash`: ish is purely interactive,
so it cannot handle OpenSSH's `-c` remote commands or read the profile that
starts the desktop.

| Keys | Action |
| --- | --- |
| Super+Return, Ctrl+Return | ghostty-custom |
| Shift+Return | bemenu-run |
| Super+p | screenshot a region to the clipboard |
| Super+k | close window |
| Super+m | fullscreen |
| Super+f | toggle floating |
| Super+e | toggle previous layout |
| Super+j | focus next window |
| Super+h, Super+l | shrink, grow the master area |
| Super+i, Super+d | add, remove a master window |
| Super+Left, Super+Right | view the previous, next tag |
| Super+Shift+Left, Super+Shift+Right | move the window to the previous, next tag |
| Super+Tab | view the previous tag |
| Super+0, Super+Shift+0 | view all tags, move the window to all tags |
| Super+1..5, Super+Shift+1..5 | view tag, move window to tag |
| XF86AudioMute | toggle mute |
| XF86AudioLowerVolume, XF86AudioRaiseVolume | volume down, up |
| Super+Escape | quit dwl |

## 3. Verify

```sh
doas sh usr/host/alpine/verify.sh server
doas sh usr/host/alpine/verify.sh
```

The first command forces the server checks. The second checks the profile
recorded in `/etc/home/install-mode`; a desktop install includes every server
check. Pass `desktop` to force the desktop checks.

## 4. Recover

Quitting or crashing dwl returns tty1 to a normal shell; the exit status and
log path (`/run/user/$UID/dwl.log`) are printed. tty2 to tty6 are ordinary
logins (Ctrl+Alt+F2). The desktop starts only for an interactive tty1 login of
a `seat` member, so `doas delgroup "$USER" seat` disables it.

## 5. Reapply

Pull or edit the `usr` checkout and run `doas env INSTALL_MODE=desktop sh usr/host/alpine/install.sh`
again, or answer `desktop` at the prompt. Use `INSTALL_MODE=server` to reapply
only the headless base.
Unchanged files are left alone, dwl is rebuilt only when `build/dwl.sh` or
`config/dwl.h` changes, ghostty-custom and helium are updated only when a newer
matching prerelease appears, and each tool in the installed profile is
installed only if missing (update it with `usr`'s own `dl`). `sh dl TOOL` adds
an opt-in tool. A managed path holding something home did not install stops the
run; move it aside or merge it, then rerun.

home recognizes files it installed by comparing them with every committed
version of their source, so it needs a full clone; a shallow clone is refused.
Packages follow the edge repositories, so reruns can upgrade them.
Ghostty-custom tracks the newest `release-*` prerelease, so reruns can upgrade
it when a new Linux build is published. Helium is x86_64-only and also tracks
the newest `helium-*` prerelease; it is not installed by a server-only
provision.

## Not managed

Disks, partitions, filesystems, encryption, bootloader, kernel, initramfs, EFI,
Secure Boot, networking, DNS, passwords, root account, SSH server configuration,
authorized keys and SSH keys other than the generated GitHub key, audio routing
and mixer state, power management and lid handling. `setup.sh`
switches a stable install to edge and replaces `linux-lts` with `linux-stable`;
the provisioner itself does not manage repositories or the kernel. The desktop
layer installs `alsa-utils` and a `volume` helper for the media keys, but it
does not choose cards or persist mixer state. The desktop layer refuses to run
while `linux-lts` is installed, while a server install accepts it. Docker
daemon configuration is not managed. Tailscale authentication, tailnet policy
and ACLs, exit nodes, and subnet routes are not managed; the provisioner
installs the package, loads `tun`, runs the service, and enables Tailscale SSH
as described above.

## Hardware checklist (XPS 13 9343)

The VM test does not cover these. Check them after provisioning the laptop.

- [ ] Wi-Fi comes up after reboot on edge with `linux-stable` and udev. Edge
      broke XPS Wi-Fi once before, and a past mdev-to-eudev switch lost the
      interface until `iwlwifi` was listed in `/etc/modules`.
- [ ] `intel-ucode` is applied at boot (`dmesg | grep microcode`).
- [ ] i915 drives the panel; dwl starts on tty1 without errors in `dwl.log`.
- [ ] Keyboard, including Super bindings, and touchpad tap and two-finger scroll.
- [ ] dwl renders with GLES on i915 (the VM test forces the pixman renderer).
- [ ] `vainfo` reports `VAProfileH264` and Helium uses `VaapiVideoDecoder` for
      H.264 or VP8; VP9 and HEVC stay on software.
- [ ] Ctrl+Alt+F2 reaches a login and Ctrl+Alt+F1 returns to dwl.
- [ ] Super+p screenshot lands in the clipboard.
- [ ] Brightness, suspend and resume (not managed; note what is missing).
