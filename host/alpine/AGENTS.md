# home

Post-install provisioner for stock Alpine edge with linux-stable, not an ISO or OS distribution.
It lives at `host/alpine/` in the `usr` checkout.

- Two install modes: `server` is the headless base, and `desktop` layers the graphical session on top of it. `install.sh` prompts unless `INSTALL_MODE` is set; the desktop layer must keep working after a server-only install.
- Server mode installs only `packages.txt`, `packages-$arch.txt`, dotfile links and ish. Never install Wayland, graphics, seatd, udev or ghostty packages there.
- Keep POSIX sh, apk, OpenRC, seatd, udev, dwl and ghostty-custom. No display manager, XWayland, D-Bus or session daemons. No `make` orchestration: `install.sh`, `verify.sh` and `tests/` are plain POSIX sh; dotfiles come from `sh sync` in the enclosing checkout.
- Never manage disks, bootloaders, kernels, initramfs, repositories, passwords, doas policy or networking; check them instead (edge only, and no linux-lts for a desktop).
- No autologin or passwordless privilege escalation; seat access comes from seatd's `seat` group only.
- User dotfiles and ish come from the enclosing `usr` checkout via `sh sync links` and `sh sync tools ish` (never the full `dl` set or `setup-linux`). The login shell stays ash.
- Check everything before the first change; the dotfile plan and every mode's managed-path checks must pass before provisioning. A managed path whose content is not a committed version of its source (following renames) is a conflict.
- Reruns must not rewrite unchanged files; dwl rebuilds only when its build id changes, and ghostty-custom updates only when a newer release appears.
- Verify with `sh tests/static.sh`; run `sh tests/vm.sh` for behavior changes. Hardware testing is separate from the VM test.
