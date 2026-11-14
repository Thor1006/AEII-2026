# Report: First training on real recordings, and a 2-people-train split

**Date:** 2026-11-14 13:05 · **Result:** ⚠️ partial (code done and tested; the model is not yet better than the mean) · **Plan:** [2026-11-14-train-two-test-one](../plans/2026-11-14-train-two-test-one.md)

## Goal
Find the new recordings on the PortableSSD, train the radar-only network on them, and change the split so that with
3 people each model trains on 2 instead of 1.

## Data
- SSD mounted at `/Volumes/PortableSSD`; sessions in `truerehab-sessions/` (recorded by the Pi bridge, 10–13 Nov).
- 19 sessions, 3 people. `check_session.py`: **15 usable, 417 reps** (S01 145, S02 162, S03 110); 4 unusable
  (one without sEMG/IMU lines, three where no reps were found).
- Reps come from the IMU elbow angle. No markers were pressed (`markers.csv` is header-only: no `s`, no space), no pose
  → compensation shrug/lean can't be labelled; comp_rom has 23 positives of 417. 106 reps longer than 128 frames
  (~2.1 s) get cropped.
- Subject IDs on the SSD are first names (the check warns). Reports now show S01–S03; the name list is printed on
  screen only.
- The check's "no movement seen in front" warning (12 of 15) is misleading: per session, range-Doppler motion at
  1.7–1.9 m correlates **0.40–0.80** with the IMU forearm speed (circular-shift chance ≤ 0.22). The radar sees the arm.

## What changed
- `model/trnet/dataset.py` — `session_val_splits()`: each other person trains, their last session (≥ 4 reps)
  validates; the test person is never in train or val.
- `model/trnet/training.py` — `loso_folds(sessions, val)`; `run_loso(..., val="person"|"sessions")`.
- `model/trnet/baseline_ridge.py` (new) — ridge on per-rep timing (duration, rest) and 3 radar motion numbers,
  relative to each session's first 3 reps; numpy only.
- `model/train.py` — `--val auto|person|sessions` (auto: sessions below 5 people), names → S01…, label-spread
  table and ridge table in `report.md`.
- `model/tests/test_dataset_train.py` — 3 new tests (no leak, one val session per person, ignored short sessions,
  error with no second session; folds for both modes; ridge recovers a linear rule).
- `model/README.md` — one paragraph on the two splits.

## Results (mean over the 3 left-out people; MAE lower is better)

| Head | Person val (`runs/2026-11-14_130205`) | Sessions val (`runs/2026-11-14_130309`) | Mean baseline |
|---|---|---|---|
| fatigue | 0.231 (baseline 0.232) | **0.213** (baseline 0.235) | — |
| quality | 0.036 (0.035) | 0.031 (0.031) | — |
| comp_rom macro-F1 | 0.49 (0.49) | 0.49 (0.49) | — |

Sessions-val fatigue per person: S01 0.306 vs 0.306 (tie), S02 0.192 vs 0.165 (**worse**), S03 0.142 vs 0.234
(better). One better, one worse, one tie: **not a reliable gain**; one seed only.

- Label spread: quality barely varies (std 0.02–0.05 per person) → nothing to learn there. Fatigue does vary
  (std within a session 0.11–0.24). comp_rom is rare.
- Ridge: radar features add nothing over the mean on any person in either split; timing alone doesn't either.

## Verified by
- `bash scripts/check_all.sh`: nothing failed (model 80 tests).
- `--val person` reproduces the earlier run's numbers exactly (`runs/2026-11-14_125327`).
- Not done from the plan: `train.py --fake 6 --val sessions`, because fake people have one session each (it raises
  a clear error); the session split is tested with two sessions per fake person in the unit test instead.

## Issues / not done
- The network isn't shown to beat the mean on real data. 3 people is too few to tell.
- Fatigue/quality labels still use placeholder thresholds.

## Next
1. Record 2–3 more people (codes, not names; press `s` + space; webcam pose for compensation).
2. Rerun `train.py --sessions /Volumes/PortableSSD/truerehab-sessions` (auto picks the split).
3. Loosen or redefine the check's "movement in front" warning (it uses the empty-room p99 over 0.3–3 m).

**Uncommitted work:** yes (5 modified files in `model/`, the new `baseline_ridge.py`, this report and the plan)
