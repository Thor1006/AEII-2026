# Context

<!-- Living state. Updated by /wrap-up at the end of every loop. Keep under ~40 lines: replace, don't append forever. -->

**Last updated:** 2026-10-12 (late evening)

## Current focus
Two synthetic-only pieces are ready and waiting on real radar data:
- CNN frame encoder v0.1 in `sandbox/Encoder_0.1/`
- TypeScript dashboard in `frontend/`, now protocol 1.1: the Pi describes itself (`hello` + manifest), and the page sends start/stop commands. It has a start screen, Session/Technical views and plain-language help. Restyled 2026-10-12 (Fluent palette, Inter, floating cards; `src/styles/theme.css`). Opens on an Apple-style home page (`#/`, `src/home/`) with a live demo, how-it-works list and Camera/Wearables/Radar table; the dashboard is at `#/app`. Design rules in `frontend/DESIGN.md`. "TR" logo in `components/Logo.tsx`.
- **Kit key (protocol 1.2), committed (`c16d563`):** challenge/response handshake + signed commands. Page side and mock server verified (`scripts/check-hmac.ts`, `scripts/check-auth.ts`, browser). Python side (`auth.py`, `server.py`, `__main__.py --new-key/--show-link`, `check_bridge.py --key --auth-selftest`) passes `tests/test_auth.py` (21 ok, 4 skipped) but the bridge has never been run. Plan: [kit-pairing-key](plans/2026-10-12-kit-pairing-key.md).
- **Paused on purpose:** the Python Pi bridge `pi-bridge/` has never run. The user said **do not install its packages (`websockets`, `numpy`) now; ask again when we are really setting up a Pi.** See [report](output/2026-10-11-1828-easier-ui-pi-bridge.md).

## Recent changes
- 2026-10-12 — Kit key (protocol 1.2): challenge/response + signed commands ([plan](plans/2026-10-12-kit-pairing-key.md))
- 2026-10-12 — Home page "AI slop" pass: demo above the fold, no eyebrows/card grids, comparison table, DESIGN.md([report](output/2026-10-12-2243-home-ai-slop-pass.md))
- 2026-10-12 — Home page + hash routing + new TR logo([report](output/2026-10-12-2220-home-page.md))
- 2026-10-12 — Dashboard restyle: Fluent palette, Inter, floating rounded cards, no gradients; pushed to GitHub ([report](output/2026-10-12-2131-dashboard-restyle.md))
- 2026-10-10 — Built the TypeScript dashboard + mock Pi bridge; typecheck, build and browser checks pass ([report](output/2026-10-10-2154-typescript-frontend.md))

## Open questions
- Does `radar_ml_context.md` (presence/range/behavior heads, Mac host) replace or adjust the Oct 5 plan (TrueRehab heads, Pi 5)?
- The real AWR1843 chirp config, which sets the encoder input (view, H, W, C).
- Phase 2 micro-vibration: is it a 1D phase signal (needing its own branch)?
- Team agreement on scope and roles. Is ethics approval needed for healthy volunteers?
- Who writes the radar capture in `pi-bridge/truerehab_bridge/providers/radar.py`? Can the Pi 5 run DCA1000 capture + FFT at 20 fps?
- Multi-kit plan (proposed) suggests MQTT. For now we connect straight to each Pi over WebSocket; `kitId`/`sessionId` are already in protocol 1.1.
- Teammate (KINKIN-007) pushed `Phisit/`: a separate simulation dashboard + FastAPI backend. Merge with `frontend/` / `pi-bridge/`, or keep separate?
- Home page: sign off tagline + comparison-table wording; add a problem section or Thai? Logo uses outlined Apple SF Rounded, so check the licence before any public poster.
- Restyle follow-up: check light mode and a wide window; heatmap colour ramp is still a smooth blend (data colouring) — change it?

## Next steps
1. Team sign-off on the home page copy (tagline, comparison table); then a problem section (and Thai if wanted). Look at `Phisit/` with the teammate.
2. When we really set up a Pi (**ask the user then** before installing packages): install the pi-bridge packages in a venv, run all unit tests (the 4 skipped key tests too), start the bridge with a key, run `check_bridge.py --commands` and `--key … --auth-selftest`, `--new-key --write …`, and open the bridge-served page with a sticker link.
3. Get radar streaming and a first real capture (mmWave Studio + DCA1000). Write down the chirp config.
4. Set the real `InputContract` from that capture, then rerun `check_encoder.py`.
5. Try radar height / elevation angle for shoulder elevation (sandbox finding).
6. Write the real radar provider in `pi-bridge/` (template + steps are in `providers/radar.py`).
7. Later: temporal attention block that takes `[B, T, E]` embeddings.
