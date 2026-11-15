# Report: A checksum for every recording (and the 5-person training)

**Date:** 2026-11-15 11:51 · **Result:** ✅ done · **Plan:** [2026-11-15-recording-checksums](../plans/2026-11-15-recording-checksums.md)

## Goal
Make "did a file get corrupted?" answerable: each session folder carries a SHA-256 fingerprint of every file.

## Before this: the 14 Nov data and training (run the night of 14 Nov)
- 4 new sessions from a 5th person (30 IMU reps each). All pass the check. `052208` has 208 missing radar frames
  (longest gap 3.1 s) and one 9471 °C temperature reading, which must be a bad value.
- Asked "any file corrupted?" on 15 Nov: every 14 Nov file was read in full by the check, the rep counter and
  training without errors. The SSD was unplugged, so nothing was re-checked, and no checksums existed then.
  `git fsck`: intact, apart from a Finder `.DS_Store` inside `.git/refs` (harmless).
- Rep counter (`runs/arm_2026-11-14_232602`): 653 radar vs 657 IMU reps over 23 sessions, 80 % found (chance 44 %).
  The new person, never used to tune it: 116 vs 120, 67 % found (chance 34 %).
- Training (`runs/2026-11-14_232558`, 5 people, 687 reps, a whole other person validates):
  - fatigue MAE 0.193 vs 0.217 for the mean, better for 3 of 5 people (one only slightly), worse for 1, tied for 1;
  - quality and reduced-ROM no better than the mean.
  - A hint, not proof. Codes shift as people are added (the new person is S01).

## What changed
- `recorder/rec/checksums.py` (new): `write`, `read`, `verify`. Hidden files (`.DS_Store`, `._*`) are skipped;
  writing is atomic.
- `recorder/rec/session.py`: `SessionWriter.close()` writes `checksums.sha256` last. This covers both the Mac recorder
  and the Pi bridge (both close the sensors first). A failure to write only prints a warning; the session is kept.
- `recorder/checksums.py` (new command): `add` (only where missing, never replaces) and `verify` (exits 1 on a
  changed or missing file).
- `model/trnet/check.py`: `files` line: `checksums ok (N files)`, a warning naming the changed or missing file, or
  `no checksum` (real sessions only). Nothing is refused.
- Tests: `recorder/tests/test_checksums.py` (4), 1 in `model/tests/test_check.py`, and an assertion in
  `pi-bridge/tests/test_radar_provider.py`. `test_recording.py` was left alone, because the Pi has uncommitted
  edits to it.
- `recorder/README.md` Checksums section; `model/README.md` note.

## Verified by
- `bash scripts/check_all.sh`: nothing failed (model 86, recorder 27, pi-bridge 72 tests).
- `pi-bridge`: the radar recording test ran (not skipped), and the folder's checksums verify.
- A 5-s `record.py --radar-sim` recording: macOS `shasum -a 256 -c checksums.sha256` gives OK for all 4 files.
  After one byte of a copy's `radar.bin` was changed, `checksums.py verify` exits 1 and names `radar.bin`, and so
  does `check_session.py`.

## Issues / not done
- The 30 existing SSD sessions have no checksums. `checksums.py add` was not run (SSD unplugged; needs your OK).
- The Pi only gets this with the next Pi set, which waits for its uncommitted IMU work to be committed.
- If a sensor thread doesn't stop within 3 s, it could still write after hashing; `verify` would then report the
  file as changed (honest, not hidden).

## Next
1. SSD plugged in: `recorder/.venv/bin/python recorder/checksums.py add /Volumes/PortableSSD/truerehab-sessions`
   (asks first), then `verify` after every copy.

**Uncommitted work:** yes
