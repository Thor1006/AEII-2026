# Context

<!-- Living state. Updated by /wrap-up at the end of every loop. Keep under ~40 lines: replace, don't append forever. -->

**Last updated:** 2026-10-17 (evening)

## Current focus
**Still no real radar capture.** The Oct 5 plan wanted one by Oct 12 and data collection from Oct 20; Nov 15 is ~4 weeks away. Everything below runs on synthetic data:
- CNN frame encoder v0.1 in `sandbox/Encoder_0.1/`.
- TypeScript dashboard `frontend/` (protocol 1.2): home page `#/`, dashboard `#/app`, kit key, Session/Technical views; since Oct 13 also EN/TH/zh-HK (`src/i18n/`), Help & Guide, transitions, session summaries (CSV/print) and 5 saved summaries in localStorage. **Uncommitted:** Delete a saved summary, which passes its tests and a browser check. See [report](output/2026-10-17-2101-oct13-17-catchup.md).
- **Paused on purpose:** the Python bridge `pi-bridge/` has never run. The user said **do not install its packages (`websockets`, `numpy`) now; ask again when we are really setting up a Pi.**
- `Phisit/` (teammate): separate FastAPI + React demo. It shows "future compensation risk" and "reps to compensation", which `frontend/` doesn't.

## Recent changes
- 2026-10-13–17 — Languages, help guide, transitions, session summaries + 5-session history; Delete feature uncommitted ([report](output/2026-10-17-2101-oct13-17-catchup.md))
- 2026-10-12 — Kit key (protocol 1.2): challenge/response + signed commands ([plan](plans/2026-10-12-kit-pairing-key.md))
- 2026-10-12 — Home page "AI slop" pass: demo above the fold, comparison table, DESIGN.md ([report](output/2026-10-12-2243-home-ai-slop-pass.md))
- 2026-10-12 — Home page + hash routing + new TR logo ([report](output/2026-10-12-2220-home-page.md))
- 2026-10-12 — Dashboard restyle: Fluent palette, Inter, floating cards ([report](output/2026-10-12-2131-dashboard-restyle.md))

## Open questions
- The real AWR1843 chirp config, which sets the encoder input (view, H, W, C). Who does the first capture, and when?
- Shoulder elevation is invisible to a front radar at chest height (sandbox). Elevation antennas or a different mount height, decided before data collection?
- One dashboard or two: merge `Phisit/` ideas (compensation risk, reps-to-compensation) into `frontend/`, or keep separate?
- Does `radar_ml_context.md` replace or adjust the Oct 5 plan? Phase 2 micro-vibration: a 1D phase branch?
- Team scope and roles; ethics approval for healthy volunteers?
- `CLAUDE.md` says macOS/zsh, but recent work runs on Windows (git user KINKIN-007, Oct 12 commits by Thor1006). Update the instruction?
- Home page copy sign-off; SF Rounded logo licence before any public poster. Poster says "oral health" (typo?).

## Next steps
1. Commit the Delete feature (8 files in `frontend/`) together with this report.
2. Get radar streaming and a first real capture (mmWave Studio + DCA1000). Write down the chirp config.
3. Set the real `InputContract` from that capture, then rerun `check_encoder.py`; try radar height or elevation for shoulder elevation.
4. Small fixes: the Reps panel keeps counting after a session stops (`sessionEvents` ignores `endedAt`); the Python bridge's `session_end` lacks `reps`; `sandbox/ml_Try-1.py` doesn't run.
5. When we really set up a Pi (**ask the user first** before installing packages): venv, all pi-bridge tests, `check_bridge.py --commands` and `--key … --auth-selftest`.
6. Write the real radar provider in `pi-bridge/providers/radar.py`; later a temporal block on `[B, T, E]` embeddings.
