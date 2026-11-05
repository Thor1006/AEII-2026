# Report: radar-only network + data pipeline, built and tested without sensors

<!-- Filename: YYYY-MM-DD-HHMM-<slug>.md -->

**Date:** 2026-11-05 13:16 · **Result:** ✅ done (untrained by design) · **Plan:** [plans/2026-11-05-neural-network.md](../plans/2026-11-05-neural-network.md)

## Goal
Build everything from a recorder session to scores and a recommendation, plus fake data tuned from the real
recordings and a one-command session check, so the user can work on the model anywhere (e.g. at school)
without sensors. The user approved this with "Approve and build".

## What changed
- `model/` (new, 3,870 lines; its own `.venv` reuses the installed PyTorch 2.14.1/numpy, nothing downloaded):
  - **`trnet/contract.py`:** `v0-draft` input contract, built from the recorded profile and saved with the weights.
  - **`trnet/radar.py`:** frames are put on a 60-fps grid, using the frame number as a clock with a lower-edge
    fit. Then: gaps are masked, an angle FFT is done with the antennas at their real columns, and magnitude,
    phase-change and range-Doppler (log2 Q8 → dB) channels are made.
  - **`trnet/truth.py`, `sync.py`, `reps.py`, `labels.py`, `pipeline.py`:** sEMG MDF (FFT band-pass and
    50-Hz comb), IMU forearm angle, pose angles (reused from `recorder/rec/pose.py`), shrug sync against the
    radar, reps and sets, SPARC smoothness, and labels with `PLACEHOLDER_THRESHOLDS`.
  - **`trnet/network.py`:** 239,515 parameters (stems 5,168, trunk 109,600, within-rep 86,849, GRU 37,248,
    heads 650). The phase channel can be switched off.
  - **`trnet/calibrate.py` → `model/calib/real_stats.json` (280 KB):** from the real recordings, it saves:
    - radar room clutter and noise patterns per range bin, with their frame-to-frame correlation;
    - range-Doppler levels;
    - the real delivery-jitter sequence;
    - IMU still noise and bias;
    - the Wi-Fi delay sequence.

    sEMG and pose are marked uncalibrated.
  - **`trnet/synth.py`:** fake sessions in the exact recorder format. The radar runs on top of real
    empty-room frames, or on the stats when the recordings aren't there. It can plant 13 kinds of problems on
    purpose.
  - **`trnet/check.py` + `check_session.py`:** checks files and line formats, rates and gaps, board
    counters, saturation, temperature, movement in front, shrug sync, reps and cropping, what the session can
    train, and privacy/safety. Exit code 0 means usable.
  - **`trnet/dataset.py`, `training.py`, `train.py`, `recommend.py`:** cached samples, leave one subject
    out, masked losses, a report against the baseline, and the 5 rules plus a live `Advisor`.
  - **`tests/` (57 tests), `README.md`, `.gitignore`** (`.venv/`, `data/`, `runs/`, `__pycache__/`).
- **Plan:** updated with the user's 2 additions and the heatmap correction before approval; now `done`.
- **Changed during the build, compared with the plan:**
  - Each sample (one set) gets the **session's** first 3 reps as its baseline, not the set's own. Labels also
    compare with the session's first reps, so fatigue keeps building across sets.
  - Rep features are duration **and** rest before the rep (+64 parameters).
  - The stems are conv → pool → conv, which is cheaper with the same parameters.
  - The MDF label uses the active part of each rep and is smoothed over 3 reps. One 2-s rep scatters by ~5 %,
    which is a quarter of the fatigue scale.
  - **Shrug sync:**
    - Every sensor becomes a speed-like signal, smoothed the same way.
    - The window ends at the first rep marker.
    - It is applied to pose and IMU only; sEMG is reported (electromechanical delay).
  - **Training:**
    - Heads start at the training average.
    - The score losses are smooth-L1, with the same pull as the flags.
    - The flags' extra positive weight is capped at 5×.
    - Training runs up to 40 epochs with patience 8.

    The first fake run, with the original setup, did not beat the baseline (quality MAE 0.23 vs 0.05).
  - The fake-vs-real noise-floor test no longer asks for "within 1 dB in every bin". It requires a mean
    difference under 0.5 dB, and no bin worse than the real recording differs from itself (4.8 dB).

