#!/usr/bin/env python3

import argparse
import re
import subprocess
import sys


def diskutil_list():
    return subprocess.run(
        ["diskutil", "list"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def parse_disk0(output):
    parts = []
    in_disk0 = False

    for line in output.splitlines():
        if line.startswith("/dev/disk0 ") and "(internal, physical)" in line:
            in_disk0 = True
            continue

        if in_disk0 and line.startswith("/dev/"):
            break

        if not in_disk0:
            continue

        # Parse from the right so column alignment doesn't matter.
        m = re.match(
            r"^\s*(\d+):\s+(.+?)\s+"
            r"([\d.]+)\s+(?:KB|MB|GB|TB)\s+"
            r"(disk0s\d+)\s*$",
            line,
            re.IGNORECASE,
        )

        if not m:
            continue

        number, description, size, identifier = m.groups()
        fields = description.split(None, 1)

        if not fields:
            continue

        parts.append({
            "number": int(number),
            "type": fields[0],
            "name": fields[1] if len(fields) > 1 else "",
            "size": size,
            "id": identifier,
        })

    return parts


def derive_plan(parts):
    # EFI - ASAHI is our anchor.
    efi_matches = [
        p for p in parts
        if p["type"] == "EFI"
        and "ASAHI" in p["name"].upper()
    ]

    if len(efi_matches) != 1:
        raise RuntimeError(
            f"expected exactly one Asahi EFI partition, "
            f"found {len(efi_matches)}"
        )

    efi = efi_matches[0]
    efi_index = parts.index(efi)

    # The Asahi APFS stub immediately precedes EFI.
    if efi_index < 1:
        raise RuntimeError("Asahi EFI has no preceding partition")

    stub = parts[efi_index - 1]

    if stub["type"] != "Apple_APFS":
        raise RuntimeError(
            f"partition before Asahi EFI is not Apple_APFS: "
            f"{stub['id']} ({stub['type']} {stub['name']})"
        )

    # The macOS APFS container immediately precedes the Asahi stub.
    if efi_index < 2:
        raise RuntimeError("could not locate macOS APFS container")

    macos = parts[efi_index - 2]

    if macos["type"] != "Apple_APFS":
        raise RuntimeError(
            f"partition before Asahi stub is not Apple_APFS: "
            f"{macos['id']} ({macos['type']} {macos['name']})"
        )

    # Linux filesystem partitions after EFI, stopping at Recovery.
    linux = []

    for p in parts[efi_index + 1:]:
        if p["type"] == "Apple_APFS_Recovery":
            break

        if p["type"] == "Linux" and p["name"] == "Filesystem":
            linux.append(p)
        else:
            raise RuntimeError(
                "unexpected partition between Asahi EFI and Recovery: "
                f"{p['id']} ({p['type']} {p['name']})"
            )

    if not linux:
        raise RuntimeError(
            "no Linux Filesystem partitions found after Asahi EFI"
        )

    # Exactly one Apple recovery partition must exist.
    recovery = [
        p for p in parts
        if p["type"] == "Apple_APFS_Recovery"
    ]

    if len(recovery) != 1:
        raise RuntimeError(
            f"expected exactly one Apple_APFS_Recovery partition, "
            f"found {len(recovery)}"
        )

    recovery = recovery[0]

    if recovery["number"] <= linux[-1]["number"]:
        raise RuntimeError(
            "Apple_APFS_Recovery is not after the Linux partitions"
        )

    commands = [
        ["diskutil", "apfs", "deleteContainer", stub["id"]],
        ["diskutil", "eraseVolume", "free", "free", efi["id"]],
    ]

    commands.extend(
        ["diskutil", "eraseVolume", "free", "free", p["id"]]
        for p in linux
    )

    # 0 means consume all available free space.
    commands.append(
        ["diskutil", "apfs", "resizeContainer", macos["id"], "0"]
    )

    return {
        "macos": macos,
        "stub": stub,
        "efi": efi,
        "linux": linux,
        "recovery": recovery,
        "commands": commands,
    }


def print_command(command):
    print("$", " ".join(command))


def main():
    parser = argparse.ArgumentParser(
        description="Uninstall Asahi Linux and reclaim its disk space."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="execute the derived commands (default: dry run)",
    )
    args = parser.parse_args()

    if sys.platform != "darwin":
        sys.exit("error: this script must be run from macOS")

    try:
        parts = parse_disk0(diskutil_list())

        if not parts:
            raise RuntimeError("could not parse /dev/disk0")

        plan = derive_plan(parts)

    except subprocess.CalledProcessError as e:
        sys.exit(f"error running diskutil: {e}")
    except RuntimeError as e:
        sys.exit(f"error: {e}")

    print("Detected layout:")
    print()
    print(f"  macOS APFS : {plan['macos']['id']} ({plan['macos']['size']} GB)")
    print(f"  Asahi stub : {plan['stub']['id']} ({plan['stub']['size']} GB)")
    print(f"  Asahi EFI  : {plan['efi']['id']} ({plan['efi']['size']} MB)")
    print(
        "  Linux      :",
        " ".join(
            f"{p['id']} ({p['size']} GB)"
            for p in plan["linux"]
        ),
    )
    print(
        f"  Recovery   : {plan['recovery']['id']} "
        f"({plan['recovery']['size']} GB) [PROTECTED]"
    )

    print()
    print("Derived commands:")
    print()

    for command in plan["commands"]:
        print_command(command)

    print()

    if not args.apply:
        print("DRY RUN: no changes were made.")
        print()
        print("Run with --apply to execute these commands.")
        return

    print("WARNING: the commands above will permanently remove Asahi Linux.")
    print("The Apple Recovery partition will not be touched.")
    print()

    if input("Type 'REMOVE ASAHI' to continue: ") != "REMOVE ASAHI":
        print("Aborted. Nothing changed.")
        return

    print()

    for command in plan["commands"]:
        print_command(command)
        subprocess.run(command, check=True)
        print()

    print("Asahi has been removed and the macOS APFS container resized.")
    print()
    print("Final disk layout:")
    print(diskutil_list())


if __name__ == "__main__":
    main()
