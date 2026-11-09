# Report: the fixes before collecting data (must and should)

<!-- Filename: YYYY-MM-DD-HHMM-<slug>.md -->

**Date:** 2026-11-09 16:50 · **Result:** ✅ done (pushed on branch `claude/codebase-audit-diagram-786f9c`, not merged) ·
**Plan:** [plans/2026-11-09-before-data-collection.md](../plans/2026-11-09-before-data-collection.md), items 1-8

## Goal
The user approved "Must and should, also report back what did you change or fix". The findings are in the
[readiness report](2026-11-09-1630-data-collection-readiness.md).

## What changed

### Must fix
1. **A board restart no longer breaks a session's timing.**
   - `recorder/rec/session.py`:
     - new `device_runs()` splits the device clock wherever it goes back (the board restarted; a 32-bit wrap doesn't
       count);
     - `align_device_time()` lines up each run on its own (`_align_run`, the old fit, unchanged).
   - The model reads sEMG and IMU through the same function (`trnet/truth.py`), so it is fixed too.
   - `model/trnet/check.py`, new `_clock_report()`:
     - names each restart, with the time and how much is missing ("the board restarted 1 time(s), at 35 s (~2.0 s
       missing)");
     - fails a sensor whose aligned times sit more than 0.5 s from its arrival times.
2. **The right sync order everywhere.**
   - `recorder/record.py` (docstring and the on-screen prompt) now says: stand still for 5 s, then press `s` and do 3
     shrugs, then `space` at each rep start.
   - `recorder/README.md` steps 2-3 say the same, and why: the sync looks from 1 s before `s` to 10 s after it.
3. **Wi-Fi in every MyoWare instruction.**
   - `recorder/README.md`:
     - the diagram, now with the webcam;
     - the example command: `--emg tcp://truerehab-myoware.local:3334`;
     - "on the board since 7 Nov";
     - safety: battery and Wi-Fi.
   - `recorder/record.py`: the `--emg` help and the docstring example.
   - `model/README.md`: protocol step 5.
   - The safety warning in `model/trnet/check.py`.

### Should fix
4. **Names are refused.** `record.py` accepts only `S01`–`S999` or `TEST`, checked before any folder or file is
   written. The rule is `CODE_RE` in `rec/session.py`, and a test keeps it equal to the check's.
5. **The Mac stays awake.** `record.py` runs macOS `caffeinate -i -w <its own pid>` while recording; it ends with the
   recorder.
6. **A stopped camera no longer spins.** `rec/pose.py` has a new `read_frame()`. It naps 10 ms between failed reads,
   and after 3 s without a picture it raises, so the status line shows `pose ERROR` and the other sensors keep
   recording.
7. **Radar frame limit.** `rec/sources.py` `RadarSource.status()`:
   - in the last 2 minutes before the 65 535-frame limit (~18 min) it shows "N s of radar left";
   - at the limit it says "FINISHED … start a new session";
   - only when the recorder started the radar itself.
8. **The check reads the MyoWare's own counters.** `model/trnet/check.py` `_board_counters()`:
   - `skipped`, `link_dropped` and `link_send_fails` during the recording;
   - "another program connected to the MyoWare N time(s)" when `link_clients` grew by more than the recorder's own
     reconnects (Wi-Fi only).
   - The IMU's counters now also count only the recording; before, they counted since the board booted.

### Tests added (13)
- `recorder/tests/test_recorder.py`: a restart is lined up on its own; a wrap is not a restart; a name is refused
  before anything is written; the radar status before and at its frame limit.
- `recorder/tests/test_pose.py`: a few failed reads are waited out; a dead camera raises instead of spinning; reading
  stops with the recording.
- `model/tests/test_check.py`:
  - a MyoWare restart halfway is found and lined up;
  - another program on the MyoWare is named;
  - board counters count only the recording;
  - the two subject-code rules are equal.

### Map
The page "TrueRehab-RF System Map" (https://claude.ai/artifact/LY2VUitK2dgooDYfjaW4FD) is updated at the same link:
- this branch and the uncommitted changes;
- a 13th part, Repo checks (`scripts/`);
- 13 "fixed 9 Nov" flags, and the open findings of 9 Nov, for example "not for training yet" on the Pi bridge's
  recording arrow;
- chips for the files that differ from `main`.

The generator is still in this session's scratchpad; plan 2026-11-08 item 17 would put it in the repo.

## Verified by
- **The restart:**
  - in the alignment alone (60 s, a 2-s reboot, 60 s more), the error went from 14 s / 79 s to 10.0 ms in both runs,
    which is the constant delivery delay;
  - in a fake session through the real check, the sEMG times match the unbroken session (0 ms), and the check warns
    about the restart.
- **Real recordings unchanged:** all 9 real sensor files (Nov 4-5 IMU sessions) give identical aligned times before
  and after: 0 ns difference.
- **Dry run with keys, through `record.py` in a pseudo-terminal:**
  - setup: simulated radar, fake MyoWare (with Wi-Fi pauses), fake Wi-Fi IMU;
  - the new prompt shows; 2,696 radar frames, 0 missing; sEMG and IMU at full rate; 9 markers;
  - `caffeinate -i -w <recorder>` ran during the recording and was gone after it.
- **`bash scripts/check_all.sh` and `--clean`:** nothing failed in either; model 77 tests (+4), recorder 23 (+7),
  pi-bridge 67, every front-end check.
- **The check's tests on the real recordings** (linked in read-only): 14/14.

## Issues / not done
- Not tested: a real camera that stops (Claude's shell can't open the camera), and a real board restart. Both are
  covered by the tests above.
- Still before the first volunteer, from the plan:
  - the radar profile (don't mix);
  - the left/right test;
  - the IMU wiring, or recording without it;
  - a 5-min dress rehearsal with the real hardware;
  - one reader per board;
  - consent;
  - daily backups.
- Pi dashboard recordings are still not for training (markers saved as `x`, subject `KIT`/`U-0007`). Use `record.py`.

## Next
1. The decisions and the dress rehearsal with the real hardware (plan items 9-15).

**Uncommitted work:** none: committed on branch `claude/codebase-audit-diagram-786f9c` and pushed (2026-11-09).
