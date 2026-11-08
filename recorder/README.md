# recorder — radar + sEMG + IMU on one clock

Records training sessions: every radar frame and every ground-truth sample gets a timestamp from the
same Mac clock, so they can be lined up afterwards. Plan: [`CLAUDE/plans/2026-11-04-recorder.md`](../CLAUDE/plans/2026-11-04-recorder.md).

```
AWR2944PEVM (USB, 60 fps) ──┐
MyoWare sEMG (Bluetooth) ───┼─► record.py ─► data/sessions/<date>_<time>_<subject>_<exercise>/
MPU6050 IMU (optional) ─────┘        ▲                meta.json, radar.bin, radar_index.csv,
           keys: rep, tired, ... ────┘                emg.csv, imu.csv, markers.csv
```

Recordings stay on this Mac: `data/` is git-ignored. Use subject **codes** (S01), never names.

## Record a session

```bash
cd recorder
```

```bash
.venv/bin/python record.py --subject S01 --exercise elbow_flexion --radar-data /dev/cu.usbmodemRA29P0554 --radar-cli /dev/cu.usbmodemRA29P0551 --emg /dev/cu.TrueRehab-MyoWare
```

1. The recorder starts the radar at 60 fps (it keeps the radar's command port open and stops the radar at the end).
2. **Start with 3 quick shoulder shrugs and press `s`.** All sensors see them, so their offsets can be checked.
3. Keys: `space` rep start · `s` sync shrugs · `t` feels tired · `c` compensating · `x` note · `q` stop.
4. The status line shows each sensor's rate. A sensor that stops shows `0/s` or `ERROR`.

Without hardware: `.venv/bin/python record.py --subject TEST --exercise demo --radar-sim --duration 10`

Radar limits (from radar-lab): one run is at most 65 535 frames (~18 min at 60 fps). If the radar's command
port doesn't answer, press the board's reset button and start again.

## MyoWare: use the record sketch

Upload [`firmware/myoware_record/myoware_record.ino`](../firmware/myoware_record/myoware_record.ino) (Arduino IDE,
board "ESP32 Dev Module"). It sends `E,<micros>,<raw>,<env>` at 1 kHz with the ESP32's own clock, so the
recorder removes Bluetooth jitter. RAW is what fatigue analysis (median frequency) needs; the demo sketch only
sends the envelope 50×/s. Set `USE_IMU 1` and the I2C pins to add the MPU6050 as `I,<micros>,ax,ay,az,gx,gy,gz` at 200 Hz.
**Not compiled or run yet.** Safety: no USB cable while the sensor is on a person; record over Bluetooth.

The demo sketch still records (lines saved as received), just without device timestamps.

## IMU: dedicated ESP32 board

[`sandbox/imu-mpu6050-oled/`](../sandbox/imu-mpu6050-oled/README.md) with `RECORD_MODE 1` sends the same
`I,<micros>,ax,ay,az,gx,gy,gz` line at 200 Hz / 921600 baud (16384 per g, 131 per °/s, raw), plus `#` header and
status lines. Add `--imu /dev/cu.usbserial-0001`; read back with `s.record_mode("imu", "I")`. Its chip is an
MPU-6500-family clone (WHO_AM_I 0x74), which the record sketch's IMU path now accepts too.

**Over Wi-Fi** (firmware built with `WIFI_LINK 1`, see the IMU README): `--imu tcp://truerehab-imu.local:3333`.
The recorder reads it with a plain TCP socket. If the link closes or is quiet for 6 s, the recorder reconnects
once a second and writes `# recorder: link lost (...)` / `# recorder: link back` rows into `imu.csv`; the readers
skip them. While it's down the status line shows `imu RECONNECTING`; the summary counts `link_drops`.
The name is looked up over IPv4: macOS otherwise waits 5 s for an IPv6 address the board doesn't have.

**Device clock → host clock** (`align_device_time`, used by `record_mode()`):
- The slope (clock drift) is fitted through the least-delayed sample of every 2-s window: the lower edge of
  the arrival times.
- The offset comes from that edge.
- Fitting through all samples would let delay bursts tilt the result. Wi-Fi pauses for ~1 s now and then and
  delivers the backlog at once, and Bluetooth arrives in bursts. On a real 2-min Wi-Fi recording, the old fit
  wandered 37 ms against the USB copy; the edge fit stayed a constant 4.1 ms apart.
- Recordings shorter than ~6 s fall back to the old fit.

## Video pose (ground truth only)

A camera + MediaPipe Pose gives 33 body points per frame (image position and 3D metres) → `pose.csv`.
The product stays camera-free; this only labels training data. Raw video is **not** kept unless `--save-video`.

One-time setup (done on this Mac): `mediapipe` in `.venv`, and the 9.4 MB model `models/pose_landmarker_full.task`
from `storage.googleapis.com/mediapipe-models` (git-ignored; sha256 `4eaa5eb7…cdec4ad`).

**Camera permission first.** If `--list` prints "not authorized to capture video", the app that started Python has
no camera permission and macOS can't ask for it. Run the command from the Terminal app and click Allow, or turn
the app on in System Settings > Privacy & Security > Camera. On this Mac, camera 0 is the MacBook webcam
(1920×1080, ~32 fps); camera 1 (~11 fps) is probably the iPhone.

```bash
.venv/bin/python pose_check.py --list
```

```bash
.venv/bin/python pose_check.py --camera 0
```

The preview draws the skeleton with elbow angles, trunk lean and ear-to-shoulder gap (shrinks in a shrug), plus fps
(`q` quits). Then add `--camera N` to `record.py`. For the iPhone (Continuity Camera): turn off Center Stage,
Portrait, Studio Light and Desk View, tripod in landscape, same spot every session. Front view shows shoulder
elevation and sideways lean; side view shows forward lean and the elbow angle.

Read back: `p = s.pose()` → `t_s`, `person`, `image [n,33,4]`, `world [n,33,3]`; `rec.pose.angles(p["world"])`.

## Read a session back

```python
from rec import session
s = session.load("data/sessions/2026-11-04_183553_S01_elbow_flexion")
idx = s.radar_index()               # frame_no, t_s, offset, length
for t, frame in s.radar_frames():   # parsed with radar-lab's reader
    ...
emg = s.record_mode("emg", "E")     # t_s on the host clock, values[:, 0] raw, [:, 1] env
s.markers                           # (t_s, key, label)
```

## Wi-Fi link report

How often a Wi-Fi sensor's data paused in a recording, and why (recorder or Pi bridge sessions; pure Python):

```bash
.venv/bin/python link_report.py data/sessions/<A> data/sessions/<B>
```

- **held:** the board kept sampling and all of it arrived late (the network held it back). A tiny first chunk after the
  pause means the ESP32's TCP resend timer ended it (it waits 1-2 s after a short radio blackout).
- **not sent:** the board's own clock jumps too (it froze, restarted or its buffer was full).
- Also: how late chunks arrive, a regular delay every 0.52 s (a Mac's AirDrop/Handoff radio on the receiving side), link
  drops, another program reading the board, signal strength, and the MyoWare's `link_stall_ms` / `link_buf_max`.
- Several sessions: a comparison table at the end. On the Nov 5 bench session it finds the two ~1.1-s pauses (both ended
  by the resend timer) and the Mac's 0.52-s pattern.

## Files

- `record.py` — the recorder (status line, keys, starts/stops the radar)
- `rec/session.py` — session folder writer, reader, device-clock alignment
- `rec/sources.py` — radar and serial-line sensors, one thread each
- `rec/pose.py` — camera + MediaPipe source, joint angles
- `pose_check.py` — camera list and live skeleton preview
- `link_report.py` — Wi-Fi pauses in a recording, and why
- `rec/radar_lab.py` — uses `radar-lab/` (frame reader, configs, radar commands) without copying it
- `tests/` — `.venv/bin/python -m unittest discover tests` (simulated radar + a fake MyoWare)

## Verified

- Real radar, Nov 4: 15 s (919 frames), 10 s (619) and 4 s (254) sessions at 60 fps, 0 missing; the radar stops
  cleanly and the next session starts without a reset; sessions read back (60.0 fps, all TLVs).
- Tests: simulated radar + fake MyoWare on a pseudo-terminal (every sample kept, device clock unwrapped and aligned);
  a fake Wi-Fi IMU on localhost. The fake closes the link once and goes silent once: both are reconnected, every
  whole line is kept exactly once, no half line is glued to the next, and both outages show as gaps on the aligned
  timeline. An unreachable board fails before recording starts.
- IMU board with its real sensor, Nov 4 (`--imu`, RECORD_MODE 1, OLED running): 40 s, 8032 samples, 200.00 Hz, steps
  4999–5001 µs, no gaps, 0 I2C errors. Found and fixed on the way: on this Mac a serial port replays one stale line ~50 times when it opens
  (the last copy spliced onto a new line). `SerialLineSource` now discards what arrives in the first 50 ms, and
  `record_mode()` drops rows that repeat the previous device time.
- IMU board over Wi-Fi, Nov 5 (`--imu tcp://truerehab-imu.local:3333`, the board's USB output recorded alongside):
  - 2 min at 200.0 Hz. Every sample present in both copies is identical, and the board dropped nothing.
  - A forced reconnect at 40 s cost one 1.0-s gap.
  - Aligned times: Wi-Fi vs USB a constant 4.1 ms apart (spread < 0.01 ms).
  - Details: the IMU README's "Verified".
- Video pose on the MacBook webcam, Nov 4 (`pose_check.py --camera 0`, 1920×1080 ~32 fps): skeleton tracked; elbow
  angle, shrug (ear–shoulder gap) and trunk lean responded as expected. This was checked by eye in the live preview,
  not measured against a goniometer.

## Not done yet

- Video pose inside `record.py` alongside the radar: not recorded together yet. iPhone camera: only ~11 fps in the
  list check; it needs to be on a stand and reach ~30 fps before it is used.
- MyoWare record sketch: not run on hardware yet.
- IMU board on a moving arm: not recorded yet. Its wiring dropped out when the board moved on Nov 4 (see the IMU README).
