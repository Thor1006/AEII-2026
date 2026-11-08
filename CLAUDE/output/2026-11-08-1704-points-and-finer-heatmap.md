# Report: radar points + heatmaps (model input v1) and a finer range profile

**Date:** 2026-11-08 17:04 · **Result:** ⚠️ software built and pushed; the board test of the finer profile and the points decision are still open · **Plan:** [plans/2026-11-08-points-and-finer-heatmap.md](../plans/2026-11-08-points-and-finer-heatmap.md)

## Goal
The user: "so we use both and cross refferences?", then "also make the heat map finer if possible", then "Approve and
build". (Before that: the radar stays on USB; Ethernet firmware would only send bare points.)

## What changed (pushed: 900f4da, 9927122, 7c314ad)
- **`radar-lab/configs/fullmap_fine_awr2x44p.cfg`:** range 5.94 → 3.88 cm per bin, out to 2.48 m.
  - Same 64 bins, bytes per frame, speed steps and 60 fps.
  - Only `profileCfg` differs: start 76.55 GHz, idle 254.3 µs, ramp 42.7 µs, 3311 ksps.
  - **Not yet run on the board.** The old profile is still the default everywhere.
- **Model input contract v1:**
  - H `[4, 64, 32]`: magnitude, phase change, point height, point presence (15 frames = 0.25 s pooled).
  - 32 angle bins, zero-padded (real resolution stays ~9°).
  - Points: `points_of` / `point_cells` / `PointWindow` in `trnet/radar.py`, the same code in the Pi bridge.
  - The network pools 32 angle bins to 8 (239,803 parameters).
- **Session check:** points per frame, points vs heatmap agreement, height noise of a still target.
- **Fake data v2** (`model/data/fake_v2`; the old `data/fake` is left alone):
  - realistic sparse points with real-like height noise;
  - physical steering;
  - the empty-room background resampled for other range steps;
  - the points use their own random stream, so the other sensors' fake data didn't change.
- **Calibration re-run** on the same real recordings for the 32-bin grid. It also picked up the Nov 5 smoke-test
  IMU: |acc| 1.10 → 1.05 g.
- **Pi bridge + dashboard:**
  - 4th radar view "Points (height)", with its own colour scale (±0.6 m, new optional `range` field of a frame stream);
  - views that have shown negatives keep the two-sided scale;
  - EN/TH/zh-HK.
- **`train.py --no-points / --angle-bins`** for comparisons.

## Verified by
- **Real recordings (4):** with sign +1, still points sit **+10.7 to +11.5 dB** above the rest of their range row.
  With −1 it's −0.8 to +5.8 dB; random cells score 0 dB. The empty-room recording is ambiguous: +8.7 vs +10.5.
- **Real point quality** (`check_session`):
  - median 5–7 points per frame;
  - a still target's height jitters **±0.16–0.25 m** per frame (curls, left/right recordings). Pooling 0.25 s
    gives ~±5 cm, about the size of a shrug.
- **Tests:** model 73 (9 new), radar-lab 6, bridge radar + sEMG 20, check-i18n 512 pairs, typecheck.
- **Browser** (replay): 4 radar views arrive; the fake person's points show in orange/blue on "Points (height)".
- **Fake training, same fresh fake people, one run each:**

  | Head | With points (v1) | Without points | Baseline |
  |---|---|---|---|
  | Fatigue MAE | 0.288 | 0.227 | 0.319 |
  | Quality MAE | 0.046 | 0.044 | 0.048 |
  | Shrug F1 | 0.49 | 0.60 | 0.39 |
  | Lean F1 | 0.51 | 0.73 | 0.42 |
  | Reduced-ROM F1 | 0.41 | 0.41 | 0.41 |
  | Risk F1 | 0.51 | 0.63 | 0.28 |

  On fake data the noisy point layers **hurt**: the small network overfits them. Fake data, 6 people, one run each:
  this is a warning sign, not proof.

## Issues / not done
- **The point layers hurt on fake data.** Decision for the user: keep them on by default, or switch them off for
  the model until real sessions show a benefit. Either way the dashboard view and the session check keep them.
- **The finer profile hasn't run on the board.** It needs the radar plugged in (power first, then USB) and a check:
  60 fps, 0 missing, temperature, two metal objects ~5 cm apart. Only then switch `paths.RADAR_CFG`, the recorder
  and the bridge to it.
- **The bridge's websockets tests** (shared recording, live connection) wait for the PortableSSD's test venv.
- **Data rate:** with 32 angle bins and 4 views, the dashboard's data rate roughly doubles (~0.3 MB/s per viewer;
  the finer profile ×1.5). The bridge's `frame_dtype = "u16"` halves it if needed.

## Next
1. **Decide** whether the point layers stay on for the model.
2. **Plug in the radar** and try `fullmap_fine_awr2x44p.cfg`, then switch the defaults if it passes.
3. **Real person sessions:** do the points help there?

**Uncommitted work:** this report, CONTEXT, DECISIONS and the plans: committed and pushed with this report.
