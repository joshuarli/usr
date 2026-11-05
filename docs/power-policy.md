# Linux CPU power policy

`power-policy` is a POSIX `sh` utility installed by the `usr` Linux dotfile
layer as `~/.local/bin/power-policy`. It requires only sysfs and the shell: no
systemd, D-Bus, TLP, PowerTOP, Python, or resident process. This replaces the
former `threadripper-tune` executable.

```sh
power-policy status              # source, driver, governor, EPP/EPB, boost
power-policy diff auto           # preview only; does not require root
doas "$HOME/.local/bin/power-policy" auto           # choose AC/battery once
doas "$HOME/.local/bin/power-policy" battery        # explicitly prefer energy savings
doas "$HOME/.local/bin/power-policy" ac             # explicitly prefer balanced performance
doas "$HOME/.local/bin/power-policy" performance    # performance hint + boost, where supported
```

`power-policy apply MODE` and `power-policy MODE` are equivalent, and no
arguments defaults to read-only `status`. `diff` always stays read-only. Writes
are idempotent and read back for verification; failures are reported and return
nonzero. Unsupported drivers, missing sysfs attributes, and unadvertised
values are not guessed.

## CPU driver support

| Kernel `scaling_driver` | AC / battery | Performance |
| --- | --- | --- |
| `intel_pstate` (e.g. **Intel N100 with active HWP**) | Driver's dynamic `powersave` governor; EPP `balance_performance` / `balance_power` when available | Dynamic governor with `performance` EPP, or `performance` governor without HWP; enable turbo if exposed |
| `intel_cpufreq` (Intel passive mode) | `schedutil`, else `ondemand` | `performance` governor; enable turbo if exposed |
| `amd-pstate-epp` (modern Ryzen / Threadripper) | Driver's dynamic `powersave` governor; EPP `balance_performance` / `balance_power` | `performance` EPP, keep adaptive governor, enable boost |
| `amd-pstate` (passive/guided) | `schedutil`, else `ondemand` | `performance` governor, enable boost |
| `acpi-cpufreq` (e.g. **AMD Ryzen 5 2400GE**, older CPUs) | `schedutil`, else `ondemand` | `performance` governor, enable boost if exposed |

For AMD `amd-pstate-epp`, **`auto` prefers `dynamic` EPP if the kernel offers
it**. Recent kernels can then react to AC/battery changes themselves. Older
kernels with global `amd_pstate/dynamic_epp=enabled` are also left in charge:
manual modes fail with a clear message rather than fighting kernel policy.

On older Intel without EPP, the script can use the per-CPU Energy Performance
Bias (`energy_perf_bias`) value: `0` for performance, `6` for AC, `12` for
battery. Hardware-dependent EPB values remain hints, not frequency limits.

**Important CPUFreq distinction:** for `intel_pstate` in active mode and
`amd-pstate-epp`, `powersave` allows adaptive CPU operation. For generic
CPUFreq such as the 2400GE's `acpi-cpufreq`, `powersave` can pin the CPU to
minimum frequency. This script deliberately uses the load-responsive
`schedutil` or `ondemand` governor instead. Without EPP or similar hardware
hints, the 2400GE's AC/battery settings intentionally have the same adaptive
scaling behavior; no fictitious power savings are promised.

`performance` enables the generic CPUFreq `boost` knob (`1`) and Intel
`intel_pstate/no_turbo` (`0`) if the kernel exposes them. AC and battery modes
never disable boost. The script never touches voltage, thermal limits, or
hard CPU frequency caps.

## What is deliberately out of scope

This is a small **CPU policy** utility, not a complete replacement for all
TLP features, nor a diagnostic tool like PowerTOP. It does not blindly change
PCIe ASPM, USB/PCI autosuspend, SATA link policy, Wi-Fi power saving, audio
codec timeouts, or display brightness. Those may break devices or be better
handled by kernel defaults and device-specific policy after measurements.

`auto` examines `/sys/class/power_supply` once when invoked. Systems without
a system battery (including typical N100/2400GE mini-PCs) default to AC.
Peripheral batteries marked `scope=Device` are ignored. On Intel and older
AMD, `auto` needs a new invocation after a power-source event. There is no
polling or background process.

## Optional automatic application on Alpine / OpenRC

Automatic installation is intentionally opt-in: a battery-powered laptop,
headless N100, and Threadripper workstation should not share one implicit
power policy.

For a one-shot boot policy, create executable `/etc/local.d/power-policy.start`:

```sh
#!/bin/sh
exec /home/josh/.local/bin/power-policy auto
```

Adjust the path for the host's user, then enable OpenRC's existing `local`
service with `doas rc-update add local default` if necessary.

On a desktop already running udev, an optional `/etc/udev/rules.d/90-power-policy.rules`
can re-run the one-shot command after a power-supply change:

```text
SUBSYSTEM=="power_supply", ACTION=="change", RUN+="/home/josh/.local/bin/power-policy auto"
```

Adjust the path, reload udev rules, and check behavior on real hardware. The
rule is not needed when AMD's kernel-managed dynamic EPP is sufficient. Neither
hook is installed automatically by `usr`.

## Tests and hardware validation

```sh
sh dotfiles/power-policy-test.sh
# also: dash dotfiles/power-policy-test.sh
# and: busybox ash dotfiles/power-policy-test.sh
```

The test suite uses a disposable file-backed sysfs tree, including **N100
active/passive Intel drivers**, **Ryzen 2400GE `acpi-cpufreq`**, AMD active
EPP, legacy Intel EPB, unsupported drivers, and power-source detection.
`POWER_POLICY_SYSFS_ROOT` exists only for this fixture; leave it unset on a
real machine.

After running `power-policy diff auto`, measure actual idle wall power,
responsiveness, and suspend/resume before installing boot/event hooks. The
mock tests cannot validate real firmware-specific behavior.

Kernel references: [Intel P-State](https://www.kernel.org/doc/html/latest/admin-guide/pm/intel_pstate.html), [AMD P-State](https://www.kernel.org/doc/html/latest/admin-guide/pm/amd-pstate.html).
