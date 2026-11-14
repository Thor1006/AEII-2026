# Plan: The radar follows the arm (elbow angle and reps, checked against the IMU)

**Status:** done
**Date:** 2026-11-14

## Why
The fatigue model can't beat the mean with 3 people
([report](../output/2026-11-14-1305-first-real-training.md)). An easier, real question: **can the radar alone
follow the curl, with no wearable?** The data says it might. Radar motion at ~1.75 m correlates 0.40–0.80 with the
IMU forearm speed in all 15 usable sessions. Every second of every session is a labelled example (IMU angle at
60 frames/s): about 15 min of curls, not 417 single labels.

This is the proposal's Movement Quality part (ROM, velocity, rep timing). It also fills a gap: the live dashboard
needs radar-only rep detection.

Time box: about 1 day of my work, while you're at school; no hardware. AEII is in 5 days, so anything not working by
day 2 is dropped, not stretched.

## Approach
Everything is tested by leaving one person out: train on 2, test on the 3rd (the same split as
`train.py --val sessions`). The IMU is only the answer key; it never enters the radar model.

1. **No-learning baseline first** (`trnet/armtrack.py`):
   - find the person's range from the radar alone (the range with the most movement, 0.3–3 m);
   - per frame, radar motion at that range: Doppler energy (moving vs approaching/receding), smoothed;
   - count reps from that signal with the existing rep finder's peak logic. If this already counts reps well, we
     use it and stop there for the booth.
2. **Small learned model, if 1 isn't enough:**
   - input: a 1-s window (60 frames) of range-Doppler, cropped ±0.3 m around the person's range, plus the
     angle-spectrum row at that range;
   - output: the IMU's elbow angle and angular speed at the window's end;
   - first a ridge regression on those inputs, then a tiny 1-D conv net (≤ 20 k parameters, not 240 k);
   - reps: `trnet/reps.find_reps` on the predicted angle, the same rule used on the IMU.
3. **Scores, per left-out person and session** (honest, in degrees and reps):
   - angle: correlation and mean error (°) vs the IMU;
   - reps: counted vs the IMU's count, and how many radar reps start within 0.5 s of an IMU rep;
   - range of motion per rep: radar vs IMU (°);
   - next to each, a "chance" number (the radar signal shifted in time), as in the correlation check.
4. **Booth piece, only if 3 is good enough:** `export_dashboard.py --session <folder> --radar-arm` adds a
   "Radar elbow angle (°)" channel next to the IMU's and the radar's rep events, so the replay shows both curves
   together. No frontend change if the dashboard already plots every `aux` channel (I'll check; if not, it's a
   separate OK).

## Files touched
- `model/trnet/armtrack.py` (new) — range finding, radar motion features, ridge + tiny conv net, rep counting.
- `model/armtrack.py` (new) — command: `python armtrack.py --sessions /Volumes/PortableSSD/truerehab-sessions`;
  writes `runs/arm_<date>_<time>/report.md` (S01–S03 codes, never names).
- `model/tests/test_armtrack.py` (new) — on fake sessions: the range finder finds the fake person; a perfect
  signal gives the right rep count; folds never leak the test person.
- `model/export_dashboard.py` — `--radar-arm` option (step 4 only).
- `model/README.md` — a short section.

## Risks / needs OK
- **It may not work well.** Doppler sees speed toward the radar, not the angle; how a curl looks depends on where
  the person faces. Rep counting is the realistic goal; an accurate angle in degrees may not be. The report says
  which.
- **Sync:** no `s` marker was pressed. The IMU was lined up with the radar in only 2 of 15 sessions (+54 and
  +169 ms); the rest are not corrected. Offsets of ~0.1–0.2 s blur the angle's timing but barely affect rep counts.
  The report gives the measured offset per session.
- 3 people again: a result is "works on these 3 people in this room", nothing wider. The booth wording says so.
- Nothing installed, no firmware or radar config, SSD read only, no commit unless you ask.

## How we'll verify
- `bash scripts/check_all.sh` passes, new tests included.
- The report's numbers per left-out person, next to the chance numbers.
- Step 4: open the replay in the dashboard and check both curves and the rep marks by screenshot.
