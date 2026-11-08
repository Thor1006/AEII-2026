# Plan: stop the live-data pauses on 2.4 GHz (sensors → Pi → dashboard)

**Status:** approved in part — the user: "can you build it with no pi? and we can test it tomorrow". Built 2026-11-08
(uncommitted, [report](../output/2026-11-08-2240-wifi-pause-fixes-built.md)): 1, 2 (plus `env_hz = 25`), 3, 7, firmware
13 (compiled, not uploaded), `recorder/link_report.py` for the quick check, and the steps for 4–6 and 10–12 in
`deploy/pi/README.md`. Left: the quick check on the Pi; 8, 9, 14 (only if the check shows lost data), 15–16
**Date:** 2026-11-08

## Why
The user: "can you think of a solution to solve the temporary drop in 2.4Ghz that appear when connecting to Pi via
websocket? ... I want a bunch of solution that's truly viable". My draft was challenged by five reviewers (radio,
ESP32 firmware, bridge/dashboard code, Pi Linux, devil's advocate). What survived is below.

## What we found
- **No measurement involved the Pi or a dashboard yet.** Nov 5, IMU → Mac recorder
  ([report](../output/2026-11-05-0012-imu-wifi-link.md)):
  - Bench, 140 s: 2 real network pauses (1.18 s, 1.06 s). The data was held, then delivered, starting with a tiny
    chunk: the signature of the ESP32's TCP resend timer.
  - Worn: all 28 pauses were the IMU board's own freezes (its clock jumps by the same amount), not Wi-Fi.
  - Every session: ~75 ms of delay every 524 ms, most likely the Mac's AWDL (AirDrop/Handoff) radio. It affects a
    Mac as receiver or viewer only.
- **The ESP32's TCP** (arduino-esp32 3.3.12, lwIP; checked in its source):
  - One lost packet is resent after ~60–80 ms.
  - A radio blackout of ≳0.1 s (≥5 lost packets) or a lost resend waits for the resend timer: **1.0–2.0 s**, never
    less; the next waits add 2.5–3 s, then 5.5–6 s. Arduino code can't shorten it.
  - So ~1–2-s pauses = resend timer after a short blackout; 0.1–0.5-s pauses = the link itself or queues.
- **Real data loss** (not just delay) happens only around a reconnect:
  - the board buffers only while a client is connected (`myoware_record.ino:128`);
  - a Wi-Fi rejoin always kills the TCP link;
  - the bridge needs ~7–9 s to notice (`emg.py` IDLE_S 6);
  - a stall of ≥3.5 s overflows the board's ~3-s buffer.
- **The dashboard stream is small:** 0.297 MB/s before compression, ~0.13 MB/s on the air (permessage-deflate is on),
  ~180 packets/s, ~10–20 % of 2.4-GHz airtime per viewer. At home that's milliseconds of jitter, not pauses; on a
  crowded venue channel it makes everything worse.
- **The Pi:** its queues hold an ACK for a few to tens of ms, not hundreds. Power save is on but only sleeps after
  2 s of silence, so not mid-stream. Background scans happen only below −70 dBm (40–120-ms holes per channel), and
  `nmcli dev wifi list` forces one.
