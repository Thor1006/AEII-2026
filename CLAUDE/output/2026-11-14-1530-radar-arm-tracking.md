# Report: The radar counts elbow curls on its own

**Date:** 2026-11-14 15:30 · **Result:** ✅ done (rep counting and pace; no angle in degrees) · **Plan:** [2026-11-14-radar-arm-tracking](../plans/2026-11-14-radar-arm-tracking.md)

## Goal
Show that the radar alone, with no wearable, follows the elbow curl and counts reps, using the IMU only as the
answer key; and put it in the dashboard replay for AEII.

## Data
`/Volumes/PortableSSD/truerehab-sessions`: now 26 sessions, 4 people (6 new `TTT` sessions from 14 Nov 01:44–02:09
appeared after this morning's run). 19 scored; 7 left out: 5 without IMU reps, 1 under 10 s, and TTT `015221`,
where only 5 % of radar frames line up (its frame numbers jump to 65,535 in 65 s; worth a look in the Pi bridge's
frame-number count-on). Reports show S01–S04 (codes in alphabetical order of the subject IDs; the
list is printed on screen only).

## What changed
- `model/trnet/armtrack.py` (new) — no learning:
  1. person range: the range bin whose Doppler velocity repeats at curl pace (0.25–1 Hz) with the most moving power;
  2. radial velocity there (Doppler centroid, zero-speed bins left out);
  3. leaky integral (1.5 s) → an arm signal scaled to ~0–100, sign chosen so the arm's still moments sit low;
  4. reps with `reps.find_reps` (the IMU's own rule); `score_reps` against IMU turning points (top or bottom,
     ±0.25 s) and a chance level (same reps moved 1–10 s at random).
- `model/armtrack.py` (new) — command; writes `runs/arm_<date>_<time>/report.md` and `results.json`.
- `model/export_dashboard.py` — `--radar-arm`: rep events from the radar, two charts (radar arm signal, IMU elbow
  angle as answer key), network scores and advice left out; non-code subjects become `anon` in every replay.
- `model/tests/test_armtrack.py` (new, 5 tests); `model/README.md` section.

## Results (`model/runs/arm_2026-11-14_152626`)
- Person range found from the radar alone: 1.72–1.96 m in 18 of 19 sessions (one at 1.01 m still worked).
- Radar velocity vs IMU arm speed: |r| 0.74–0.96 in every scored session; radar and IMU lined up within 0.1 s.
- **Count: radar 537 reps, IMU 537.** Per session within ±1 in 14 of 19; worst: S04 `014406` 21 vs 30.
- Pace: median time between reps matches the IMU within 0.05 s in nearly every session.
- Timing: 83 % of IMU reps have a radar rep within ±0.25 s of a turning point; chance 47 %. Two slow sessions
  (S01 `043646` 10 %, S02 `074144` 38 %) count perfectly but turn early (the leaky integral leads on slow reps).
- Per person found: S01 79 %, S02 78 %, S03 91 % (chance 67 %: fast reps), S04 88 %.

## Verified by
- `bash scripts/check_all.sh`: nothing failed (model 85 tests).
- Replay `2026-11-13_080422_anon_elbow_flexion_radar-arm.ndjson` opened in the dashboard (`npm run dev`): rep count
  rises with the radar's reps; the Technical view shows the radar arm signal and the IMU angle with the same curls
  beat for beat; no console errors; no names in the file.

## Issues / not done
- No elbow angle in degrees and no top/bottom (sign is a coin flip), so no range of motion per rep.
- The fixed numbers (curl band, leak, swing) were chosen on these same sessions: no held-out check.
- Step 2 of the plan (learned angle model) skipped: step 1 already counts reps; degrees need more than the time left.
- The Session view's score dials stay empty in a `--radar-arm` replay (on purpose); use the Technical view at the booth.
- Live use needs the same code in the Pi bridge (not done).

## Next
1. Booth: pick 1–2 sessions and export them with `--radar-arm`; say "counts curls from the radar alone, checked against
   an IMU, 4 people".
2. After AEII: check TTT `015221`'s frame numbers; tune nothing further without new people; then port to the bridge.

**Uncommitted work:** yes
