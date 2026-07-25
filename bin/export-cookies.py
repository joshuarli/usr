#!/usr/bin/env python3
"""Export cookies from Helium or Safari in Netscape format."""

import json
import os
import re
import shutil
import sqlite3
import struct
import sys
import tempfile

MAC_EPOCH_DELTA = 978307200  # seconds between Mac (2001-01-01) and Unix (1970-01-01) epochs


def mac_abs_to_unix(t):
    return t + MAC_EPOCH_DELTA if t else 0


def parse_binary_cookies(path):
    """Yield Netscape-format rows from Safari's binary cookie file."""
    with open(path, "rb") as f:
        data = f.read()

    if len(data) < 8 or data[:4] != b"cook":
        return

    num_pages = struct.unpack(">I", data[4:8])[0]
    page_sizes_end = 8 + num_pages * 4
    if page_sizes_end > len(data):
        return
    page_sizes = struct.unpack(">" + "I" * num_pages, data[8:page_sizes_end])
    pos = page_sizes_end

    for page_size in page_sizes:
        page_start = pos
        page_end = pos + page_size
        if page_size < 8 or page_end > len(data):
            break
        num_cookies = struct.unpack("<I", data[pos + 4 : pos + 8])[0]

        offsets = []
        for i in range(num_cookies):
            off = pos + 8 + i * 4
            if off + 4 > page_end:
                break
            offsets.append(struct.unpack("<I", data[off : off + 4])[0])

        for co in offsets:
            cs = page_start + co
            if cs + 48 > page_end:
                continue
            record_size = struct.unpack("<I", data[cs : cs + 4])[0]
            if record_size < 48 or cs + record_size > page_end:
                continue

            def read_str(offset):
                at = cs + offset
                if offset < 0 or at >= cs + record_size:
                    return ""
                end = data.find(b"\x00", at, cs + record_size)
                return data[at:end].decode("utf-8", errors="replace") if end != -1 else ""

            flags = struct.unpack("<I", data[cs + 8 : cs + 12])[0]
            domain_off, name_off, path_off, value_off = struct.unpack(
                "<iiii", data[cs + 16 : cs + 32]
            )
            expiry_raw = struct.unpack("<d", data[cs + 32 : cs + 40])[0]
            domain = read_str(domain_off)
            name = read_str(name_off)
            path = read_str(path_off)
            value = read_str(value_off)
            secure = "TRUE" if flags & 1 else "FALSE"
            expires = mac_abs_to_unix(int(expiry_raw)) if expiry_raw else 0
            yield (domain, "TRUE", path, secure, expires, name, value)

        pos = page_end


SAFARI_PATHS = [
    os.path.expanduser(
        "~/Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies"
    ),
    os.path.expanduser("~/Library/Cookies/Cookies.binarycookies"),
]

CHROME_BASE = os.path.expanduser("~/Library/Application Support/net.imput.helium")


def find_chrome_cookies():
    state_path = os.path.join(CHROME_BASE, "Local State")
    profile = "Default"
    try:
        with open(state_path) as f:
            state = json.load(f)
            profile = state.get("profile", {}).get("last_used", "Default")
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    db = os.path.join(CHROME_BASE, profile, "Cookies")
    if not os.path.isfile(db):
        print(f"Chrome cookies DB not found: {db}", file=sys.stderr)
        return None
    return db


def find_safari_cookies():
    for p in SAFARI_PATHS:
        if os.path.isfile(p):
            return p
    print("Safari cookies file not found", file=sys.stderr)
    return None


def query_chrome(db_path, hostname):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".cookies")
    try:
        shutil.copy2(db_path, tmp.name)
        tmp.close()
        con = sqlite3.connect(tmp.name)
        rows = con.execute(
            """SELECT host_key, 'TRUE', path,
                      CASE WHEN is_secure THEN 'TRUE' ELSE 'FALSE' END,
                      CASE WHEN expires_utc = 0 THEN 0
                           ELSE CAST(expires_utc / 1000000 - 11644473600 AS INTEGER)
                      END,
                      name, value
               FROM cookies
               WHERE lower(host_key) = ? OR lower(host_key) LIKE ?
               ORDER BY host_key, name""",
            (hostname, f"%.{hostname}"),
        ).fetchall()
        con.close()
    finally:
        os.unlink(tmp.name)
    return rows


def query_safari(db_path, hostname):
    try:
        rows = list(parse_binary_cookies(db_path))
    except PermissionError:
        print("Cannot read Safari cookies — grant Full Disk Access to Terminal in"
              " System Settings > Privacy & Security > Full Disk Access", file=sys.stderr)
        return []
    return [r for r in rows if host_matches(r[0], hostname)]


def host_matches(cookie_host, hostname):
    cookie_host = cookie_host.lower().lstrip(".")
    return cookie_host == hostname or cookie_host.endswith("." + hostname)


if __name__ == "__main__":
    args = [a.lower() for a in sys.argv[1:]]
    if len(args) != 2 or args[0] not in {"safari", "helium"}:
        print("Usage: export-cookies.py [safari|helium] hostname", file=sys.stderr)
        sys.exit(1)

    target, hostname = args
    if not re.fullmatch(
        r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*",
        hostname,
    ):
        print(f"Invalid hostname: {hostname}", file=sys.stderr)
        sys.exit(1)

    all_rows = []
    if target == "helium":
        db = find_chrome_cookies()
        if db:
            all_rows.extend(query_chrome(db, hostname))
    else:
        db = find_safari_cookies()
        if db:
            all_rows.extend(query_safari(db, hostname))

    if not all_rows:
        print("No cookies found", file=sys.stderr)
        sys.exit(1)

    all_rows.sort(key=lambda r: (r[0], r[5]))
    with open(f"cookies-{hostname}.txt", "w") as out:
        out.write("# Netscape HTTP Cookie File\n")
        for row in all_rows:
            out.write("\t".join(str(v) for v in row) + "\n")
