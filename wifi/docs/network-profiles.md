# Per-network settings and SSID-aware benchmarking

The CLI is `bin/wifi.py` (Python 3 standard library only). The `.sh` files are
thin wrappers around it, so there is one implementation.

```sh
python3 bin/wifi.py --help
python3 bin/wifi.py bench home-before
python3 bin/wifi.py summary home-before
python3 bin/wifi.py compare home-before home-after
```

Every benchmark records `WIFI_SSID` and `WIFI_PROFILE` in `metrics.env`, so a
home and an office run can be compared directly by label. Use distinct labels
(`home-before`, `office-before`, `office-after`) rather than reusing `BEFORE`.

## Detecting the SSID

`profile detect` uses `networksetup -getairportnetwork en0`. On this macOS 27
host that command reports "not associated" even though `system_profiler` shows
an active 802.11ac link, and CoreWLAN returns no SSID. The usual cause is that
the terminal lacks Location Services permission.

Fix one of these ways:

- Grant Location Services to your terminal app in
  System Settings → Privacy & Security → Location Services, then reconnect.
- Set `WIFI_SSID="Name Of Network"` before running a command.
- Pass `--ssid "Name Of Network"` to `profile scaffold` or `profile apply`.

The benchmark fails safe: if SSID detection fails it records `UNKNOWN` and
applies no settings. Auto-apply refuses to change anything without a known SSID.

## Profiles

Profiles live in `profiles/<slug>.json`, where the slug is the lowercase SSID
with non-alphanumerics collapsed to `-` (`Tea & Vessel 5G` → `tea-vessel-5g`).

```json
{
  "ssid": "Tea & Vessel 5G",
  "dns": ["1.1.1.1", "8.8.8.8"],
  "web_proxy": {"host": "", "port": 0},
  "secure_web_proxy": {"host": "", "port": 0},
  "notes": "home"
}
```

- `dns`: list of server IPs. Empty list means "use DHCP" (`-setdnsservers … empty`).
- Proxy objects: an empty `host` means proxy off.
- Only Wi-Fi DNS and proxies are touched. Wi-Fi power, the interface, and
  Tailscale are never modified.

Commands:

```sh
python3 bin/wifi.py profile detect
python3 bin/wifi.py profile scaffold --ssid "Tea & Vessel 5G"
python3 bin/wifi.py profile list
python3 bin/wifi.py profile apply --dry-run
python3 bin/wifi.py profile apply
python3 bin/wifi.py profile install --interval 15
python3 bin/wifi.py profile uninstall
```

`install` writes `~/Library/LaunchAgents/com.josh.wifi-profile.plist` and loads
it. It polls the SSID every 15 seconds, applies a profile only when the SSID
changes, and logs to `~/.local/state/wifi-profiles/`. `apply --force` re-applies
the current profile; `--quiet` is used by the agent.

## Tailscale DNS caveat

Tailscale is deliberately left enabled. Its MagicDNS resolver has order 100000
while the Wi-Fi resolver has order 200000, so **Wi-Fi-specific DNS servers do
not win for general queries while Tailscale is connected**. Measured lookup
latency was ~21–25 ms either way, so this has not been a bottleneck.

If office DNS (split-horizon names, internal zones) must take precedence, that
requires either configuring those zones in Tailscale's DNS settings or setting
`tailscale set --accept-dns=false`. The latter removes tailnet name resolution
and is **not** done by this script; it needs your explicit choice first.
