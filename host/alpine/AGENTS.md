# home

Post-install provisioner for stock Alpine edge with linux-stable, not an ISO or OS distribution.
It lives at `host/alpine/` in the `usr` checkout.

- Two install modes: `server` is the headless base, and `desktop` layers the graphical session on top of it. `install.sh` prompts unless `INSTALL_MODE` is set; the desktop layer must keep working after a server-only install.
- Server mode installs only `packages.txt`, `packages-$arch.txt`, dotfile links and the minimal server tool profile in `tools-server.txt`. Never install Wayland, graphics, seatd, udev or ghostty packages there.
- The server tool profile is part of the provisioner contract: `install.sh` installs it with `sh sync tools`, and `verify.sh` checks its launchers. Desktop mode installs the full default `dl` set. Write `/etc/home/install-mode` so `dl`, `sync`, and `doctor` follow the installed profile.
- Keep POSIX sh, apk, OpenRC, seatd, udev, dwl and ghostty-custom. No display manager, XWayland, D-Bus or session daemons. No `make` orchestration: `install.sh`, `verify.sh` and `tests/` are plain POSIX sh; dotfiles come from `sh sync` in the enclosing checkout.
- Never manage disks, bootloaders, kernels, initramfs, repositories, passwords or networking apart from Tailscale; check them instead (edge only, and no linux-lts for a desktop). The `host/setup.sh` bootstrap stops after stable-to-edge conversion; reboot before rerunning it to provision.
- Grant passwordless `doas` only to the configured user through `/etc/doas.d/30-home-nopass.conf`; preserve every other rule and never make `wheel` passwordless.
- Create an unencrypted Ed25519 GitHub key at `~/.ssh/github` only when its path is unused; preserve a valid existing pair and print only its public half.
- In `host/setup.sh`, use `gh` device login with `admin:public_key` only when needed and register `~/.ssh/github.pub` as an authentication key; never expose tokens or private keys.
- Tailscale is part of the server base: add `tun` to `/etc/modules`, enable the `modules` service in `boot`, enable and start the `tailscale` service, and enable Tailscale SSH. `TS_AUTHKEY` logs in during provisioning; without it, log in interactively when stderr is a terminal, otherwise leave the node logged out and print `doas tailscale up --ssh`. Never manage tailnet policy, ACLs, exit nodes or subnet routes.
- Docker Engine and CLI are part of the server base; enable and start `docker` and add the user to `docker`. Docker group membership grants root-equivalent host access and is the explicit passwordless Docker permission.
- `make` and rustup are part of the server base; rustup is initialized for the user before tools are installed because kache needs it when `sh sync` installs kache.
- `pnpm` ships with `nodejs` in the default tool set; neither is part of the minimal server profile.
- No autologin; seat access comes from seatd's `seat` group only.
- User dotfiles come from the enclosing `usr` checkout via `sh sync links`; the server tool profile, or the full `dl` set on desktop, comes from `sh sync tools` (never `setup-linux`). The account shell stays ash for OpenSSH command execution and login profile startup; interactive logins hand off to ish.
- Check everything before the first change; the dotfile plan and every mode's managed-path checks must pass before provisioning. A managed path whose content is not a committed version of its source (following renames) is a conflict.
- Reruns must not rewrite unchanged files; dwl rebuilds only when its build id changes, and ghostty-custom updates only when a newer release appears.
- Verify with `sh tests/static.sh`; run `sh tests/vm.sh` for behavior changes. Hardware testing is separate from the VM test. `static.sh` runs syntax, shellcheck and package-name checks. `vm.sh` needs `qemu` and `nc`, provisions the committed `HEAD` in QEMU (Alpine edge, `linux-stable`, aarch64), checks the server base and desktop across a rerun and reboot, and runs from `host/alpine/`.
