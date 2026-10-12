# Plan: TypeScript frontend (dashboard) with live sensor input

**Status:** done
**Date:** 2026-10-10

## Why
The user wants the dashboard in TypeScript instead of Streamlit (Oct 5 plan). It must take live sensor input. Every component should stay open for later customization, because heads, input views and scores aren't fixed yet.

## Key constraint (read first)
A browser **cannot** read the DCA1000 directly. It streams raw UDP and needs mmWave Studio / a Python receiver plus FFT processing. So "input from the sensor" means:

```
AWR1843 → DCA1000 → Python receiver + processing + model (future)  ──WebSocket──►  web app
Arduino (sEMG / force) ──USB serial──► Web Serial API (Chrome/Edge only)  ───────►  web app
Recorded session file (.json / .ndjson) ─────────────────────────────────────────►  web app
```

**Raspberry Pi over Wi-Fi:** the Pi 5 runs the bridge. It takes DCA1000 data over wired Ethernet, processes it, and serves a WebSocket on the LAN (`ws://<pi>.local:8765`). Any browser on the same Wi-Fi connects to it. Browsers can't receive raw UDP, so the Pi must speak WebSocket. Protocol changes this needs:
- Radar frames go as **binary** WebSocket messages (header + Float32 or uint8 array), not JSON/base64. Example: a 64×128 float32 map at 20 fps ≈ 5 Mbit/s, which Wi-Fi handles. Raw ADC over Wi-Fi is not supported.
- Every message carries the **Pi's timestamp + sequence number**. Plots use sensor time, not arrival time (Wi-Fi jitter), and gaps show as dropped frames.
- Auto-reconnect with backoff. Show latency and drop rate in `ConnectionStatus`.
- If the Arduino is plugged into the Pi, its data comes in as `aux` messages over the same socket. Web Serial is only for an Arduino plugged into the laptop.
- Serve the page over plain http on the LAN (or from the Pi). An https-hosted page can't open `ws://` to the Pi.

The frontend defines one typed message **protocol** and a `SensorSource` interface. Each input above is an adapter. The Python bridge isn't built yet. A small Node mock server speaks the same protocol, so the WebSocket path can be tested today.

## Approach
1. **Stack:** Vite + React 18 + TypeScript (strict). No UI framework. Styling uses CSS variables (theme tokens) + CSS modules, so restyling = editing tokens. Plots are drawn on plain `<canvas>` (heatmap, line), so there's no chart lib lock-in and it's fast enough for ~10–30 fps maps.
2. **Protocol (`src/sensor/protocol.ts`):** versioned, discriminated union:
   - `frame`: radar map (range-Doppler / micro-Doppler / range-time), `{view, shape:[H,W], data: number[] | base64 Float32}`, timestamp, frame index
   - `scores`: open `Record<string, number>`, e.g. fatigue / quality / compensation, each 0–1 with an optional confidence. Keys aren't hard-coded.
   - `event`: rep start/end, compensation flag, recommendation (`continue | correct_posture | reduce_load | rest | see_physio`)
   - `aux`: ground-truth channels (sEMG, force, joint angle) as named scalar samples
   - `status`: source health (fps, packet loss, connected)
3. **Sources (`src/sensor/sources/`):** `SensorSource` interface (`connect / disconnect / onMessage / status`) with adapters:
   `WebSocketSource` (Python bridge or mock), `WebSerialSource` (Arduino lines → `aux`), `ReplaySource` (load a recorded file, play/pause/speed), `MockSource` (in-browser synthetic data).
   A registry lets new adapters be added without touching the UI.
4. **State:** a small store (React context + ring buffers) holding the latest frame, score history and events. History has a fixed capacity, so memory stays bounded.
5. **Components (`src/components/`)**, all props-driven with `className` / `style` overrides, render-prop or slot where useful:
   `SourcePicker`, `ConnectionStatus`, `HeatmapCanvas` (any H×W map, pluggable colormap), `TimeSeriesChart` (multi-series), `ScoreGauge`, `ScoreTrend`, `RecommendationCard`, `RepCounter`, `EventLog`, `AuxSignalPanel`, `SessionRecorder` (save incoming stream to .ndjson for replay), `Panel` (layout shell).
6. **Layout:** a `dashboard.config.ts` lists which panels show and in what order. Adding/removing a panel is a config edit.
7. **Mock server:** `mock-server/` (Node + `ws`) sends synthetic frames, scores and events at a set fps. It's clearly labelled synthetic.
8. **Docs:** `frontend/README.md` covers how to run it, the protocol spec (for whoever writes the Python bridge) and how to add a component or source.

## Files touched
- New `frontend/` at project root (Vite app + `mock-server/`). Nothing else changes except CLAUDE/ bookkeeping.

## Risks / needs OK
- **Changes the Oct 5 decision** (Streamlit → TypeScript). Trade-off: more control and a nicer demo, but a second language beside Python, and a Python WebSocket bridge is still needed for live radar. Will log in DECISIONS.md.
- **Web Serial** works only in Chrome/Edge, not Safari/Firefox.
- No real data yet. Frame shapes, score names and the message rate are placeholders. The protocol is versioned so it can change.
- Location `frontend/`, not `truerehab-rf/dashboard/` (that repo layout doesn't exist yet). Say if you want it elsewhere.
- Needs `npm install` (React, Vite, TypeScript, ws). It downloads packages from npm.

## How we'll verify
- `npm run typecheck` and `npm run build` pass with no errors.
- Run the mock server + dev server. In the browser pane, check that the heatmap, scores, trend and events update live over WebSocket. Then check that MockSource and ReplaySource (a recorded file) work too.
- Web Serial: can only check that the UI path loads (no Arduino attached here).
