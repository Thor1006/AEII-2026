# Context

<!-- Living state. Updated by /wrap-up at the end of every loop. Keep under ~40 lines: replace, don't append forever. -->

**Last updated:** 2026-10-11

## Current focus
Two synthetic-only pieces are ready and waiting on real radar data:
- CNN frame encoder v0.1 in `sandbox/Encoder_0.1/`
- TypeScript dashboard in `frontend/`, now protocol 1.1: the Pi describes itself (`hello` + manifest), and the page sends start/stop commands. It has a start screen, Session/Technical views and plain-language help.
- **Paused mid-task:** the new Python Pi bridge `pi-bridge/` is written but **never run**. Its packages aren't installed yet (needs the user's OK). See [report](output/2026-10-11-1828-easier-ui-pi-bridge.md).

## Recent changes
- 2026-10-11 — Easier UI + protocol 1.1 + Python Pi bridge and checker (frontend verified, Python untested) ([report](output/2026-10-11-1828-easier-ui-pi-bridge.md))
- 2026-10-10 — Built the TypeScript dashboard + mock Pi bridge; typecheck, build and browser checks pass ([report](output/2026-10-10-2154-typescript-frontend.md))
- 2026-10-08 — Built frame encoder v0.1: 17/17 checks pass, synthetic LOSO ties SmallCNN ([report](output/2026-10-08-2105-frame-encoder.md))
- 2026-10-07 — FMCW chain + ML example sandbox (`sandbox/`): shoulder elevation is undetectable with a front-mounted radar
- 2026-10-05 — Proposed ML plan & stack

## Open questions
- Does `radar_ml_context.md` (presence/range/behavior heads, Mac host) replace or adjust the Oct 5 plan (TrueRehab heads, Pi 5)?
- The real AWR1843 chirp config, which sets the encoder input (view, H, W, C).
- Phase 2 micro-vibration: is it a 1D phase signal (needing its own branch)?
- Team agreement on scope and roles. Is ethics approval needed for healthy volunteers?
- Who writes the radar capture in `pi-bridge/truerehab_bridge/providers/radar.py`? Can the Pi 5 run DCA1000 capture + FFT at 20 fps?
- Multi-kit plan (proposed) suggests MQTT. For now we connect straight to each Pi over WebSocket; `kitId`/`sessionId` are already in protocol 1.1.
- Version control: not a git repo yet (`frontend/` alone is ~60 files).

## Next steps
0. Finish the paused task: install the pi-bridge packages (ask first), run the unit tests, `check_bridge.py --commands` (and the `BREAK=` modes, which must fail), and open the bridge-served page.
1. Get radar streaming and a first real capture (mmWave Studio + DCA1000). Write down the chirp config.
2. Set the real `InputContract` from that capture, then rerun `check_encoder.py`.
3. Try radar height / elevation angle for shoulder elevation (sandbox finding).
4. Write the real radar provider in `pi-bridge/` (template + steps are in `providers/radar.py`).
5. Later: temporal attention block that takes `[B, T, E]` embeddings.
