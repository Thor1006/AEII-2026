# Report: Phase 1, tests that give the same answer on any computer

<!-- Filename: YYYY-MM-DD-HHMM-<slug>.md -->

**Date:** 2026-11-09 15:25 · **Result:** ✅ done (pushed on branch `claude/codebase-audit-diagram-786f9c`, not merged) ·
**Plan:** [plans/2026-11-08-codebase-optimization.md](../plans/2026-11-08-codebase-optimization.md), Phase 1

## Goal
The user approved Phase 1 ("Yes, Phase 1"). It covers:
- the 3 tests that passed only on this Mac;
- one command for every check;
- a faster slow test.

## What changed
- **`model/tests/test_synth.py`:**
  - the reps-and-delays test gets its own 3 fake sessions with the saved-statistics radar background, so they are
    identical on every computer;
  - its webcam-delay limit is one webcam frame (1000 / fps = 33 ms) instead of 15 ms.
- **`model/tests/test_dataset_train.py`:** `test_overfits_a_tiny_batch` stops once the loss has stayed below 30 % of
  its start for 10 steps in a row, at most 150 steps.
- **`recorder/tests/test_pose.py`:** the MediaPipe estimator test skips, with the reason, when the git-ignored pose
  model isn't downloaded.
- **`pi-bridge/tests/test_protocol.py`:**
  - only the 4 `BridgeLogic` tests need websockets, and they skip with the reason;
  - the other 8 (frame encoding, JSON messages, serial lines, synthetic data) now run on every computer.
- **`scripts/check_all.sh` (new):**
  - runs every suite and prints one table; the exit code is 0 when nothing failed;
  - `--clean` copies the files git would commit (tracked plus new, not ignored) to a temporary folder and runs there;
  - `--only` picks groups or suites;
  - uses each part's `.venv` (from a worktree: the main checkout's) and never installs anything;
  - works with macOS's bash 3.2.
- **`model/README.md`:** the test count and time; the sync accuracy, re-measured.
- **`CLAUDE/CLAUDE.md`:** "Commands" now names `scripts/check_all.sh`; it said "None yet — no code in the project".
- The plan's status, `CONTEXT.md`, `DECISIONS.md`.

## Changed from the plan (item 6)
The plan said: give the fake radar background its own random stream, and set the limit from the webcam frame time.
I didn't change the generator:
- **It would change every fake session.** `SYNTH_VERSION` would go from 2 to 3. `demo.py` and
  `export_dashboard.py --person` would fail until `train.py --fake 6` remakes the fake people (~3 min, +275 MB).
- **It still wouldn't make the input identical everywhere:** the radar background itself differs between computers.

Pinning the test's sessions to the saved-statistics background makes them identical everywhere, with no change to
the generator.

## Measured
- **Pose sync error on fake people:**
  - saved-statistics background, 40 people: median 5.2 ms, 90 % within 17.0 ms, worst 29.0 ms (4 of 40 over 17 ms);
  - real empty-room background, 20 people: median 6.5 ms, worst 16.4 ms;
  - the old 15-ms limit held only for the test's 3 people with the real background; one webcam frame (33 ms) covers
    all 60.
- **The overfit test:**
  - the loss is below 30 % of its start from step 6 on (0.18 at step 10, 0.005 at step 150);
  - a step takes 327 ms, so all 150 steps took 49 s.

## Verified by
`bash scripts/check_all.sh` on this folder, and `--clean` on a fresh copy without the recordings, the pose model or
websockets:

| Suite | Before (8 Nov, clean copy) | Now, clean copy |
|---|---|---|
| model | 65 pass, 7 skipped, **1 fail**; 70 s | 73 tests OK (7 skipped); 28 s |
| recorder | 15 pass, **1 error** | 16 OK (1 skipped: no pose model) |
| pi-bridge | 44 pass, 10 skipped, **1 error** | 66 OK (14 skipped) |
| radar-lab, Encoder 0.1, packets, room map, Drive | pass | pass |
| frontend (6 checks + build) | pass | pass |

This Mac's case was checked too, with the recordings and the pose model linked in:
- `test_synth`: 9/9;
- recorder: 16/16, with the estimator running.

## Found: a bug in the bridge's sEMG health (fixed the same day: [report](2026-11-09-1555-semg-health-fix.md))
- **Where:** `pi-bridge/truerehab_bridge/providers/emg.py`, `health()`, has `if last is None or now - last > 3:`.
- **What it does:** every (re)connect resets `_last_sample` to `None`. Until the first sample arrives, the dashboard is
  told "Connected, but no sEMG samples for 3 s", only milliseconds after connecting.
- **How it showed up:** as a rare failure of v0.3's `test_another_reader_is_named_and_not_fought`:
  - 1 failure in about 15 full runs of the bridge suite;
  - 0 in 20 runs of the test alone, and 0 in 10 full runs afterwards.
- **On the Pi:** after a Wi-Fi reconnect, a dashboard heartbeat that lands in that window shows a false error for
  1 s. That window is exactly what today's reconnect tests look at.
- **Proposed fix:**
  - complain only when no sample has arrived for 3 s since connecting:
    `(last is None and since > 3) or (last is not None and now - last > 3)`;
  - before that, show "Connected, waiting for data" (state "missing");
  - add a test that reads the health right after a reconnect.

## Issues / not done
- Not merged: it is on its own branch, `claude/codebase-audit-diagram-786f9c`.
- Not run:
  - Phisit's backend tests: fastapi isn't installed;
  - the Windows viewer's HTTP test: it needs that viewer running;
  - the firmware builds.
- The map page is the 8 Nov snapshot: it still flags the 3 tests, and it hasn't been rebuilt.

## Next
1. Decide on the bridge fix, before today's Pi test if you want it there (fixed the same day).
2. Merge later: this branch sits on top of v0.3, so merging it into `main` brings v0.3 along (plan step 0.1).
3. Then Phase 0 with you, or Phase 2.

**Uncommitted work:** none: committed on branch `claude/codebase-audit-diagram-786f9c` and pushed (2026-11-09).
