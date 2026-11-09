# Report: is the code ready for collecting data?

<!-- Filename: YYYY-MM-DD-HHMM-<slug>.md -->

**Date:** 2026-11-09 16:30 · **Result:** ⚠️ not yet: 3 must-fix problems, all small (fixed the same day, with the
should-fix items: [report](2026-11-09-1650-fixes-before-data-collection.md)) · **Plan:**
[plans/2026-11-09-before-data-collection.md](../plans/2026-11-09-before-data-collection.md) (items 1-8 done)

## Goal
The user asked: "Is there anything else to fix before collecting data? Go check the entire code base."

## What was checked
- **Everything a recording passes through:**
  - the recorder (`record.py`, `rec/session.py`, `rec/sources.py`, `rec/pose.py`);
  - the MyoWare firmware;
  - radar start/stop and the radar profiles;
  - the Pi bridge's recording;
  - the session check (`model/trnet/check.py`) and how the model reads sEMG, IMU and radar;
  - both recording protocols (`recorder/README.md`, `model/README.md`).
- **A board restart, simulated:** in `align_device_time` directly, and in a fake session run through the real
  session check.
- **A dry run of a recording day:**
  - `record.py` in a pseudo-terminal with the simulated radar, the fake MyoWare (Wi-Fi, a pause every 15 s) and a fake
    Wi-Fi IMU;
  - keys pressed in the protocol's order;
  - then `check_session.py` and `link_report.py`.

## Must fix before collecting
1. **A board restart breaks the timing of the whole session, and the check says ok.**
   - **Code:** `recorder/rec/session.py` `unwrap_u32` only undoes the 32-bit wrap. A restart sends the device clock
     back near 0, and `align_device_time` fits one line through both parts. `model/trnet/truth.py` `record_rows`
     does the same.
   - **Measured, alignment alone:** 60 s, a 2-s reboot, 60 s more. Errors are 14 s before the reboot and 79 s after;
     the same 60 s without a reboot is 10 ms off.
   - **Measured, fake session, one MyoWare restart halfway:** the sEMG times move 23 s (median) before it and 37 s
     after it, up to 59 s. The check still says "63187 samples at 1000 Hz, no gaps [ok]".
   - **Why it matters:** `check.py` `_device_rate` counts only forward jumps as gaps. The fatigue labels (sEMG median
     frequency per rep) would be computed on the wrong part of the session.
   - **How likely:** a MyoWare on battery with Wi-Fi bursts can brown out. The v0.3 report already saw the boards'
     own freezes and restarts.
2. **The recorder tells the operator the wrong order for the sync shrugs.**
   - `record.py` (docstring and on-screen prompt) and `recorder/README.md` say "3 quick shoulder shrugs and press s".
   - `trnet/sync.py` `shrug_window` searches from 1 s before `s` to 10 s after it. `model/README.md` has it right:
     press `s`, then shrug.
   - The prompt also never says to stand still for 5 s first.
3. **The MyoWare instructions still describe Bluetooth.**
   - `recorder/README.md` (diagram, the example `--emg /dev/cu.TrueRehab-MyoWare`, "Not compiled or run yet",
     "record over Bluetooth"); `record.py` `--emg` help; `model/README.md` step 5 ("battery + Bluetooth").
   - The safety warning in `model/trnet/check.py` (lines 134-135) says the same.
   - The board uses Wi-Fi since 7 Nov: `--emg tcp://truerehab-myoware.local:3334`.

## Should fix (cheap)
4. **The recorder accepts any short subject**, `^[A-Za-z0-9_-]{1,12}$`, so a first name passes. The check flags it
   only afterwards, when it's already in the folder name and `meta.json`.
5. **Nothing keeps the Mac awake** during a recording. On macOS the monotonic clock stops in sleep, and so does the
   data.
6. **A camera that stops makes the pose thread spin:** `rec/pose.py` 147-148 does `if not ok: continue` with no
   sleep and no error, competing with the radar thread.
7. **The radar stops after 65 535 frames** (~18 min at 60 fps). Only the status line's "0 fps" would show it.
8. **The session check ignores the MyoWare's own status counters** (`skipped`, `link_dropped`, `link_clients`). It
   reads the IMU's. `link_report.py` covers the Wi-Fi side; until then, run both after each recording.

## Decisions and checks before the first volunteer
- **Radar profile:** record with the current `fullmap_awr2x44p.cfg` (5.94 cm, 3.8 m), or first test the finer
  profile on the board. Don't mix the two in one dataset.
- **Left/right test** with a still metal object (not done yet).
- **IMU:** fix the wiring (179 I²C errors on the arm on 5 Nov), or record without it; the webcam gives the angles.
- **Dress rehearsal with the real hardware**, 5 minutes, not worn: radar, MyoWare, the webcam started from the Terminal
  app (Claude's shell can't open the camera), IMU if used. Then `check_session.py` and `link_report.py`.
  - Webcam pose has never been recorded together with the radar. MediaPipe, 60-fps radar parsing and 1-kHz sEMG in one
    Python process is untested for dropped radar frames.
- **One reader per board.**
  - The MyoWare serves one client: a Pi bridge with sEMG on would take turns with the recorder, and both lose data.
  - Never run radar-lab next to the recorder.
- **Volunteers:** written consent; raw video only with written consent (off by default); healthy volunteers only. The
  ethics question is still open in CONTEXT.
- **Backups:** copy `recorder/data/sessions/` to the SSD after each day.
- **Optional:** upload the v0.3 MyoWare firmware (better Wi-Fi diagnostics; compiled, not uploaded; needs your OK).

## What's fine
- **The dry run's recording chain (45 s):**
  - radar (simulated) 2,696 frames, 0 missing, 60 fps;
  - sEMG ~1,000 lines/s and IMU 200/s over Wi-Fi, no errors, no link drops;
  - all 9 key presses saved.
- **The check:** read both ground-truth sensors and found 8 reps matching the 8 `space` presses.
- **The link report:** found the fake's two 1.1-s Wi-Fi pauses and called them "held, nothing lost".
- **Session files:**
  - `meta.json` is written atomically; markers are flushed at once; data is flushed every 0.5 s;
  - a sensor that fails shows ERROR and the others keep recording;
  - Wi-Fi sensors reconnect and mark the gap.
- **Privacy defaults:** raw video off; the check flags names and saved video.
- **Space:** a session is ~15 MB per minute; 584 GB free.

## Not covered
- The radar part of the dry run. The model needs the static-heatmap and range-Doppler parts of each frame, which the
  simulator doesn't produce, so the check said "no frames could be read". Real recordings are read fine.
- The camera: Claude's shell can't open it.
- Firmware builds. Phisit and the dashboard aren't part of data collection.

## Next
1. Your OK on the plan: the 3 must-fix items (~2 h), and the cheap should-fix items if you want them (~2 h).
2. Then the decisions and the dress rehearsal with the real hardware, before the first volunteer.

**Uncommitted work:** none: committed on branch `claude/codebase-audit-diagram-786f9c` and pushed (2026-11-09). This
review changed no code; the fixes are in the [fixes report](2026-11-09-1650-fixes-before-data-collection.md).
