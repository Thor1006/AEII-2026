# Plan: fixes before collecting data

<!-- Filename: YYYY-MM-DD-<slug>.md -->

**Status:** done for items 1-8 (2026-11-09, [report](../output/2026-11-09-1650-fixes-before-data-collection.md); approved by the user: "Must and should, also report back what did you change or fix"). Items 9-15 are decisions and checks for you, before the first volunteer.
**Date:** 2026-11-09

## Why
The user asked: "Is there anything else to fix before collecting data? Go check the entire code base." The review
and the evidence are in the [report](../output/2026-11-09-1630-data-collection-readiness.md).

Three problems would spoil or mislabel real recordings without anyone noticing:
1. **A sensor board that restarts mid-session breaks the timing of the whole session.**
   - If the MyoWare or IMU restarts (battery dip, brown-out, watchdog), its clock starts again near 0.
   - `align_device_time` then fits one straight line through both parts. On a fake session, one restart moved every
     sEMG timestamp by 23 s (median) before it and 37 s after it.
   - The session check still says "1000 Hz, no gaps, ok".
2. **The recorder tells the operator the wrong order for the sync shrugs.**
   - Its prompt and `recorder/README.md` say "3 quick shoulder shrugs and press s".
   - The sync only looks from 1 s before `s` to 10 s after it, so shrugs done first are missed.
   - `model/README.md` has the right order: press `s`, then shrug.
3. **The MyoWare instructions still describe Bluetooth.** The README example command uses `/dev/cu.TrueRehab-MyoWare`
   and says to "record over Bluetooth". The board uses Wi-Fi since 7 Nov:
   `--emg tcp://truerehab-myoware.local:3334`.

## Approach

### Must fix (~2 h)
1. **Clock alignment survives a restart:**
   - in `recorder/rec/session.py`, split the device timeline wherever the clock goes back by more than a few ms
     without a 32-bit wrap (the board restarted), and align each piece on its own;
   - `model/trnet/truth.py` `record_rows` uses the same split (it repeats `record_mode`'s filters);
   - the session check reports each restart (warn), and fails a sensor whose aligned times sit seconds away from its
     arrival times.
   - Tests: the restart from the report, as a unit test and as a check test.
2. **The sync order is right everywhere:**
   - the recorder's on-screen prompt and docstring: "stand still 5 s, press s, then 3 quick shrugs; space at each rep";
   - `recorder/README.md` step 2.
3. **MyoWare over Wi-Fi in every instruction:**
   - `recorder/README.md`: the diagram, the example command, "Not compiled or run yet", "record over Bluetooth";
   - `record.py`: the `--emg` help and the docstring example;
   - `model/README.md` step 5: battery + Wi-Fi;
   - the safety warning in `model/trnet/check.py`.

### Should fix (~2 h, small and safe)
4. **The recorder refuses a subject that the check would flag.** Only `S01`–`S999` or `TEST`, so a name never reaches a
   folder name or `meta.json`.
5. **The recorder keeps the Mac awake** while recording: macOS `caffeinate -i -w <pid>`, which ends with the recorder.
6. **A camera that stops doesn't freeze the others.**
   - The pose thread sleeps between failed reads, instead of `continue` at full speed.
   - After 2 s of failures it shows `pose ERROR`.
7. **The status line warns before the radar's frame limit:** 65 535 frames is ~18 min at 60 fps. After that, the radar
   stops and only the line's "0 fps" shows it.
8. **The session check reads the MyoWare's own counters**, as it already does for the IMU: `skipped`, `link_dropped`,
   and "another program read the board" (`link_clients` jumps).

### Decisions and checks before the first volunteer (not code)
9. **Radar profile:** record with `fullmap_awr2x44p.cfg` (5.94 cm, 3.8 m) or first test the finer profile and switch.
   Don't mix the two in one dataset.
10. **Left/right test** with a still metal object (10 min), so the recorded angle axis can be read.
11. **IMU:** fix its wiring (179 I²C errors on the arm on 5 Nov), or record without it. The webcam gives the angles.
12. **Dress rehearsal with the real hardware**, 5 min: radar, MyoWare (not worn), webcam started from the Terminal app,
    IMU if used. Then `check_session.py` and `link_report.py`. This tests what no simulation can:
    - radar, MediaPipe and 1-kHz sEMG together in one process (never recorded together yet);
    - 0 missing frames;
    - pose fps.
13. **One reader per board:** turn off the Pi bridge's sEMG (or the Pi) while recording on the Mac, and never run
    radar-lab next to the recorder.
14. **Volunteers:** written consent; raw video only with written consent (it is off by default); healthy volunteers
    only.
15. **Back up** `recorder/data/sessions/` to the SSD after each day. It's git-ignored and exists only on this Mac.

### Not needed before collecting
- Point layers, frames per rep (T), freezing contract v1, label thresholds: decided on the recordings afterwards.
- Pi dashboard recordings aren't ready for training:
  - every marker is saved as `x`, not `s` or `space`;
  - the subject comes out as `KIT` or a `U-0007`-style code;
  - there is no IMU or pose.
  Use `record.py`.

## Files touched
- **Must:**
  - `recorder/rec/session.py`, `model/trnet/truth.py`, `model/trnet/check.py`;
  - `recorder/record.py`, `recorder/README.md`, `model/README.md`;
  - tests in `recorder/tests/` and `model/tests/`.
- **Should:** `recorder/record.py`, `recorder/rec/pose.py`, `recorder/rec/sources.py`, `model/trnet/check.py`, with
  tests.

## Risks / needs OK
- **#1 changes how every session's sEMG and IMU times are computed.** A session without a restart must come out
  exactly as before. Test: identical aligned times on the real Nov 4–5 recordings, before and after.
- **#4 rejects subjects like `U-0007`** in the Mac recorder; the Pi bridge keeps its own rules.
- **#5 runs `caffeinate`**, a built-in macOS tool. Nothing is installed.
- Nothing flashes firmware or changes a radar profile.

## How we'll verify
- `bash scripts/check_all.sh` and `--clean` stay green.
- The restart session from the report is aligned within normal error, and the check names the restart.
- The real recordings give the same aligned times as before the change.
- The dry run again: simulated radar, fake MyoWare and fake IMU through `record.py` in a pseudo-terminal, then
  `check_session.py` and `link_report.py`.
