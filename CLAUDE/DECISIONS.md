# Decisions

<!-- Newest on top. One short entry per decision that someone might later ask "why did we do it this way?" about. -->

## 2026-10-12 — Home page first, with hash routing (no router library)
- **Decision:** `#/` is an Apple-style landing page (`frontend/src/home/`), `#/app` is the dashboard. `Root.tsx` picks the route. Opened from a Pi bridge or with `?pi=`, it skips the landing page and goes straight to the dashboard. The page's live preview runs its own nested `SensorProvider` with `MockSource`, so it never touches the real connection. See [plan](plans/2026-10-12-home-page.md).
- **Why:** The user needed something to present first; the old first screen was "Connect your kit". Two routes don't justify a router package, and the Pi-served page must still open on live data.
- **Alternatives:** A router library (heavier for two routes); making the connect screen prettier (no story, no demo); a static preview image (not live).

## 2026-10-12 — Logo: "TR" monogram, SF Rounded outlined to SVG, mono
- **Decision:** The header logo is a rounded-square tile with "TR" (SF Rounded Bold), drawn as an inline SVG in `frontend/src/App.tsx`. The letters are traced outlines, not text, so no font is needed. Mono colours that flip with the theme (`currentColor` tile, `var(--bg)` letters); no gradients.
- **Why:** The first logo (CSS-gradient arcs) was disliked, and the user wanted something other than blue. Outlines look identical on every device and offline on the Pi. Mono avoids a second bright colour next to the blue accent and the status colours.
- **Alternatives:** Pulse tile, joint angle, target rings, wave, "shape with a ghost" (true vs compensation) and coloured versions; Mistral (Adobe font, can't be bundled); live text in SF Rounded (only looks right on Apple devices).
- **Open risk:** Apple licenses SF fonts for Apple platforms, so using outlines of them in a public logo is a grey area. For a poster or product logo, redo it with a clearly licensed rounded font (e.g. Nunito).

## 2026-10-12 — Dashboard look: Fluent-style neutrals, Inter, floating rounded rectangles, no gradients
- **Decision:** Neutral greys + one blue accent (`#0f6cbd` light / `#479ef5` dark), muted green/amber/red only for status. Font: Inter + Noto Sans Thai, bundled with `@fontsource` so it works offline on the Pi. Every container is a floating card (layered `--float` shadow, 16px radius); small controls use 10px; no pills. No CSS gradients anywhere. All of it lives in `frontend/src/styles/theme.css`. See [plan](plans/2026-10-12-dashboard-restyle.md).
- **Why:** The first teal/cyan-on-navy palette looked like generic AI styling. The user chose the Microsoft-like direction and wanted a calm, clinical feel. Bundled fonts keep the Pi demo offline-safe.
- **Alternatives:** Apple-like or OpenAI-like neutrals; IBM Plex Sans; Google Fonts CDN (needs internet); frosted-glass surfaces (tried, dropped because there are no gradients to blur); real Liquid Glass refraction (Chromium-only SVG filter).

## 2026-10-11 — Protocol 1.1: the Pi describes itself; Python reference bridge
- **Decision:** Each Pi sends a `hello` with a manifest of every stream (labels, units, score direction, radar axes, device links, accepted commands). The dashboard labels itself from it and checks that each stream arrives. Commands (`session.start/stop`, `marker`) go back with `ack` replies. The reference Pi side is `pi-bridge/` (Python, `websockets`). It also serves the dashboard over HTTP, so users open `http://<pi>.local:8080` and nothing needs typing. `check_bridge.py` verifies any bridge. See [plan](plans/2026-10-11-easier-ui-and-pi-bridge.md).
- **Why:** Hardcoded labels in the web break as soon as the Pi changes. A manifest + checker proves the Pi sends everything the page needs. Serving the page from the Pi removes the hardest setup step.
- **Alternatives:** MQTT broker (from the multi-kit plan): deferred until 2+ kits; `kitId`/`sessionId` are already in the envelope. Keeping labels in the frontend config: drifts from the Pi.

## 2026-10-10 — Dashboard in TypeScript (replaces Streamlit), WebSocket protocol v1
- **Decision:** The dashboard is a Vite + React + TypeScript app in `frontend/` with no UI framework and canvas plots. Sensors reach it through one `SensorSource` interface: a WebSocket from the Pi bridge (binary `TRF1` radar frames + JSON for everything else, each with a seq number and Pi timestamp), Web Serial for an Arduino, or replay. See [plan](plans/2026-10-10-typescript-frontend.md).
- **Why:** The user asked for TypeScript and fully customizable components. Browsers can't receive UDP, so the Pi must speak WebSocket over Wi-Fi. Binary frames keep a 64×64 map at 20 fps around 2.6 Mbit/s. Sensor timestamps keep the plots right despite Wi-Fi jitter.
- **Alternatives:** Streamlit (from the Oct 5 plan: one language, but less control and a weaker live demo). JSON/base64 frames (about 4× heavier). A chart library (lock-in, slower for heatmaps).

## 2026-10-08 — Frame encoder v0.1 design (sandbox)
- **Decision:** A CNN frame encoder that accepts any input size (`[B,C,H,W]` gives `[B,E]`, E=128), with GroupNorm, pooling only while an axis stays ≥ 4, and an `InputContract` saved alongside the weights. It lives in `sandbox/Encoder_0.1/` (user choice) rather than the `truerehab-rf/` layout. See [plan](plans/2026-10-08-frame-encoder.md).
- **Why:** There is no real chirp config yet, so the input view and shape must stay open. Batches will be small. The contract stops a model being fed differently preprocessed data.
- **Alternatives:** A fixed range-Doppler input (could rule out micro-Doppler or range-time views). BatchNorm (unstable with small batches).

## 2026-10-05 — ML stack and 6-week scope (proposed to team)
- **Decision:** Python end to end: numpy/scipy processing, MediaPipe + LSL for labels and sync, scikit-learn baselines then a small PyTorch CNN, leave-one-subject-out evaluation, Streamlit demo. Scope to 15 Nov: Phase 1 + 3 working, Phase 2 exploratory, Phases 4–7 as demo/future work. See [plan](plans/2026-10-05-ml-plan-and-stack.md).
- **Why:** No data yet and ~6 weeks; data collection is the bottleneck. Small data favours simple models and strict subject-wise evaluation.
- **Alternatives:** MATLAB for processing (splits the codebase, harder on Pi 5); all 7 phases by Nov 15 (unrealistic without multi-session data).

## 2026-10-05 — Adopted CLAUDE/ workspace via /initiate-project
- **Decision:** Keep project context, decisions, session reports and plans in `CLAUDE/`; root `CLAUDE.md` points to it.
- **Why:** Every session starts oriented and leaves a trail.
- **Alternatives:** A single root CLAUDE.md — gets long and mixes stable facts with changing state.
