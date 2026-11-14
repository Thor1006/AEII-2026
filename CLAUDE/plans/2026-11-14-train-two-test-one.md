# Plan: Train on 2 people, test on the third

**Status:** done
**Date:** 2026-11-14

## Why
First real training run (2026-11-14, `model/runs/2026-11-14_125327`, 417 reps from 3 people on the PortableSSD):
the model equals the simple baseline on every head (fatigue MAE 0.231 vs 0.232, quality 0.036 vs 0.035,
comp_rom F1 0.49 vs 0.49).

The split is the main cause. `loso_splits` (`trnet/dataset.py:162`) takes one *whole person* for testing and
one *whole person* for validation (early stopping), so with 3 people each model trains on **one person only**.
Validation loss rose after epoch 1–3 in every fold: it learned that one person, not curls in general.

Meanwhile the radar does follow the arm: per session, radar motion at ~1.7–1.9 m correlates 0.40–0.80 with the
IMU forearm speed (chance ≤ 0.22). So there is a signal to learn; the question is whether this network can learn it
from 2 people.

## Approach
1. **New split when there are few people** (`trnet/dataset.py`): for each test person, train on **all the others**.
   Validation for early stopping = the **last session of each training person** (held out by session, not by
   person). The test person is never used for training or for stopping. With ≥ 5 people the current
   person-level validation stays the default.
   - Flag: `train.py --val sessions|person` (default: `sessions` below 5 people, `person` from 5).
   - Each person has 4–6 usable sessions, so this keeps ~80 % of the training reps for training.
2. **Check the labels before blaming the network** (report only, no code change to the labels):
   - spread of the fatigue and quality targets per person and per session (quality MAE 0.035 suggests it barely
     varies; if so, the head has nothing to learn);
   - comp_rom has only 23 positives of 417, so its F1 will stay noisy.
3. **A tiny sanity model next to the network**, in the same report: ridge regression on 3–4 hand-made radar
   features per rep (motion energy at the person's range: peak, mean, duration). If even that beats the baseline
   on the left-out person, the radar carries the information and the big network is the problem (too many
   parameters for 2 people). If not, more people are needed before any model will help.
4. Run both splits on the same data (current `person` and new `sessions`) and put both tables in one report, so
   the change is visible, not hidden.

## Files touched
- `model/trnet/dataset.py` — a `session_val_splits()` next to `loso_splits()`.
- `model/trnet/training.py` — `run_loso(..., val="person"|"sessions")`.
- `model/train.py` — `--val` flag; label-spread table and ridge baseline in `report.md`.
- `model/trnet/baseline_ridge.py` (new, small) — hand-made radar features + ridge (numpy only, nothing to install).
- `model/tests/test_dataset_train.py` — tests: the test person never appears in train/val; each training person
  gives exactly one val session; falls back to person validation from 5 people.
- `model/README.md` — one paragraph on the two splits.

## Risks / needs OK
- **Honesty of the numbers:** validating on later sessions of the *training* people is easier than on a new
  person, so early stopping may pick a model that suits those people. The test score stays honest because the test
  person is untouched; the report will say this.
- 3 test people is too few to call any gain real. Small differences (e.g. 0.231 → 0.22) will be reported as
  "not distinguishable", not as an improvement.
- The SSD sessions use first names as subject IDs. The code only reads them; reports will show S01/S02/S03 instead.
  Renaming the folders on the SSD is your call (not part of this plan).
- No firmware, radar config, or SSD files change. Nothing to install. No commit unless you ask.

## How we'll verify
- `bash scripts/check_all.sh` passes (old tests + the new split tests).
- `train.py --fake 6 --val sessions` still beats the baseline on fake data (plumbing).
- `train.py --sessions /Volumes/PortableSSD/truerehab-sessions --val person` reproduces today's numbers (same seed).
- Same with `--val sessions`: report both tables, the label spread, and the ridge baseline per left-out person.
