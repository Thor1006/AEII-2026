# Context

<!-- Living state. Updated by /wrap-up at the end of every loop. Keep under ~40 lines: replace, don't append forever. -->

**Last updated:** 2026-11-03 (night)

## Current focus
**First real radar data (Nov 3).** The hardware we have is an **AWR2944PEVM** (not the AWR1843 + DCA1000), on USB. `radar-lab/` (standalone) shows the whole room, still objects included, in 2D and in 3D at **60 radar fps** ([report](output/2026-11-03-2214-radar-lab-fullmap-3d.md)). Board quirks (baud 3 125 000, no `numFrames 0`, command port goes silent if closed while running) are in `radar-lab/README.md`. Nov 15 is 12 days away.
- CNN frame encoder v0.1 in `sandbox/Encoder_0.1/` (still synthetic input).
- TypeScript dashboard `frontend/` (protocol 1.2): home, dashboard, kit key, EN/TH/zh-HK, help, session summaries + 5-session history (all committed).
- **Paused on purpose:** the Python bridge `pi-bridge/` has never run. The user said **do not install its packages (`websockets`, `numpy`) now; ask again when we are really setting up a Pi.**
- `Phisit/` (teammate): separate FastAPI + React demo. It shows "future compensation risk" and "reps to compensation", which `frontend/` doesn't.

## Recent changes
- 2026-11-03 — `radar-lab/`: full-room radar map on the real AWR2944PEVM, then 3D viewer at 60 fps ([report](output/2026-11-03-2214-radar-lab-fullmap-3d.md))
- 2026-10-13–17 — Languages, help guide, transitions, session summaries + 5-session history; Delete feature uncommitted ([report](output/2026-10-17-2101-oct13-17-catchup.md))
- 2026-10-12 — Kit key (protocol 1.2): challenge/response + signed commands ([plan](plans/2026-10-12-kit-pairing-key.md))
- 2026-10-12 — Home page "AI slop" pass: demo above the fold, comparison table, DESIGN.md ([report](output/2026-10-12-2243-home-ai-slop-pass.md))
- 2026-10-12 — Home page + hash routing + new TR logo ([report](output/2026-10-12-2220-home-page.md))

## Open questions
- Which radar is the project's radar now: AWR2944PEVM (what we have, on-chip heatmaps, no raw data) or AWR1843 + DCA1000 (raw ADC, needs the DCA)? It sets the encoder input: today 64 range bins × 64 angles (static map) + 64 × 16 range-Doppler, 30–60 fps.
- LAN: the AWR2944PEVM's Ethernet needs TI's Ethernet firmware (flashing — ask first), which sends points, not heatmaps. Worth it?
- Shoulder elevation is invisible to a front radar at chest height (sandbox). Elevation antennas or a different mount height, decided before data collection?
- One dashboard or two: merge `Phisit/` ideas (compensation risk, reps-to-compensation) into `frontend/`, or keep separate?
- Does `radar_ml_context.md` replace or adjust the Oct 5 plan? Phase 2 micro-vibration: a 1D phase branch?
- Team scope and roles; ethics approval for healthy volunteers?
- `CLAUDE.md` says macOS/zsh; Nov 3 ran on macOS, but some October work ran on Windows (git user KINKIN-007). Keep as is?
- Home page copy sign-off; SF Rounded logo licence before any public poster. Poster says "oral health" (typo?).

## Next steps
1. radar-lab: test stop-on-close in `view3d.py` (no reset needed afterwards?); check left/right and antenna order with a person standing to one side.
2. Decide the radar (open question 1), then record a first labelled capture (e.g. elbow flexion) with `radar-lab` and save frames to disk.
3. Set the real `InputContract` from that capture, then rerun `check_encoder.py`; try radar height or elevation for shoulder elevation.
4. Small fixes: the Reps panel keeps counting after a session stops (`sessionEvents` ignores `endedAt`); the Python bridge's `session_end` lacks `reps`; `sandbox/ml_Try-1.py` doesn't run.
5. When we really set up a Pi (**ask the user first** before installing packages): venv, all pi-bridge tests, `check_bridge.py --commands` and `--key … --auth-selftest`.
6. Write the real radar provider in `pi-bridge/providers/radar.py` from `radar-lab/radarlab/` (parser + maps already work); later a temporal block on `[B, T, E]` embeddings.
