# Report: radar-lab — full-room radar map, then 3D at 60 fps (first real radar data)

**Date:** 2026-11-03 22:14 · **Result:** ✅ done (one piece untested, see below) · **Plan:** [fullmap](../plans/2026-11-03-radar-lab-fullmap.md), [3D 60 fps](../plans/2026-11-03-radar-lab-3d-60fps.md)

## Goal
Get the radar talking to the Mac and show the *whole* room (still objects too), not only the moving points of the TI demo; then show it in 3D at 60 fps.

## What changed
- `radar-lab/` (new, standalone) — TLV frame parser, heatmap maths, config reader (antenna layout, range/speed scales), simulator, 2D viewer `view.py` (matplotlib), 3D viewer `view3d.py` (pyqtgraph/OpenGL), 6 tests, README with everything learned about the board.
- `radar-lab/configs/fullmap_awr2x44p.cfg` — TI visualizer config for SDK 04.07 / AWR2X44P with clutter removal off, both heatmaps + stats on, finite frame count.
- `radar-lab/.venv` (not committed) — pyserial, pyqtgraph, PyQt6, PyOpenGL (user OK'd each install).
- `.gitignore` (+ `.venv/`) and `firmware/myoware_demo/myoware_demo.ino` — older uncommitted work, included at the user's request.

## Verified by
- Real AWR2944PEVM over USB: theory confirmed (`radar-lab/real_room.png`, `real_room3d.png`): walls/objects visible with clutter removal off.
- `view3d.py --measure`: **60.0 radar fps, 601/601 frames, both heatmaps kept**; firmware: processing 0.66 ms, UART send 14.1 ms, spare 1.7–7.8 ms/frame. Screen redraws at 119.6 fps (120 Hz display).
- `python3 -m unittest discover tests` — 6 pass.

## Issues / not done
- **LAN not used:** the board's firmware is the UART demo (no `enetStreamCfg`). The Ethernet cable links at 1 Gbps but the board sends nothing on it. TI's Ethernet demo would need flashing and sends points, not heatmaps.
- **Board quirks found:** `numFrames 0` crashes `sensorStart`; data port is 3 125 000 baud; closing the command port while the radar runs makes it silent until reset (3 resets today). `view3d.py` now keeps the port open and sends `sensorStop` on close — **untested on the board**.
- 3D height comes from the point cloud only (~6 points/frame); the heatmap itself is 2D (range × azimuth, 8 antennas).
- Left/right direction and antenna order (even vs `antGeometryCfg`) not confirmed with a known target.

## Next
1. Test stop-on-close in `view3d.py` (start, close window, check `version` still answers without reset).
2. Stand ~1.5 m to one side: check left/right (`F` if mirrored) and the antenna order.
3. Decide how radar-lab feeds the main project (pi-bridge radar provider, encoder input contract: 64 range bins × 64 angles, 30–60 fps).

**Uncommitted work:** no (committed and pushed right after this report)
