# Replacement router shortlist

Criteria from the baseline: real SQM for bufferbloat, modern WiFi the Mac can
use, low idle power, and root-level hackability (OpenWrt/SSH/scripting). The Mac
supports 802.11ax/be and 6 GHz; the RF scan has one 6 GHz AP, so a 6 GHz radio
is genuinely useful but not required for the measured 200–435 Mbps line.

## The sweet spot: GL.iNet Flint 2 (GL-MT6000)

- MediaTek Filogic 830, **official OpenWrt support**, root SSH, LuCI, packages.
- Dual-band WiFi 6, **4×4**, 160 MHz capable on 5 GHz (80 MHz recommended here).
- 2× 2.5 GbE (WAN + LAN) + 4× 1 GbE, 1 GB RAM, 8 GB eMMC, USB 3.
- **5.6 W idle, under 12 W under load** (ServeTheHome measurements).
- Roughly $130–170.
- macOS: standard 802.11ax/WPA2/WPA3, no vendor client needed.

This is the recommendation. It fixes the actual bottleneck (SQM), matches the
Mac's WiFi 6 capability, stays cool and quiet, and leaves full firmware control.
The only gap is no 6 GHz.

## If the empty 6 GHz band is the priority: GL.iNet Flint 3 (GL-BE9300)

- WiFi 7 tri-band including 6 GHz, 320 MHz/MLO, all ports 2.5 GbE, ~$210.
- **Caveats:** ~25 W, 2×2 radios, MLO reports are flaky, and the OpenWrt wiki
  currently says **no official upstream support** — you get GL.iNet's
  OpenWrt-derived firmware, which is still rootable but not upstream.
- If chosen, turn MLO off and run 6 GHz ch 37/160 MHz as a separate SSID.

## Maximum hackability, separate AP: MikroTik RB5009 + cAP ax / hAP ax³

- RB5009: ~7 W, 7× 1 GbE + 1× 2.5 GbE + SFP+, RouterOS scripting, CAKE SQM,
  WireGuard, VLANs. Pair with an ax AP for ~$280–350 total.
- Most tunable of the set, but a steep learning curve and two devices to manage.

## Enthusiast pick: OpenWrt One

- MT7981, 2×2 WiFi 6, 2.5 GbE + GbE, replaceable NOR firmware, ≈$89.
- Built for OpenWrt hacking and low power, but less WiFi muscle than Flint 2.

## What to configure after flashing

Install SQM and set it on the WAN interface:

```sh
opkg update && opkg install sqm-scripts luci-app-sqm
```

Start with `cake` / `piece_of_cake.qos`, download ≈180 Mbps, upload ≈390 Mbps
(about 90% of the measured line), link layer `ethernet`. Then re-run:

```sh
./bin/wifi-bench.sh AFTER
./bin/compare.sh BEFORE AFTER
```

Success criterion: loaded latency drops from ~215 ms toward <50 ms and RPM
rises above ~600. Keep 5 GHz at 80 MHz, enable WMM/802.11ax, and keep the
existing `10.0.1.0/24` subnet so device addresses do not all change.

## Under $100

6 GHz and 160 MHz are out of reach at this price. All three options below can
run CAKE SQM, which is the fix that actually matters. Set SQM a little below
the measured line (about 220 Mbps down / 380 Mbps up): you give up a small
amount of peak speed in exchange for the latency collapse.

| Model | Street price | Why | Trade-off |
|---|---|---|---|
| **OpenWrt One** | ≈$89 | Official OpenWrt, MT7981, 1 GB RAM, 2.5 GbE + GbE, NOR + NAND, JTAG/serial — most repairable and hackable | 2×2 WiFi 6; SQM likely ~300–400 Mbps |
| **GL.iNet Beryl AX (GL-MT3000)** | ≈$99 | Same MT7981, **3.5 W idle / 8 W loaded**, 2.5 GbE WAN, OpenWrt with LuCI plus GL's UI, doubles as a travel router | Small antennas, limited range; similar SQM ceiling |
| **Linksys E8450 / Belkin RT3200 (refurb)** | ≈$60–90 | 4×4 WiFi 6, 5×GbE, 512 MB RAM; OpenWrt forum reports SQM at **1 Gbps** | Used/refurb only, no 2.5 GbE, availability varies |

Pick: **OpenWrt One** for maximum hackability, **Beryl AX** for easiest UI and
lowest power, **E8450 refurb** for the most SQM headroom if you find one.

Sources: OpenWrt table of hardware for [Flint 2](https://openwrt.org/toh/gl.inet/gl-mt6000)
and [Flint 3](https://openwrt.org/toh/gl.inet/gl-be9300); ServeTheHome power
measurements for [Flint 2](https://www.servethehome.com/gl-inet-gl-mt6000-flint-2-wifi-router-review-mediatek-openwrt/3/).
