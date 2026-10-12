# Report: TypeScript frontend with live sensor input

**Date:** 2026-10-10 21:54 · **Result:** ✅ done · **Plan:** [2026-10-10-typescript-frontend.md](../plans/2026-10-10-typescript-frontend.md)

## Goal
Build a customizable TypeScript dashboard that takes sensor input, including from a Raspberry Pi over Wi-Fi.

## What changed
- `frontend/` (new): Vite + React 18 + TypeScript (strict), no UI framework, plots drawn on canvas.
  - `src/sensor/protocol.ts`, `codec.ts`: protocol v1. JSON for scores, events, aux and status. Binary `TRF1` for radar frames (f32/u8/u16). Every message carries a sequence number and a sensor timestamp.
  - `src/sensor/sources/`: WebSocket (Pi bridge, auto-reconnect, ping/RTT), Web Serial (Arduino, 4 line formats), Replay (.ndjson), Mock (synthetic). A registry builds the source picker's form from each source's fields.
  - `src/state/`: `SensorStore` with bounded ring buffers, drop and fps stats, rAF-throttled hooks.
  - `src/components/`: presentational components that take data through props only. `src/widgets/` holds the connected versions. `src/dashboard.config.ts` sets the layout and is type-checked against each widget's props.
  - `src/config/defaults.ts`: labels, thresholds and recommendation text. `src/styles/theme.css`: design tokens for light and dark.
  - `mock-server/server.ts`: synthetic Pi bridge (env vars `FPS`, `DTYPE`, `DROP`). `samples/`: Arduino sketch and Python bridge sketch.
  - `README.md`: how to run it, the protocol spec for the Python side, and how to customize it.
- `.claude/launch.json`: preview configs `frontend` and `mock-bridge`.

## Verified by
- `npm run typecheck` (app + Node) and `npm run build` pass.
- Browser pane: the in-browser mock and the WebSocket mock bridge both update live. WebSocket ran at 19.6 fps with 0% drops and RTT shown. No console errors. Checked at 1440 px and 375 px (no horizontal scroll).
- Node script: binary round-trip error is f32 0, u16 3e-4, u8 0.08 dB. NDJSON round-trip, score shorthand, all serial line formats, the drop counter (5 messages with a gap of 2 → 2 counted), and replay at 4× (135/135 messages) all pass.

## Issues / not done
- Web Serial was not tested with real hardware (no Arduino attached). It needs Chrome or Edge.
- Replay's file picker was not clicked through in the browser. Replay logic was tested in Node only.
- All data is synthetic. Frame shape, score names and rates are placeholders.
- npm skipped esbuild's postinstall script (allowScripts). The build works anyway.

## Next
1. Write the real Python bridge on the Pi using `samples/python_bridge_sketch.py` and the README protocol.
2. Once the chirp config is known, set real axes, units and shape in the frame header.

**Uncommitted work:** yes, not a git repo yet.
