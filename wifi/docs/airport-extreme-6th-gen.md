# AirPort Extreme 6th generation (A1521) — diagnosis implications

## Identification

The connected link in the baseline is **802.11ac, 80 MHz, 866 Mbps PHY, MCS 8–9**.
The 5th-generation AirPort Extreme (A1408, 2011) is **802.11n only** and cannot
produce that association. This is therefore the 6th-generation model, **A1521**
(2013, 802.11ac draft, 3×3, up to 1.3 Gbps PHY, six-element beamforming).
Confirm by reading the model number on the bottom of the unit (`A1521` vs `A1408`).

Apple's published specs: <https://support.apple.com/en-us/112419>

## What this router is

- 802.11a/b/g/n/ac, simultaneous dual-band, 3×3 MIMO on 5 GHz, beamforming.
- US approved channels: **2.4 GHz 1–11; 5 GHz 36–116, 132–140, 149–165**.
- Gigabit WAN + three Gigabit LAN ports, guest network, NAT firewall.
- WPA2 Personal/Enterprise. No WPA3, no 6 GHz.
- AirPort Utility 6.3.9 is the last management app; the hardware is vintage/EOL
  with no security maintenance.

## What it cannot do (and why that matters here)

| Capability | AirPort Extreme 6th gen | Baseline impact |
|---|---|---|
| 802.11ax / OFDMA / TWT / MU-MIMO | No | Cannot improve airtime efficiency in a 33-AP 5 GHz environment |
| 160 MHz channels | No — 802.11ac Wave 1, 80 MHz max | Cannot widen the 5 GHz pipe |
| 6 GHz operation | No | The one clean band in the scan (ch 37/160 MHz, 1 AP) is unreachable |
| SQM / CAKE / fq_codel / HTB | No | **The #1 bottleneck is unfixable on this hardware** |
| Per-client bandwidth limits / real QoS | No | Cannot control a misbehaving client |
| WPA3 | No | Security, not throughput |

## Channel-plan correction from the RF scan

The scan reported the cleanest 80 MHz block as **132–144** (1 AP), then
**116–128** (2), then **100–112** (3). On this router most of those are unusable:

- 132–144 needs channel **144**, which is not in Apple's US list (ends at 140).
- 116–128 needs channels 120–128, also not approved for the US.
- 52–64 needs channels 52–64, also not in Apple's US list (starts at 36, then 100).
- **100–112** is usable but DFS (radar-triggered channel changes).
- **36–48** and **149–161** are the usable non-DFS 80 MHz blocks.

Counts for those two: 36–48 = 11 APs, 149–161 = 10 APs. **The client is already on
the cleaner of the two (ch 149), so there is no worthwhile 5 GHz channel change.**
For 2.4 GHz, channel **1** is the cleanest of 1/6/11.

Note: the client RF itself is healthy — SNR 66 dB, zero interface errors, MCS 8–9.
Channel changes are therefore low impact; do not expect them to change the
baseline numbers.

## What AirPort Utility can still tune

- Manual 2.4 GHz channel (1–11) and 5 GHz channel (from the approved list).
- Radio mode (802.11ac/n/a on 5 GHz, 802.11b/g/n on 2.4 GHz).
- A separate 5 GHz network name — this opts out of Apple's single-SSID band
  selection, which is the closest thing this router has to band steering.
- Guest network on/off (disable it if unused).
- Firmware version check (no further updates expected).

The exact click paths depend on the AirPort Utility version and should be taken
from a screenshot of the Wireless tab rather than guessed.

## Bottom line

Two of the three real bottlenecks are outside this box:

1. **Bufferbloat** — loaded latency 214.7 ms vs 11.2 ms idle, RPM 279, ECN and
   L4S disabled. Needs SQM on a router; the AirPort cannot provide it.
2. **ISP path instability** — Sonic hop 5 alternates between ~109 ms and ~147 ms
   across different core routers, with a logged 60 s flow timeout. External.
3. **WiFi generation ceiling** — 866 Mbps ac link. Only a replacement AP with
   WiFi 6/6E/7 fixes this, and it also unlocks the empty 6 GHz band.

Safe local tuning exists but is low impact. The durable fix is replacing the
AirPort with an SQM-capable, OpenWrt-based router; see `docs/router-shortlist.md`.
