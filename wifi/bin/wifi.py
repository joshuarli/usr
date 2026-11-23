#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
PROFILES = ROOT / "profiles"
IF = "en0"
SERVICE = "Wi-Fi"
STATE_DIR = Path.home() / ".local/state/wifi-profiles"
STATE_FILE = STATE_DIR / "current"
AGENT_PATH = Path.home() / "Library/LaunchAgents/com.josh.wifi-profile.plist"


def sh(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return p.stdout


def first(pattern, text, group=1, default="NA"):
    m = re.search(pattern, text, re.M)
    return m.group(group).strip() if m else default


def gateway():
    return first(r"gateway:\s*(\S+)", sh(["route", "-n", "get", "default"]))


def detect_ssid():
    override = os.environ.get("WIFI_SSID")
    if override:
        return override.strip(), "WIFI_SSID env"
    text = sh(["networksetup", "-getairportnetwork", IF])
    if "not associated" in text.lower():
        return None, "networksetup: not associated"
    m = re.search(r"Current Wi-Fi Network:\s*(.+)", text)
    if m:
        return m.group(1).strip(), "networksetup"
    return None, "no SSID source"


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def default_profile(ssid):
    return {
        "ssid": ssid,
        "dns": [],
        "web_proxy": {"host": "", "port": 0},
        "secure_web_proxy": {"host": "", "port": 0},
        "notes": "",
    }


class Bench:
    def __init__(self, label):
        self.dir = RESULTS / label
        self.dir.mkdir(parents=True, exist_ok=True)
        self.raw = (self.dir / "raw.log").open("w")
        self.metrics = {}

    def section(self, title):
        print("\n===== %s =====" % title, file=self.raw, flush=True)
        print("-> %s" % title)

    def line(self, text):
        print(text.rstrip(), file=self.raw, flush=True)

    def metric(self, key, value):
        self.metrics[key] = str(value)

    def cap(self, cmd):
        text = sh(cmd)
        self.line(text)
        return text

    def finish(self):
        with (self.dir / "metrics.env").open("w") as f:
            for key, value in self.metrics.items():
                f.write("%s=%s\n" % (key, value))
        self.raw.close()
        print("Raw:    %s" % (self.dir / "raw.log"))
        print("Metrics:%s" % (self.dir / "metrics.env"))


def block_5g(channel):
    if 36 <= channel <= 48:
        return "36-48"
    if 52 <= channel <= 64:
        return "52-64"
    if 100 <= channel <= 112:
        return "100-112"
    if 116 <= channel <= 128:
        return "116-128"
    if 132 <= channel <= 144:
        return "132-144"
    if 149 <= channel <= 161:
        return "149-161"
    return "other"


def ping_stats(text):
    return {
        "avg": first(r"round-trip[^=]*=\s*([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)", text, 2),
        "max": first(r"round-trip[^=]*=\s*([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)", text, 3),
        "stddev": first(r"round-trip[^=]*=\s*([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)", text, 4),
        "loss": first(r"([\d.]+)% packet loss", text),
    }


def cmd_bench(args):
    bench = Bench(args.label)
    gw = gateway()
    ssid, source = detect_ssid()
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    bench.section("META")
    bench.line("label=%s\ndate=%s\nhost=%s\nmacOS=%s\nwifi_interface=%s\ngateway=%s\nssid=%s\nssid_source=%s" % (
        args.label, stamp, sh(["hostname"]).strip(), sh(["sw_vers", "-productVersion"]).strip(), IF, gw, ssid or "UNKNOWN", source))
    bench.metric("META_DATE", stamp)
    bench.metric("GATEWAY", gw)
    bench.metric("WIFI_SSID", ssid or "UNKNOWN")
    bench.metric("WIFI_PROFILE", slug(ssid) if ssid else "unknown")

    bench.section("STEP 1: Wi-Fi link & RF congestion")
    sp = bench.cap(["system_profiler", "SPAirPortDataType"])
    cur = sp.split("Current Network Information:", 1)[-1].split("Other Local Wi-Fi Networks:", 1)[0]
    chan_line = first(r"Channel:\s*(.+)", cur)
    signal = first(r"Signal / Noise:\s*(-?\d+) dBm", cur)
    noise = first(r"Signal / Noise:.*/\s*(-?\d+) dBm", cur)
    try:
        snr = str(int(signal) - int(noise))
    except ValueError:
        snr = "NA"
    bench.metric("LINK_PHY", first(r"PHY Mode:\s*(.+)", cur))
    bench.metric("LINK_BAND", first(r"\((\d+GHz)", chan_line))
    bench.metric("LINK_CHANNEL", first(r"^(\d+)", chan_line))
    bench.metric("LINK_WIDTH", first(r",\s*(\d+MHz)", chan_line))
    bench.metric("LINK_SIGNAL_DBM", signal)
    bench.metric("LINK_NOISE_DBM", noise)
    bench.metric("LINK_SNR_DB", snr)
    bench.metric("LINK_TX_RATE_MBPS", first(r"Transmit Rate:\s*(\d+)", cur))
    bench.metric("LINK_MCS", first(r"MCS Index:\s*(\d+)", cur))
    errs = bench.cap(["netstat", "-i", "-I", IF])
    fields = [l.split() for l in errs.splitlines() if l.strip().startswith(IF)]
    row = fields[0] if fields else []
    bench.metric("IF_ERRORS_IN", row[5] if len(row) > 5 else "NA")
    bench.metric("IF_ERRORS_OUT", row[7] if len(row) > 7 else "NA")
    bench.metric("IF_COLLISIONS", row[8] if len(row) > 8 else "NA")

    bench.section("STEP 1b: competing AP scan")
    others = sp.split("Other Local Wi-Fi Networks:", 1)[-1].split("awdl0:", 1)[0]
    channels = {"2GHz": Counter(), "5GHz": Counter(), "6GHz": Counter()}
    blocks = Counter()
    for line in others.splitlines():
        m = re.search(r"Channel: (\d+) \((2GHz|5GHz|6GHz)", line)
        if not m:
            continue
        ch, band = int(m.group(1)), m.group(2)
        channels[band][ch] += 1
        if band == "5GHz":
            blocks[block_5g(ch)] += 1
    for band in channels:
        bench.line("%s APs: %d" % (band, sum(channels[band].values())))
        bench.line("  " + ", ".join("ch%d=%d" % (c, n) for c, n in sorted(channels[band].items())))
    bench.line("5GHz 80MHz blocks: " + ", ".join("%s=%d" % (b, n) for b, n in sorted(blocks.items())))
    bench.metric("AP_COUNT_5GHZ", sum(channels["5GHz"].values()))
    bench.metric("AP_COUNT_24GHZ", sum(channels["2GHz"].values()))
    bench.metric("AP_COUNT_6GHZ", sum(channels["6GHz"].values()))
    nonoverlap = {c: n for c, n in channels["2GHz"].items() if c in (1, 6, 11)}
    bench.metric("CLEANEST_24GHZ", min(nonoverlap, key=nonoverlap.get) if nonoverlap else "NA")
    bench.metric("CLEANEST_5GHZ_BLOCK", min(blocks, key=blocks.get) if blocks else "NA")

    bench.section("STEP 2: hop-by-hop latency (idle)")
    ping_suffix = {"avg": "AVG_MS", "max": "MAX_MS", "stddev": "STDDEV_MS", "loss": "LOSS_PCT"}
    for key, target in (("GW", gw), ("INET", "1.1.1.1")):
        text = bench.cap(["ping", "-c", "30", target])
        stats = ping_stats(text)
        for name, value in stats.items():
            bench.metric("%s_PING_%s" % (key, ping_suffix[name]), value)
    v6 = [l.split()[1] for l in sh(["ifconfig", IF]).splitlines() if "inet6" in l and not l.split()[1].startswith("fe80")]
    if v6:
        text = bench.cap(["ping6", "-c", "30", "2606:4700:4700::1111"])
        bench.metric("V6_PING_AVG_MS", ping_stats(text)["avg"])
    else:
        bench.line("IPv6 skipped: no global IPv6 address on %s." % IF)
        bench.metric("V6_PING_AVG_MS", "SKIPPED")
    bench.cap(["traceroute", "-m", "5", "-w", "2", "-q", "2", "1.1.1.1"])

    bench.section("STEP 2b: VPN / proxies / hogs / Wi-Fi events")
    bench.cap(["scutil", "--nc", "list"])
    if shutil.which("tailscale"):
        bench.cap(["tailscale", "status"])
    if sh(["ifconfig", "utun4"]).strip():
        bench.cap(["netstat", "-i", "-I", "utun4"])
    bench.cap(["networksetup", "-getwebproxy", SERVICE])
    bench.cap(["networksetup", "-getsecurewebproxy", SERVICE])
    logs = sh(["log", "show", "--last", "30m", "--style", "compact", "--predicate",
               'eventMessage CONTAINS "roam" OR eventMessage CONTAINS "disconnect" OR eventMessage CONTAINS "AirPort" OR eventMessage CONTAINS "Wi-Fi"'])
    bench.line("\n".join(logs.splitlines()[-40:]))

    bench.section("STEP 3: DNS latency")
    bench.cap(["scutil", "--dns"])
    nonce = str(int(time.time()))
    system = bench.cap(["dig", "+noall", "+stats", "+time=2", "+tries=1", "b%s.example.com" % nonce, "A"])
    bench.metric("DNS_SYSTEM_MS", first(r"Query time: (\d+) msec", system))
    for name, server in (("TAILSCALE", "100.100.100.100"), ("ROUTER", gw),
                         ("CLOUDFLARE", "1.1.1.1"), ("GOOGLE", "8.8.8.8")):
        q = bench.cap(["dig", "@" + server, "+noall", "+stats", "+time=2", "+tries=1",
                       "b%s.%s.example.com" % (nonce, name.lower()), "A"])
        bench.metric("DNS_%s_MS" % name, first(r"Query time: (\d+) msec", q))

    bench.section("STEP 4: throughput & bufferbloat (alone)")
    nq = bench.cap(["networkQuality", "-v"])
    bench.metric("NQ_DL_MBPS", first(r"Downlink capacity:\s*([\d.]+)", nq))
    bench.metric("NQ_UL_MBPS", first(r"Uplink capacity:\s*([\d.]+)", nq))
    bench.metric("NQ_IDLE_MS", first(r"Idle Latency:\s*([\d.]+) milliseconds", nq))
    resp = re.search(r"Responsiveness:.*\(([\d.]+) milliseconds \| (\d+) RPM", nq)
    bench.metric("NQ_LOADED_MS", resp.group(1) if resp else "NA")
    bench.metric("NQ_RPM", resp.group(2) if resp else "NA")
    bench.metric("NQ_ECN", first(r"ECN (\w+):.*L4S (\w+)", nq, 1))
    bench.metric("NQ_L4S", first(r"ECN (\w+):.*L4S (\w+)", nq, 2))
    bench.finish()


def load_metrics(label):
    path = RESULTS / label / "metrics.env"
    if not path.exists():
        raise SystemExit("No metrics for %s. Run: wifi.py bench %s" % (label, label))
    values = {}
    for line in path.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


SUMMARY_KEYS = [
    ("META_DATE", "date"), ("WIFI_SSID", "ssid"), ("LINK_PHY", "link"),
    ("LINK_CHANNEL", "channel"), ("LINK_WIDTH", "width"), ("LINK_SIGNAL_DBM", "signal"),
    ("LINK_NOISE_DBM", "noise"), ("LINK_SNR_DB", "snr"), ("LINK_TX_RATE_MBPS", "phy"),
    ("LINK_MCS", "mcs"), ("IF_ERRORS_IN", "rx_err"), ("IF_ERRORS_OUT", "tx_err"),
    ("AP_COUNT_5GHZ", "ap_5g"), ("AP_COUNT_24GHZ", "ap_2g"), ("AP_COUNT_6GHZ", "ap_6g"),
    ("CLEANEST_24GHZ", "clean_2g"), ("CLEANEST_5GHZ_BLOCK", "clean_5g"),
    ("GW_PING_AVG_MS", "gw_avg_ms"), ("GW_PING_STDDEV_MS", "gw_sd_ms"),
    ("INET_PING_AVG_MS", "inet_avg_ms"), ("INET_PING_STDDEV_MS", "inet_sd_ms"),
    ("GW_PING_LOSS_PCT", "gw_loss"), ("INET_PING_LOSS_PCT", "inet_loss"),
    ("DNS_SYSTEM_MS", "dns_system"), ("DNS_ROUTER_MS", "dns_router"),
    ("DNS_CLOUDFLARE_MS", "dns_cf"), ("NQ_DL_MBPS", "down_mbps"),
    ("NQ_UL_MBPS", "up_mbps"), ("NQ_IDLE_MS", "idle_ms"),
    ("NQ_LOADED_MS", "loaded_ms"), ("NQ_RPM", "rpm"), ("NQ_ECN", "ecn"), ("NQ_L4S", "l4s"),
]


def cmd_summary(args):
    m = load_metrics(args.label)
    print("=== %s (%s) ===" % (args.label, m.get("META_DATE", "?")))
    for key, label in SUMMARY_KEYS:
        print("%-18s %s" % (label + ":", m.get(key, "-")))
    print("raw: %s" % (RESULTS / args.label / "raw.log"))


COMPARE_KEYS = [k for k, _ in SUMMARY_KEYS if k != "META_DATE"]


def cmd_compare(args):
    before, after = load_metrics(args.before), load_metrics(args.after)
    print("%-26s %14s %14s %10s" % ("METRIC", "BEFORE", "AFTER", "CHANGE"))
    print("%-26s %14s %14s %10s" % ("-" * 26, "-" * 14, "-" * 14, "-" * 10))
    for key in COMPARE_KEYS:
        b, a = before.get(key, "-"), after.get(key, "-")
        delta = "-"
        try:
            delta = "%+.2f" % (float(a) - float(b))
        except ValueError:
            pass
        print("%-26s %14s %14s %10s" % (key, b, a, delta))


def profile_file(ssid):
    return PROFILES / (slug(ssid) + ".json")


def cmd_profile(args):
    if args.action == "detect":
        ssid, source = detect_ssid()
        gw = gateway()
        print("SSID:    %s" % (ssid or "UNKNOWN"))
        print("Source:  %s" % source)
        print("Gateway: %s" % gw)
        print("Profile: %s" % (profile_file(ssid) if ssid else "none"))
        if not ssid:
            print("Hint: grant Location Services to your terminal, or set WIFI_SSID.")
        return

    if args.action == "list":
        for path in sorted(PROFILES.glob("*.json")):
            print(path.name)
        if not list(PROFILES.glob("*.json")):
            print("(no profiles yet)")
        return

    if args.action == "scaffold":
        ssid = args.ssid or detect_ssid()[0]
        if not ssid:
            raise SystemExit("No SSID detected. Use --ssid NAME.")
        path = profile_file(ssid)
        if path.exists() and not args.force:
            raise SystemExit("Profile already exists: %s" % path)
        path.write_text(json.dumps(default_profile(ssid), indent=2) + "\n")
        print("Wrote %s" % path)
        return

    if args.action == "apply":
        ssid = args.ssid or detect_ssid()[0]
        if not ssid:
            raise SystemExit("No SSID detected; refusing to change settings. Set WIFI_SSID or use --ssid.")
        path = profile_file(ssid)
        if not path.exists():
            raise SystemExit("No profile for %s (%s). Run: wifi.py profile scaffold --ssid %r" % (ssid, path, ssid))
        profile = json.loads(path.read_text())
        name = slug(ssid)
        if not args.force and STATE_FILE.exists() and STATE_FILE.read_text().strip() == name:
            if not args.quiet:
                print("Already applied: %s" % name)
            return
        dns = profile.get("dns", [])
        commands = [["networksetup", "-setdnsservers", SERVICE] + (dns if dns else ["empty"])]
        for key, setter, state in (("web_proxy", "-setwebproxy", "-setwebproxystate"),
                                   ("secure_web_proxy", "-setsecurewebproxy", "-setsecurewebproxystate")):
            cfg = profile.get(key, {})
            host = cfg.get("host", "")
            port = cfg.get("port", 0)
            if host and port:
                commands.append(["networksetup", setter, SERVICE, str(host), str(port)])
            else:
                commands.append(["networksetup", state, SERVICE, "off"])
        commands.append(["dscacheutil", "-flushcache"])
        for cmd in commands:
            print(" ".join(cmd))
            if not args.dry_run:
                result = sh(cmd)
                if result.strip():
                    print(result.strip())
        if not args.dry_run:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(name + "\n")
            if not args.quiet:
                print("Applied profile %s" % name)
        print("Note: Tailscale MagicDNS (order 100000) still outranks Wi-Fi DNS (200000) while connected.")
        return

    if args.action in ("install", "uninstall"):
        if args.action == "uninstall":
            if AGENT_PATH.exists():
                sh(["launchctl", "bootout", "gui/%s" % os.getuid(), str(AGENT_PATH)])
                AGENT_PATH.unlink()
            print("Uninstalled LaunchAgent")
            return
        ssid, _ = detect_ssid()
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        plist = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.josh.wifi-profile</string>
  <key>ProgramArguments</key><array>
    <string>%s</string><string>%s</string>
    <string>profile</string><string>apply</string><string>--quiet</string>
  </array>
  <key>StartInterval</key><integer>%d</integer>
  <key>RunAtLoad</key><true/>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>%s</string>
  <key>StandardErrorPath</key><string>%s</string>
</dict></plist>
""" % (sys.executable, ROOT / "bin/wifi.py", args.interval, STATE_DIR / "launchd.log", STATE_DIR / "launchd.err")
        AGENT_PATH.write_text(plist)
        sh(["launchctl", "bootout", "gui/%s" % os.getuid(), str(AGENT_PATH)])
        sh(["launchctl", "bootstrap", "gui/%s" % os.getuid(), str(AGENT_PATH)])
        print("Installed %s (every %ds)" % (AGENT_PATH, args.interval))
        print("Current profile: %s" % (slug(ssid) if ssid else "unknown"))
        return


def main():
    parser = argparse.ArgumentParser(prog="wifi.py", description="Sequential Wi-Fi/network benchmark and SSID profiles")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("bench", help="run the four-phase benchmark")
    p.add_argument("label")
    p.set_defaults(func=cmd_bench)
    p = sub.add_parser("summary", help="show measured summary for a label")
    p.add_argument("label", nargs="?", default="BEFORE")
    p.set_defaults(func=cmd_summary)
    p = sub.add_parser("compare", help="compare two labels")
    p.add_argument("before", nargs="?", default="BEFORE")
    p.add_argument("after", nargs="?", default="AFTER")
    p.set_defaults(func=cmd_compare)
    p = sub.add_parser("profile", help="SSID-based settings")
    p.add_argument("action", choices=["detect", "list", "scaffold", "apply", "install", "uninstall"])
    p.add_argument("--ssid", help="override SSID detection")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--interval", type=int, default=15)
    p.set_defaults(func=cmd_profile)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
