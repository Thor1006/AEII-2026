# Plan: radar-lab — 3D view at up to 60 fps

**Status:** done
**Date:** 2026-11-03

**Result:** `radar-lab/view3d.py` runs at **60 radar fps with both heatmaps kept** (601/601 frames in 10 s,
firmware spare time 1.7–7.8 ms/frame); the screen redraws at the display rate (119.6 fps on this 120 Hz Mac).
The 83 % link estimate below was too cautious: measured, the firmware sends while the next frame chirps.
New finding: closing the command port while the radar runs makes it silent until reset → `view3d.py` keeps
it open and sends `sensorStop` on close (**untested on the board**).

**User's choices:** install pyqtgraph/PyQt6/PyOpenGL into `radar-lab/.venv`; **keep both heatmaps, ~30 radar fps**
(screen still redraws at 60 fps, smoothing between radar frames); test faster configs on the board.
So step 3 below keeps the RD heatmap and the chirp unchanged, and only shortens the frame period.

## Why
The user wants the full-scene radar view in 3D and at 60 fps. Today: 2D matplotlib, ~3.3 radar frames/s.

## Limits found (AWR2944PEVM, UART demo, SDK 04.07.02.01)
- **3D:** the static heatmap is 2D (range × azimuth, 8 azimuth antennas). No elevation heatmap from this firmware.
  The point cloud has x, y, z (one TX sits on a raised row) and, with clutter removal off, includes still objects — but it is sparse.
  Dense 3D needs raw ADC (DCA1000) or custom firmware.
- **60 fps display:** easy with OpenGL; matplotlib can't.
- **60 radar frames/s:** USB serial at 3 125 000 baud ≈ 312 KB/s.
  Static + RD heatmap + points ≈ 4.3 KB/frame → 258 KB/s at 60 fps (83 %, likely crashes).
  Static heatmap + points ≈ 2.2 KB → 42 %, should fit.
  Chirps: 16 loops × 3 TX × 297 µs = 14.3 ms of a 16.7 ms frame → shorten idle time (speed steps ~0.31 m/s instead of 0.137).
  Real processing time: read from the stats TLV.

## Approach
1. Install `pyqtgraph`, `PyQt6`, `PyOpenGL` into `radar-lab/.venv` (with OK).
2. `view3d.py` (OpenGL, redraw at 60 fps):
   - floor: range-azimuth heatmap as a coloured surface (height = strength, optional);
   - points: point cloud in 3D (x, y, z), coloured by speed, with a short fade trail;
   - mouse orbit/zoom; on-screen radar fps + display fps; reuse `radarlab/` parser, cfg and sim.
   - serial read on a background thread so drawing never waits for the port.
3. Configs: `configs/fast_awr2x44p.cfg` — statsInfo on, RD heatmap off, shorter idle time, frame period 33 ms then 16.7 ms; lower CFAR threshold for a denser cloud.
4. Measure step by step on the board (30 fps → 60 fps) with the stats TLV; keep the fastest that runs without a crash.

## Files touched
- `radar-lab/view3d.py` (new), `radar-lab/configs/fast_awr2x44p.cfg` (new), `radar-lab/radarlab/tlv.py` (parse points + stats), `radar-lab/README.md`, tests.

## Risks / needs OK
- Installing ~100 MB of packages into `radar-lab/.venv` (not pi-bridge).
- Faster configs may crash the firmware (needs the reset button again). RAM only, no flashing.
- 60 radar frames/s may not be reachable; fallback is the fastest stable rate, drawn at 60 fps.

## How we'll verify
- Sim mode at 60 fps display (frame-time counter).
- Real board: stats TLV margins positive, no frame drops in `--dump`, measured radar fps.
