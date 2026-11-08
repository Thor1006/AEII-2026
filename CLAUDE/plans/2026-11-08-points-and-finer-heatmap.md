# Plan: radar points + heatmaps together, and a finer heatmap

**Status:** built (2026-11-08), see [report](../output/2026-11-08-1704-points-and-finer-heatmap.md); still open: the board test of the finer profile, and whether the point layers stay on (they hurt on fake data).
**Date:** 2026-11-08

## Why
The user: "so we use both and cross refferences?", then "Write the plan" and "also make the heat map finer if possible".

Facts (2026-11-08, from the Nov 5 curls recording, 4367 frames, and the radar profile `fullmap_awr2x44p.cfg`):
- **Every frame already carries points:** x, y, z, speed (TLV 1) and SNR/noise (TLV 7), next to the two heatmaps.
  They're recorded in `radar.bin` already. A median of 7 points per frame (5–10); their heights scatter widely.
- **The heatmap has no height.** The static heatmap holds only the 8 side-by-side antennas.
- **Today's grid:** range 64 steps × 5.94 cm (up to 3.80 m); angle 16 steps (8 antennas, real resolution ~9°);
  speed 16 steps × 0.137 m/s (±1.09 m/s); 60 fps.
- **The USB link is ~84 % full:** ~4.4 KB per frame × 60 fps of ~312 KB/s. More data per frame doesn't fit at 60 fps.

## Approach

### Part 1: a finer heatmap
1. **Range 5.94 → 3.88 cm (a radar settings change, no flash).** A new profile `fullmap_fine_awr2x44p.cfg`; the old
   one stays for rollback.
   - Same slope (100 MHz/µs), same 128 samples, but sampled more slowly (~3.32 Msps) over a longer ramp (~41 µs).
     That sweeps ~3.86 GHz (76.6 → 80.7 GHz, inside the band the Nov 3 Windows profile already used).
   - Idle time shortened by the same amount, so the chirp period, the speed steps and the 60 fps stay as they are.
   - Same 64 range steps, so the **same bytes per frame**.
   - **The cost:** the farthest distance drops from 3.80 m to ~2.48 m (the person stands at 1.0–1.6 m; the dashboard
     already cuts at 2.4 m).
   - 3.88 cm is the waveform's nominal step, not a measured accuracy.
2. **Angle grid 16 → 32 steps**, computed on the Mac/Pi (zero-padded FFT). It's a finer grid for locating peaks, not a
   sharper beam: the real resolution stays ~9° (8 antennas spread over 13 positions). A sharper-beam method (Capon) can be tried later.
3. **Not changed:** speed steps (more would overflow the USB link at 60 fps); height (Part 2 brings it).

### Part 2: points and heatmaps cross-referenced
1. **Read the points** of every frame in `model/trnet/radar.py`, kept with the heatmaps of the same frame (same frame
   number, same instant).
2. **Map each point onto the heatmap grid:** range step from its distance, angle step from its side angle, on the same
   axis as the angle FFT.
   - Check the mapping on real recordings: the points should sit on the heatmap's bright cells.
   - This also shows whether the heatmap's angle axis is mirrored, which feeds into the open left/right question. True
     left/right still needs the metal-object test.
3. **Two new input layers** (input contract **v1**): **height** (the highest point's z in each cell, scaled) and
   **presence** (how many points fell in the cell over the last ~0.25 s, since single frames are too sparse).
   - H becomes `[4, 64, 32]`: magnitude, phase change, height, presence. D stays `[1, 64, 16]`.
   - The network reads its input size from the contract. It's untrained, so this costs no retraining.
4. **Session check:** points per frame, how often points sit near the person, height stability while standing
   still, and points vs heatmap agreement.
5. **Fake data:** make sure the fake points follow the fake person's arm and shoulders (with height), and use the
   new profile's numbers.
6. **Pi bridge + dashboard:** maps on the new grid; a 4th radar view "Points (height)"; translations
   (EN/TH/zh-HK).
7. **Model:** a training run on fake data to check the plumbing; the model README.

## Files touched
- `radar-lab/configs/fullmap_fine_awr2x44p.cfg`: new (the old profile is kept)
- `model/trnet/contract.py` (v1: 32 angle steps, point layers), `radar.py` (points, mapping, inputs), `synth.py`,
  `check.py`, tests, `README.md`
- `pi-bridge/truerehab_bridge/providers/radar.py` (new grid, 4th view, choice of profile) and its tests;
  `recorder/` (`--radar-cfg` already takes a file)
- `model/export_dashboard.py` (4th view), `frontend/src/i18n/catalog.ts` (view name)

## Risks / needs OK
- **The radar's settings change** (Part 1.1): needs your OK before the new profile is sent to the board, and the
  radar plugged in (power first, then USB).
  - No flash. The firmware checks the settings when it starts; if it refuses them, we go back to the old file.
- **Farthest distance ~2.48 m:** stand within ~2.3 m of the radar.
- **Old recordings:** the existing real recordings use the old profile, so they don't match contract v1. They're
  test runs only; the old contract still reads them.
- **The points' height may be too noisy** to help. The real sessions decide; the network can learn to ignore a layer.
- **Larger input** (H ×4 in size): fine for training on the Mac; check the speed on the Pi later.

## How we'll verify
- **Tests:**
  - mapping (known points → expected cells; points on bright cells);
  - contract v1 save/load;
  - fake sessions through `check_session`;
  - all model, bridge, recorder and radar-lab suites.
- **On the board** (with your OK, radar plugged in):
  - new profile accepted; 60.00 fps, 0 missing, temperature OK;
  - before/after range separation: two metal objects ~5 cm apart in distance;
  - points vs heatmap agreement on a short recording.
- **Pi bridge + dashboard:** `check_bridge` with 4 views, then a browser screenshot.
- **Commits:** pushed in small chunks (profile; model input; bridge/dashboard; report).
