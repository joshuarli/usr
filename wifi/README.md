# Wi-Fi / home-network benchmark

Reproducible, sequential diagnostics for this Mac. Benchmarking never changes
network settings and never restarts the Wi-Fi interface.

## CLI

`bin/wifi.py` is the implementation (Python 3 standard library only). The `.sh`
files are thin wrappers for the same commands.

```sh
python3 bin/wifi.py --help
python3 bin/wifi.py bench BEFORE
python3 bin/wifi.py summary BEFORE
python3 bin/wifi.py compare BEFORE AFTER
python3 bin/wifi.py profile detect
```

`bench` writes `results/<LABEL>/raw.log` (all raw command output) and
`results/<LABEL>/metrics.env` (the scalar metrics used by `summary` and
`compare`). Each run records the detected SSID as `WIFI_SSID` /
`WIFI_PROFILE`, so home and office runs can use distinct labels and still be
compared directly.

Phases run strictly in order. All ping/traceroute work (phase 2) completes
before `networkQuality` (phase 4) starts, so idle latency is not polluted by
load. Do not run anything else network-heavy while a benchmark is running.

## Notes

- Tailscale is deliberately kept enabled. It is not an exit node: traffic to
  `1.1.1.1` / `8.8.8.8` still routes out `en0` to the default gateway. It does,
  however, own the system DNS resolver order, which is measured in phase 3.
- No native IPv6 exists on `en0`; tunnel-only IPv6 is skipped because it would
  measure Tailscale, not the LAN/ISP path.
- `en0` is the Wi-Fi interface and the default gateway is discovered at runtime.
- On macOS 27, `networksetup -getairportnetwork en0` may report "not associated"
  despite an active link. `profile detect` explains the workarounds.

## Analysis and decisions

- [`docs/airport-extreme-6th-gen.md`](docs/airport-extreme-6th-gen.md) — why the
  current router cannot fix bufferbloat, and its usable channel list.
- [`docs/router-shortlist.md`](docs/router-shortlist.md) — replacement options.
- [`docs/network-profiles.md`](docs/network-profiles.md) — SSID profiles and
  the optional LaunchAgent for automatic per-network settings.
