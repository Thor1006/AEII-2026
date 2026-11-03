# Plan: radar-lab — full-scene radar map (static + moving)

**Status:** done <!-- user asked directly: "make an all new folder and do this project first to test my theory" -->

**Result (2026-11-03):** works on the real AWR2944PEVM over USB. Still objects show up once
clutter removal is off and the heatmaps are on. Details and open checks in `radar-lab/README.md`.
**Date:** 2026-11-03

## Why
The point-cloud demo (and ChatGPT's attempt) only shows things that move: the firmware removes static clutter and keeps only CFAR peaks. The user wants the whole scene mapped, moving or not, with the AWR2944PEVM we have now (no DCA1000).

Theory to test: turn clutter removal off and ask the mmWave demo for its **heatmaps** (range-azimuth static heatmap + range-Doppler heatmap) instead of points. Walls, chairs and a still person then show up.

## Approach
1. New standalone folder `radar-lab/` (not wired into `pi-bridge/` or `frontend/` yet).
2. TLV frame parser for the TI mmWave demo UART output (magic word, 40-byte header, TLVs).
3. Heatmap maths: static heatmap (range × virtual antenna I/Q) → angle FFT → range-azimuth map; range-Doppler heatmap reshape.
4. Simulator that emits the same byte stream (wall, chair, still person, moving arm), with a clutter-removal switch to reproduce "only moving points".
5. Viewer (matplotlib): live window or `--save` PNG; `--sim` or real serial ports; `--probe` lists the firmware's CLI commands; `--dump` prints TLV types.
6. Config template with `clutterRemoval` off and heatmaps on — marked UNVERIFIED for the AWR2944P demo.

## Files touched
- `radar-lab/` — new folder only.

## Risks / needs OK
- The AWR2944P SDK demo's CLI commands and TLV types are not verified; the 2944 demo uses DDMA and may differ from the xWR18xx/68xx demo. `--probe` and `--dump` exist to find out.
- Live mode needs `pyserial` (not installed). Ask before installing.
- Sending a config to the radar is volatile (RAM only, no flashing), but the user runs it, not Claude.

## How we'll verify
- `python3 -m unittest` in `radar-lab/` (parser round trip, split/garbage input, sim map shows static objects; clutter removal hides them).
- `python3 view.py --sim --save` PNG, with and without `--clutter-removal`.
- Real board: later, when it is plugged in.
