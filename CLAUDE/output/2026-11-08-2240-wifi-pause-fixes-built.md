# Report: Wi-Fi pause fixes built without the Pi (Pi set v0.3)

**Date:** 2026-11-08 22:40 · **Result:** ⚠️ partial: everything that needs no Pi is built and tested; the Pi-side
steps and the board upload wait for tomorrow's test · **Plan:** [plans/2026-11-08-wifi-drop-fixes.md](../plans/2026-11-08-wifi-drop-fixes.md)

## Goal
The user: "can you build it with no pi? and we can test it tomorrow", about the fix menu for the temporary 2.4-GHz
drops (fixes 1–3, 7, the docs for 4–6 and 10–12, firmware 13, and a way to measure the result).

## What changed (uncommitted)
- **Bridge (`pi-bridge/`):**
  - `providers/emg.py`:
    - **Another reader:** the board serves one client and drops the old one for a new one. When its `link_clients`
      jumps by 2 or more between our links, another program is on it. The bridge then waits 5, 15, 30, 60 s before
      taking it back, and the health line says "Another program is reading the MyoWare…".
    - **Wi-Fi pauses:** a gap of 0.3 s or more with no samples missing (the network held the data back) is counted
      in the health line ("N Wi-Fi pause(s) in 5 min, longest X s"), logged, and summed in `meta.json`
      (`wifi_pauses`, `longest_pause_s`).
  - `server.py`: `_frame_times` is a deque trimmed as frames come. It used to grow ~7 MB/h while nobody watched,
    and the first viewer paid for the clean-up.
  - `fake_myoware.py --pause-every S [--pause-s 1.1]`: holds its data back like the real board's pauses.
- **Config** (`deploy/pi/config.pi.toml`, `pi-bridge/config.example.toml`): `frame_dtype = "u8"`, radar `fps = 10`,
  `env_hz = 25`. The dashboard stream is ~5× lighter on the air; recordings unchanged.
- **Dashboard (`frontend/`):**
  - `src/state/PlayoutClock.ts` (new), `SensorStore`, `SensorContext`, `TimeSeriesChart`, `AuxWidget`: on a live
    source the reference-signal charts end slightly behind the Pi's clock and keep moving (redrawn ~30/s).
    - The delay is 0.25 s on a clean link and up to 1.5 s after a pause, and it changes gradually.
    - The Pi's clock is estimated from arrivals (no time sync needed).
    - Replays keep their own playhead; a manual disconnect stops the scrolling.
  - Two new messages in EN/TH/zh-HK.
  - `scripts/check-playout.ts` (new).
  - `mock-server/server.ts`: `PAUSE_EVERY` / `PAUSE_S`; launch config `mock-bridge-pauses` (port 8766).
- **Firmware** `firmware/myoware_record/myoware_record.ino` (compiled, NOT uploaded):
  - the status line adds `link_stall_ms` (the longest send of the last ~5 s) and `link_buf_max` (the fullest
    buffer since the last status line);
  - the board's packets are marked CS4 (Wi-Fi "video" queue, still aggregated).
- **`recorder/link_report.py`** (new): per session, the pauses ≥ 0.2 s and their cause:
  - held by the network, and whether a tiny first chunk shows the ESP32's resend timer;
  - not sent by the board;
  - how late chunks arrive, the Mac's 0.52-s AWDL pattern, link drops, other readers, RSSI, the new board numbers;
  - several sessions: a comparison table.
- **Docs:**
  - `deploy/pi/README.md` (v0.3), "Wi-Fi: smooth live data":
    - one reader per board;
    - Pi power save off;
    - SSD unplugged and no scans during sessions;
    - placement;
    - laptop on a cable (`ipv4.method shared`, `http://10.42.0.1:8080`);
    - venue network (Pi access point with the boards' Wi-Fi name, `--ask` for the password; travel router; iPhone);
    - the 25-min A/B/C/D check.
  - The bridge, recorder and dashboard READMEs.
- **Pi set:** `deploy/pi/dist/truerehab-pi-0.3.0-20261108-3eb5887-modified.tar.gz` (105 files, sha256 `12443bc4…`).
  It lacks `recorder/link_report.py`, because the builder takes only git-tracked files.

## Verified by
- **Bridge tests:** 48 pass with the Mac's Python (5 skipped: they need websockets), incl. 3 new sEMG tests:
  - held vs lost samples;
  - a second program taking the board twice → the warning and a 5-s wait, no fighting;
  - a live 1.1-s pause from the fake board.
- **Recorder tests:** 16 pass (recorder venv), incl. 2 new `link_report` tests.
- **`link_report.py` on the Nov 5 bench session:** 2 held pauses (1.18 s, 1.06 s), both ended by a 1–4-sample
  chunk (the resend timer); the forced takeover at 40 s; the Mac's 0.52-s pattern (98 % on the beat). On the curls
  session: all 20 pauses "not sent" (the IMU froze). Both match the devil's-advocate review.
- **Dashboard:**
  - `check-playout.ts` 11/11;
  - typecheck;
  - check-i18n (514 pairs);
  - build (JS 359 KB).
- **Browser (mock bridge, 1.1-s aux pause every 10 s):**
  - the delay settled at 1.27 s;
  - with a normal frame rate the chart redrew at least every 48 ms through a 1.17-s pause, never showed the same
    image twice, and its edge moved 86–114 ms per 100 ms;
  - no gaps in the screenshot, no console errors.
  - Caveat: the Browser pane was hidden, which slows animation frames to ~6/s. I replaced them with a 16-ms timer in
    that page for the measurement; not yet seen in a visible window.
- **Firmware:** both builds compile (Wi-Fi 73 % flash, Bluetooth 83 %; only the old BluetoothSerial deprecation
  warning).
- **Bundle:** Python 3.11 syntax check passed; the new code and the settings are inside.

## Issues / not done
- **Not tested on a Pi or with the real board:** the playout delay, the warnings, the Pi network commands (power
  save, laptop cable, access point) and the firmware.
- **The websockets-based bridge tests and `check_bridge.py`** weren't run: the PortableSSD (their venv) isn't
  plugged in.
- **The Wi-Fi firmware build folder** (`scratchpad/build-myo-wifi`) still holds the compiled Wi-Fi password: my
  delete was held by a safety check while you were away. It needs your OK.
- **Mock-only side effect:** the mock's pause mode raises "Messages lost" (held messages keep their sequence
  numbers). The real bridge numbers messages when it sends them.
- **Not built:**
  - 8 (newest-frame queue, NOTSENT_LOWAT, gzip);
  - 9 (priority marks on the Pi);
  - 14 (resumable stream: only if the check shows lost data);
  - 15–16.

## Next
1. Commit (then rebuild the set so it includes `link_report.py`), copy it to the Pi, `bash install.sh`, and run the
   Wi-Fi check from `deploy/pi/README.md` with the MyoWare on the bench.
2. Upload the MyoWare firmware (needs your OK; board on USB, nobody wearing it) to get `link_stall_ms` /
   `link_buf_max`.
3. Pick the venue network (Pi access point or travel router) and test it for an hour at home.

**Uncommitted work:** yes. All of the above plus the earlier plan and CONTEXT edits.
