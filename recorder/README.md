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

## Video pose (ground truth only)

A camera + MediaPipe Pose gives 33 body points per frame (image position and 3D metres) → `pose.csv`.
The product stays camera-free; this only labels training data. Raw video is **not** kept unless `--save-video`.

One-time setup (done on this Mac): `mediapipe` in `.venv`, and the 9.4 MB model `models/pose_landmarker_full.task`
from `storage.googleapis.com/mediapipe-models` (git-ignored; sha256 `4eaa5eb7…cdec4ad`).

**Run these from the Terminal app.** macOS asks there for camera permission once (click Allow); it can't ask
a background process, so the camera stays blocked when started from elsewhere.

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

## Files

- `record.py` — the recorder (status line, keys, starts/stops the radar)
- `rec/session.py` — session folder writer, reader, device-clock alignment
- `rec/sources.py` — radar and serial-line sensors, one thread each
- `rec/pose.py` — camera + MediaPipe source, joint angles
- `pose_check.py` — camera list and live skeleton preview
- `rec/radar_lab.py` — uses `radar-lab/` (frame reader, configs, radar commands) without copying it
- `tests/` — `.venv/bin/python -m unittest discover tests` (simulated radar + a fake MyoWare)

## Verified

- Real radar, Nov 4: 15 s (919 frames), 10 s (619) and 4 s (254) sessions at 60 fps, 0 missing; the radar stops
  cleanly and the next session starts without a reset; sessions read back (60.0 fps, all TLVs).
- Tests: simulated radar + fake MyoWare on a pseudo-terminal (every sample kept, device clock unwrapped and aligned).

## Not done yet

- Video pose on a real camera: built and tested in code (MediaPipe runs, 6 ms/frame), but no camera picture yet
  (needs camera permission in Terminal).
- MPU6050 and the record sketch: untested on hardware.
