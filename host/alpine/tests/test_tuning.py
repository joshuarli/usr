"""Kernel option, boot menu and sysctl policy for the Alpine provisioner."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tuning  # noqa: E402

GRUB = "GRUB_CMDLINE_LINUX_DEFAULT"
EXT = "default_kernel_opts"
RYZEN = tuning.Cpu("x86_64", frozenset({"fpu", "constant_tsc", "nonstop_tsc"}), False)
NO_INVARIANT = tuning.Cpu("x86_64", frozenset({"fpu", "constant_tsc"}), False)
ARM = tuning.Cpu("aarch64", frozenset({"fp", "asimd"}), False)
LISA = (
    "GRUB_TIMEOUT=2\n"
    'GRUB_CMDLINE_LINUX_DEFAULT="modules=sd-mod,usb-storage,ext4,nvme quiet rootfstype=ext4"\n'
    "GRUB_DISABLE_RECOVERY=true\n"
)


class Options(unittest.TestCase):
    def missing(self, text: str, key: str = GRUB, cpu: tuning.Cpu = RYZEN) -> list[str]:
        return tuning.parse_options(text, key, cpu).missing(cpu)

    def refuses(self, text: str, key: str = GRUB) -> str:
        with self.assertRaises(tuning.OptionsError) as caught:
            tuning.parse_options(text, key, RYZEN)
        return str(caught.exception)

    def test_stable_tsc_needs_nowatchdog(self) -> None:
        self.assertEqual(self.missing(LISA), ["tsc=nowatchdog"])
        self.assertEqual(self.missing('default_kernel_opts="quiet rootfstype=ext4"\n', EXT), ["tsc=nowatchdog"])
        self.assertEqual(self.missing('default_kernel_opts=""\n', EXT), ["tsc=nowatchdog"])

    def test_existing_watchdog_opt_out_is_kept(self) -> None:
        for words in ("quiet tsc=nowatchdog", "tsc=reliable quiet", "tsc=nowatchdog,recalibrate",
                      "clocksource=tsc tsc=nowatchdog"):
            with self.subTest(words=words):
                self.assertEqual(self.missing(f'{GRUB}="{words}"\n'), [])

    def test_cpus_without_invariant_tsc_need_nothing(self) -> None:
        self.assertEqual(self.missing(LISA, cpu=NO_INVARIANT), [])
        self.assertEqual(self.missing(LISA, cpu=ARM), [])
        self.assertEqual(tuning.parse_options(f'{GRUB}="clocksource=hpet"\n', GRUB, ARM).missing(ARM), [])

    def test_unsafe_lines_are_refused(self) -> None:
        self.assertIn("not set", self.refuses('#GRUB_CMDLINE_LINUX_DEFAULT="quiet"\n'))
        self.assertIn("not set", self.refuses('GRUB_CMDLINE_LINUX="quiet"\n'))
        self.assertIn("more than once", self.refuses(f'{GRUB}="quiet"\n{GRUB}="splash"\n'))
        self.assertIn("double-quoted", self.refuses(f"{GRUB}='quiet'\n"))
        self.assertIn("double-quoted", self.refuses(f"{GRUB}=quiet\n"))
        self.assertIn("nowatchdog", self.refuses(f'{GRUB}="tsc=unstable"\n'))
        self.assertIn("another clocksource", self.refuses(f'{GRUB}="clocksource=hpet"\n'))
        self.assertIn("disables", self.refuses(f'{GRUB}="notsc"\n'))

    def test_rewrite_appends_only_the_missing_option(self) -> None:
        rewritten = tuning.parse_options(LISA, GRUB, RYZEN).with_required(RYZEN)
        self.assertEqual(rewritten, LISA.replace("rootfstype=ext4\"", "rootfstype=ext4 tsc=nowatchdog\""))
        self.assertEqual(self.missing(rewritten), [])
        empty = tuning.parse_options(f'{EXT}=""\n', EXT, RYZEN).with_required(RYZEN)
        self.assertEqual(empty, f'{EXT}="tsc=nowatchdog"\n')


class BootMenu(unittest.TestCase):
    MENU = ("menuentry 'Alpine' {\n  linux /vmlinuz-stable root=UUID=x ro quiet {opts}\n"
            "  initrd {ucode}/initramfs-stable\n}}\n")

    def menu(self, opts: str = "", ucode: str = "") -> str:
        return self.MENU.replace("{opts}", opts).replace("{ucode}", ucode).replace("}}", "}")

    def test_menu_without_option_or_microcode_is_stale(self) -> None:
        self.assertEqual(tuning.boot_config_stale(self.menu(), RYZEN, ["amd-ucode.img"]),
                         ["tsc=nowatchdog", "amd-ucode.img"])

    def test_regenerated_menu_is_current(self) -> None:
        menu = self.menu("tsc=nowatchdog", "/amd-ucode.img /intel-ucode.img ")
        self.assertEqual(tuning.boot_config_stale(menu, RYZEN, ["amd-ucode.img", "intel-ucode.img"]), [])

    def test_arm_menu_needs_nothing(self) -> None:
        self.assertEqual(tuning.boot_config_stale(self.menu(), ARM, []), [])

    def test_running_cmdline(self) -> None:
        self.assertEqual(tuning.cmdline_missing("BOOT_IMAGE=/boot/vmlinuz-stable quiet", RYZEN), ["tsc=nowatchdog"])
        self.assertEqual(tuning.cmdline_missing("quiet tsc=nowatchdog\n", RYZEN), [])


class Cpuinfo(unittest.TestCase):
    def test_flags_and_hypervisor(self) -> None:
        text = "processor\t: 0\nflags\t\t: fpu tsc constant_tsc nonstop_tsc hypervisor\n\nprocessor\t: 1\nflags\t: fpu\n"
        cpu = tuning.parse_cpuinfo("x86_64", text)
        self.assertTrue(cpu.stable_tsc)
        self.assertTrue(cpu.hypervisor)
        self.assertFalse(tuning.parse_cpuinfo("aarch64", "Features\t: fp asimd\n").stable_tsc)


class Sysctl(unittest.TestCase):
    def test_shipped_config_parses(self) -> None:
        text = (Path(__file__).resolve().parents[1] / "config/sysctl.conf").read_text()
        values = tuning.parse_sysctl(text)
        self.assertEqual(values["net.ipv4.tcp_congestion_control"], "bbr")
        self.assertEqual(values["net.core.default_qdisc"], "fq")
        self.assertEqual(tuning.sysctl_path("net.core.rmem_max"), "/proc/sys/net/core/rmem_max")

    def test_drift(self) -> None:
        wanted = {"vm.swappiness": "10", "net.ipv4.tcp_congestion_control": "bbr"}
        self.assertEqual(tuning.sysctl_drift(wanted, {"vm.swappiness": "10\n", "net.ipv4.tcp_congestion_control": "bbr\n"}), [])
        self.assertEqual(tuning.sysctl_drift(wanted, {"vm.swappiness": "60\n", "net.ipv4.tcp_congestion_control": None}),
                         ["vm.swappiness=60, want 10", "net.ipv4.tcp_congestion_control is unavailable"])

    def test_malformed_line_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            tuning.parse_sysctl("vm.swappiness 10\n")

    def test_modules(self) -> None:
        self.assertEqual(tuning.modules_missing("af_packet\ntun\n# tcp_bbr\n", ("tun", "tcp_bbr")), ["tcp_bbr"])


if __name__ == "__main__":
    unittest.main()
