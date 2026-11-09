# Report: the bridge restarts the radar at its frame limit, and keeps counting frames (fix F1)

<!-- Filename: YYYY-MM-DD-HHMM-<slug>.md -->

**Date:** 2026-11-09 19:55 · **Result:** ✅ done (committed as `33ae848`, not pushed; not yet run on the board) ·
**Plan:** [plans/2026-11-09-aeii-demo-day.md](../plans/2026-11-09-aeii-demo-day.md), item F1 (approved by the user:
"sure")

## Goal
The radar stops by itself after 65,535 frames (about 18 min at 60 fps); a count of 0 crashes this board.
- **Before:** the Pi bridge waited 3 s, said "No frames for 3 s. Check the cables…", and its supervisor restarted the
  reader. A booth demo would show that message about three times an hour.

## What changed
In `pi-bridge/truerehab_bridge/providers/radar.py`:
1. **Restart in place.** After the radar's last second of frames and a quarter of a second of quiet, the bridge sends
   the profile again on the command port that is still open (`_restart_in_place`). The profile begins with
   `sensorStop` and ends with `sensorStart`: the same lines as every start. It never closes the port, because
   closing it is what makes this board's port go silent until a reset.
2. **Frame numbers count on across every restart** (`_continue_numbering`), in the packet header too.
   - After a restart the next number is the last one plus the frames the pause would have held.
   - **Found while doing this:** before, every restart (also the supervisor's after an error) began a recording's
     numbers again near 1. The model's `load_radar` sorts frames by number and drops repeated numbers, so it would
     have mixed or dropped the second run.
   - Now a recording never jumps back, `frame_no × period` stays a clock, and the pause shows as missing frames.
3. **Plain messages.**
   - During the restart, the health line says "restarting: it sent all its frames (18-min limit)…".
   - Afterwards it says "restarted N× at its 18-min frame limit".
   - If another program started the radar, the bridge says that the radar sent all its frames and that program
     has to start it again.
   - Quiet in the middle of a run still says "Check the cables".
4. **The limits are named once:** `FRAME_LIMIT`, `END_SILENCE_S`, `NO_FRAMES_S`.

Like the rest of the radar's health line, the new parts are English only: the dashboard translates only messages that
are in its catalog, and it doesn't split the radar's comma-joined line.

## Tests (5 new, in `pi-bridge/tests/test_radar_provider.py`; fake ports, no radar, no pyserial)
- It starts the radar again at the limit and counts on, in the packet header too.
- It counts on when the bridge starts the radar again after an error.
- It says why when another program started the radar.
- Quiet in the middle of a run is still "the cables".
- **End to end:**
  - it records 120 real-looking frames (from a fake session) across a restart;
  - the frame numbers never go back;
  - the pause shows as missing frames in `meta.json`;
  - the model's own `load_radar` keeps all 120 frames on one clock.

## Verified by
- `bash scripts/check_all.sh`: nothing failed; pi-bridge 72 tests (was 67).
- `--clean --only pi-bridge`: 72 tests pass on a clean copy.
- **Clean set built after the commit:** `truerehab-pi-0.3.0-20261109-33ae848.tar.gz` (git-ignored `deploy/pi/dist/`).
  - Its checksum matches, `VERSION.json` says `33ae848`, not modified, and the fix is inside.
  - Its tests pass from the unpacked copy: bridge 72 (14 need `websockets`), recorder 23, radar-lab 6, model 9.
- **One recorder test failed once.** It was the first run on the unpacked set, right after the build. It didn't
  happen again in 69 more runs, including 63 under load. Its output wasn't saved, so which test it was is
  unknown. No recorder code changed today after the checks passed.

## Not done
- **Not run on the board.** The real check is the 25-min hands-off run, step A2 of the demo-day plan: the frames
  should come back within a second or two at about 18 min.
- **Not pushed.** The branch is ahead of GitHub until you push.
- The Mac recorder (`record.py`) still stops at the limit and says "FINISHED … start a new session"; that is
  intended (one session per recording).

**Uncommitted work:** none: the fix is `33ae848`, and the notes are the commit after it (not pushed).