- **What really happens "when connecting":**
  - **Two programs reading one board.** The board serves one client; a new one kicks out the old. Two readers (e.g.
    the Mac's recorder or SSD bridge, and the Pi bridge) take turns every ~1 s (`emg.py` RETRY_S 1), each losing
    about every other second. `selftest.py` avoids this only on the same machine.
  - **Bridge bug:** `_frame_times` grows while nobody watches (`server.py:99`, trimmed only at `:146`). The first
    viewer triggers the cleanup in the main loop: ~19 ms after 8 h on the Mac, 2–4× that on the Pi.
  - **First page load:** ~470 KB (later visits come from the cache).
- **Venue:** the event page puts AEII 2026 at HKCEC Hall 1D, 19–20 Nov. Its free Wi-Fi has a login page, which the
  ESP32s can't pass: the kit needs its own network.

## Quick check first (~25 min, MyoWare on the bench, nothing flashed)
1. Exactly one program reads the board; stop the others.
2. On the Pi, in the background: `iw dev wlan0 link`, `iw dev wlan0 get power_save`, `iw event -t`,
   `ping -D -i 0.2 <board IP>`.
3. Four 5-min recordings with Start/Stop:
   - A: no viewer (close the tab after Start);
   - B: Mac viewer on Wi-Fi;
   - C: Pi and viewer on cables;
   - D: iPhone viewer, 5 reloads 10 s apart.
4. From `emg.csv` and the board's status lines: pauses per minute, held vs never produced, size of the first chunk
   after a pause, `link_clients`, `link_dropped`, `rssi_dbm`; line them up with the ping log.

**What the results mean:**

| Result | Cause | Fixes |
|---|---|---|
| `link_clients` climbs | two readers | 1 |
| A ≈ B ≈ C, ping fine, data held | resend timer | 7, 13, 14 |
| A ≈ B ≈ C, ping drops too | link outage | 4, 5, 10–12 |
| B worse than A, C clean | dashboard traffic | 2, 6, 8 |
| hitches only after a reload | page load | 8 (gzip) |
| 524-ms pattern only with a Mac | the Mac's radio | 6, or another viewer |
| gaps in the board's own clock | the board, not Wi-Fi | battery, wiring |

## The fixes (all judged viable)

**Now: no hardware, no uploads**

| # | Fix | Effort |
|---|---|---|
| 1 | One reader per board. The bridge warns "another computer is reading the MyoWare" when the board keeps closing the link right after connecting, and backs off. | ~1 h |
| 2 | `frame_dtype = "u8"`, `fps = 10`, `env_hz = 25` in `config.pi.toml`: ~5× less air traffic. Recordings unchanged (`radar.py:316` saves raw bytes). | 5 min |
| 3 | `_frame_times` as a bounded deque. | 2 lines |
| 4 | Pi: `nmcli connection modify <profile> 802-11-wireless.powersave 2`; USB 3 SSD unplugged during sessions; no `nmcli dev wifi list` while recording. Bluetooth off (`dtoverlay=disable-bt`) only if the Bluetooth fallback isn't needed. | 10 min |
| 5 | Placement: access point 1–2 m in front at chest height, on the sensor's side. Check the **lowest** RSSI during curls, not the average. | free |

**Dashboard and bridge software**

| # | Fix | Effort |
|---|---|---|
| 6 | Laptop viewer on a cable to the Pi (USB-C LAN adapter). Open it by the Pi's Ethernet IP, not `.local`. | free |
| 7 | Live charts drawn 0.3–1.5 s behind (adaptive), so pauses up to 1.5 s are invisible whatever the cause. Pitfalls: use the bridge's clock, not `Date.now`; add its own redraw loop; align the charts; no delay in replay. | ~1 day |
| 8 | After a stall, send only the newest radar frame per view, with `TCP_NOTSENT_LOWAT` 16 KB (only together). Add a radar `views = [...]` option, plus gzip and long caching for `/assets`. | ~1 day |
| 9 | Priority marks on the Pi. ESP32 sockets: `IP_TOS 0xB8`, then `SO_PRIORITY 6`. WebSocket sockets: `IP_TOS 0x20`. Helps only with queueing; works with a Pi access point or an OpenWrt router; unknown on an iPhone hotspot. | ~10 lines |

**Venue network (pick one)**

| # | Fix | Cost |
|---|---|---|
| 10 | The Pi as a 2.4-GHz access point with the boards' existing Wi-Fi name and password, so no re-flash. One hop, no venue isolation. Quietest of channels 1/6/11, fixed sensor IPs, viewer on a cable to the Pi. Needs a 1-h test; 6–10 clients; never run a phone hotspot with the same name at the same time. | free |
| 11 | Travel router (e.g. GL.iNet Opal GL-SFT1200, ~1,400–1,900 THB, estimate) with the same name and password. Pi on its LAN port, viewers on 5 GHz or a cable, fixed 20-MHz channel, 802.11b rates off. The most robust. | ~1,500 THB |
| 12 | iPhone hotspot ("Maximize Compatibility"), with the iPhone itself as the viewer (one hop). No cable option; working on roaming in Hong Kong is unverified. Last resort. | free |

**Firmware (each upload needs the user's OK; 13 and 14 can share one upload)**

| # | Fix | Effort |
|---|---|---|
| 13 | `# status` adds the longest `write()` block and the buffer's high-water mark (≥1 s = resend timer; 0 = link). Plus `IP_TOS 0x80` (video queue, keeps aggregation). | ~15 lines |
| 14 | Resumable stream: keep buffering with no client, number the bytes, the client resumes "from N". The bridge can then reconnect after ~2 s instead of 6 without losing anything. Fixes the only real data loss. | 1–2 days |

**After the competition**
- 15. UDP with sequence numbers and resend requests from a ring: no 1-s floor. 3–5 days, medium risk.
- 16. ESP-NOW to a third ESP32 on the Pi's USB (CP2102 or native USB, not CH340): no access point at all. 3–5 days,
  last resort.

## Rejected in the review
- Rebuilding the ESP32 libraries to shorten the resend timer (too risky before the deadline).
- UDP that only repeats earlier batches (covers bursts of ≤40 ms).
- Fixed Wi-Fi rate, 802.11b only, more transmit power (already ~19.5 dBm), a bigger buffer (no PSRAM, ~110 KB
  largest block), binary lines now.
- A 5-GHz access point on the Pi (the ESP32s are 2.4 GHz only); access point + client on one radio.
- DTIM 1 or WMM switches as fixes; BSSID lock except at venues with several access points.
- Per-viewer view subscription (breaks the lost-message counter; use 8's `views` instead); batching aux values (a
  protocol change; use `env_hz` instead).
- From my draft: "EF" marking (it lands in the video queue on Linux), "ACKs wait hundreds of ms behind dashboard
  data", "power save causes mid-stream pauses".

## Recommended for the competition (11 days)
1. Quick check.
2. Fixes 1–5 (an afternoon).
3. Fix 7, for a smooth demo whatever the cause.
4. Venue network: 10 or 11, with 6.
5. Firmware 13 + 14 in one upload, if the check shows stalls or losses.
6. 15–16 after the competition.

## Files touched (if all are chosen)
- `deploy/pi/config.pi.toml`, `pi-bridge/config.example.toml`: dtype, fps, env_hz.
- `pi-bridge/truerehab_bridge/server.py`: `_frame_times`, newest-frame queue, NOTSENT_LOWAT, priority marks.
- `pi-bridge/truerehab_bridge/providers/emg.py`: the two-reader warning, priority marks, resume, IDLE_S.
- `pi-bridge/truerehab_bridge/providers/radar.py` (`views`), `pi-bridge/truerehab_bridge/web.py` (gzip, cache).
- `frontend/src/components/TimeSeriesChart.tsx`, `frontend/src/state/SensorStore.ts`, `frontend/src/widgets/AuxWidget.tsx`:
  playout delay.
- `firmware/myoware_record/myoware_record.ino`, `sandbox/imu-mpu6050-oled/imu_mpu6050_oled/imu_mpu6050_oled.ino`,
  `recorder/rec/sources.py`: status, IP_TOS, resume.
- `deploy/pi/README.md`: Pi settings, access-point setup, one reader per board.

## Risks / needs OK
- ESP32 uploads (13, 14), the Pi's network settings (4, 10) and buying a router (11) are the user's call.
- 10 takes the Pi off its current Wi-Fi: set it up with a keyboard or Ethernet attached.
- 7 delays the live display by up to 1.5 s; recordings are unchanged.

## How we'll verify
- The quick check before and after: pauses per minute in each scenario.
- Bridge tests plus new ones for the newest-frame queue and the two-reader warning; check-i18n for new messages;
  frontend typecheck.
- A 1-hour run with both boards on the chosen venue network.