## Verified by
- **Tests:** 57/57 in 53 s, including:
  - shapes at every layer and the parameter count;
  - causality over reps;
  - padded frames and reps changing nothing;
  - baseline subtraction;
  - the contract refusing a mismatch;
  - the angle FFT matching radar-lab's `maps.range_azimuth` on a real frame;
  - phase 0 after a gap and 0.32 rad for 0.1 mm of motion;
  - MDF and mains removal, and a 20 % drop giving fatigue 1.0;
  - reps, sets and cropping;
  - label masks and next-rep risk;
  - no person leaking between training and test;
  - overfitting a tiny batch;
  - the rules.
- **Real recordings:**
  - All 919 frames of `2026-11-04_183625_TEST_radar_check` load: 60.00 fps, 45 °C.
  - `record_rows` gives the same rows as the recorder's `record_mode`.
- **`check_session.py --all` on the 9 real sessions, as the plan expected:**
  - 3 radar sessions: 60 fps, 0 missing, nobody in front → "no ground truth".
  - USB IMU sessions: 200 Hz with board counters at 0.
  - 2 Wi-Fi sessions: `emg.csv` flagged as IMU lines; `wifi_check` shows its link drop.
  - Exit code 1, since none is usable yet.
- **Fake sessions:**
  - The good one is `USABLE` with fatigue ✓, quality ✓ and compensation ✓.
  - Every planted problem fires its warning: a gap, a Wi-Fi drop, sEMG over USB, saturation, no shrug, a long
    rep, a name instead of a code, raw video, and wrong `emg.csv` lines.
- **Fake vs real:**
  - noise floor mean difference < 0.5 dB;
  - frame timing reproduced;
  - IMU still noise within 20 %;
  - Wi-Fi delay median within 5 ms.
- **Sync on fake sessions:** all 3 shrugs found; IMU within 5 ms of the truth; the pose's 60-ms delay found
  within ±15 ms.
- **`train.py --fake 6`** (run `model/runs/2026-11-05_131149`, Apple GPU, 2.0 min):

  | Head | Model | Baseline |
  |---|---|---|
  | Fatigue MAE | 0.251 | 0.319 |
  | Quality MAE | 0.045 | 0.048 |
  | Shrug F1 | 0.53 | 0.39 |
  | Lean F1 | 0.63 | 0.42 |
  | Risk F1 | 0.57 | 0.28 |
  | Reduced-ROM F1 | 0.41 | 0.41 (no better) |

  Fake data, so this checks the plumbing only.
- **Speed:** one frame through the CNN takes 0.32 ms on the Apple GPU and 0.87 ms on CPU. A real-size training
  step is 15× faster on the Apple GPU.

## Issues / not done
- **Found in the real data:**
  - 2 of the 6 IMU recordings (`imu_fw_sim*`) are the firmware's simulation mode, so 4 are real; I had said 6.
  - The two empty-room radar recordings differ by up to 38 dB in some range bins, so the setup changed between
    them. The first one differs from itself by up to 4.8 dB between its halves.
  - Real radar noise moves together across the 8 antennas, and near the radar it changes slowly (correlation
    0.85–0.99).
- **Rep length:** T = 128 frames (2.13 s) crops 58 % of the fake reps (83/144, which last 2.0–2.9 s). Decide T
  after the first real session.
- **Fake data limits:**
  - The stats-only background (used when the recordings aren't on the computer) is off by up to ~2 dB in 5
    range bins. The real-frames background (the default here) is better.
  - sEMG and pose values are textbook, not measured.
- **Unproven or unmeasured:** fatigue from radar; the phase channel's value; Pi speed.
- **Still to decide:** the thresholds and rules' numbers are placeholders; the contract is not frozen.
- **Disk:** 271 MB of fake sessions and 62 MB of cache in `model/data` (git-ignored; `rm -rf data runs` inside
  `model/` removes them).

## Next
1. First full session with the README protocol: 5 s still, `s` + 3 shrugs, sets with space per rep, MyoWare on
   battery/Bluetooth. Run `check_session.py` right after it, then `python -m trnet.calibrate`.
2. Choose T (frames per rep) from the real rep durations, then freeze `InputContract` v1.
3. Agree the label thresholds and rule numbers with a physiotherapist.
4. Train for real (`train.py --sessions ...`) once at least 3 people have usable sessions.

**Uncommitted work:** yes — `model/` and `CLAUDE/` files (not committed or pushed).
