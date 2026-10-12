# Plan: Easier dashboard setup + a Pi bridge that sends everything the web needs

**Status:** approved (in progress: code written; Python side untested, see [report](../output/2026-10-11-1828-easier-ui-pi-bridge.md))
**Date:** 2026-10-11

## Why
1. **The UI is hard to set up and read.** You have to know a `ws://` URL and pick a source from a dense header. Panels use radar jargon ("range–Doppler", "rtt", "drop 0.0%"). When a connection fails, nothing says why or what to do.
2. **Labels are hardcoded.** The web assumes things the Pi never tells it: score names and directions, aux channel names and units, frame axes, and whether data is synthetic. There's also no way to send commands back (start/stop a session, set a rep target). If the Pi sends anything else, the UI shows it wrong or not at all.
3. **No real Pi-side code exists.** Only a Node mock and a Python sketch, so nothing proves the Pi sends a complete, valid stream.

## Approach

### A. Protocol v1.1 (backward compatible): the Pi describes itself
- **`hello` message** (Pi → web, first message after connect): device and kit identity (`kit_id`, `device_name`, firmware/bridge version), a `synthetic` flag, and a **manifest** of what it will send:
  - `frames`: one entry per view, with shape, axes and units, dtype and fps
  - `scores`: key, label, `higherIsWorse`, thresholds
  - `aux`: channel, label, unit, expected rate
  - `events`: the kinds it emits; `actions`: the recommendation actions it can send
  - `commands`: the commands it accepts
  - The UI builds its labels, gauges, axes and charts **from the manifest**. `config/defaults.ts` becomes the fallback.
- **Commands** (web → Pi), each with an `ack`/`error` reply: `session.start {session_id?, exercise, side, target_reps, user_id?}`, `session.stop`, `marker {label}` (tag a moment), `ping`. The Pi includes `session_id` in its messages. This matches the identity fields in the `multi-kit-identity` plan.
- **Richer `status` heartbeat (1 Hz):** `radar` / `dca1000` / `arduino` / `model` each `ok | missing | error` with a message, capture fps, DCA packet loss, CPU temperature, session state.
- **Stream health on the web:** compare what arrives against the manifest. Example: "Scores: none for 5 s, the Pi says it sends them" → shown as a clear warning.

### B. Reference Pi bridge: `pi-bridge/` (Python)
- `protocol.py`: dataclasses + encoders matching the TS types (one source of truth: the README spec).
- `server.py`: a `websockets` server that sends `hello`, a heartbeat and pong, handles commands, and **also serves the built dashboard over HTTP**. Open `http://trh-kit-01.local:8080` and the page connects to its own Pi automatically, so there's **no URL to type**.
- `providers/`: one interface `DataProvider` with `start()`, `stop()` and async iteration of messages. It ships with:
  - `SyntheticProvider` (Python port of the mock, clearly flagged synthetic) so the bridge runs today
  - `SerialAuxProvider` (Arduino on the Pi → `aux`, using pyserial)
  - `RadarProvider` **stub** with TODOs where the team plugs in DCA1000 capture + FFT + model. I won't invent radar processing.
- `config.example.toml`: port, kit_id, which providers are on.
- `check_bridge.py` **conformance checker**: connects to any bridge, then validates hello and manifest, every message type, seq continuity, timestamps, frame byte layout, and that each manifest stream actually arrives. Prints a pass/fail list. Run it against the real bridge on the Pi before a demo.
- A `systemd` unit file so the bridge starts on boot (documented; not installed by me).

### C. Easier UI
- **Start screen** (when not connected) with 3 big choices, each with a one-line explanation:
  - **Connect to Pi**: prefilled with the page's own host when served from the Pi. Otherwise it remembers recent addresses and accepts `?pi=` in the URL, so a QR code can carry it.
  - **Try demo data**
  - **Open a recording**
  - Arduino-on-laptop goes under "More options".
- **Connection checklist with plain-language errors:** "Can't reach the Pi → Is it on the same Wi-Fi? Is the bridge running? (`systemctl status truerehab-bridge`)", "This page is https: open the http address instead", "Pi uses an older protocol version".
- **Two views, toggled in the header:**
  - **Session** (default): big recommendation, rep counter, three score gauges with "lower is better" hints, trend, and Start/Stop session buttons.
  - **Technical**: radar map, ground-truth signals, link stats, stream health, events.
- **Plain words everywhere:** "Connected · signal good" instead of fps/rtt numbers (numbers on hover), an ⓘ explainer on each panel (e.g. what a range–Doppler map shows), and a device-status strip (Radar ✓ · Arduino ✗ "not plugged in" · Model ✓) from the heartbeat.
- **Session setup:** the Start button opens a small form (exercise, side, target reps) and sends `session.start`.

### D. Docs
- README rewritten as "Setup in 5 steps" (flash nothing; install bridge, start, open address) + protocol v1.1 reference.
- The Node mock server sends hello/status/acks too, so frontend-only development still works.

## Files touched
- `frontend/src/sensor/protocol.ts`, `codec.ts`: hello, manifest, commands, ack, status v1.1 (old v1 senders still work).
- `frontend/src/sensor/sources/WebSocketSource.ts`: `send(command)` with ack promise; store the hello.
- `frontend/src/state/`: manifest, device status, stream health.
- `frontend/src/shell/`: new `StartScreen`, `ConnectionHelp`, `DeviceStatus`, `SessionControls`, `ViewToggle`; the source picker moves into the start screen and "More options".
- `frontend/src/widgets/`, `components/Panel.tsx`: read labels from the manifest; add an info tooltip.
- `frontend/src/dashboard.config.ts`: two layouts (`session`, `technical`).
- `frontend/mock-server/server.ts`: hello, status, command handling.
- New `pi-bridge/`: `server.py`, `protocol.py`, `providers/*.py`, `check_bridge.py`, `config.example.toml`, `truerehab-bridge.service`, `requirements.txt`, `README.md`.

## Risks / needs OK
- **Overlaps the `multi-kit-identity` plan (still `proposed`).** That plan suggests MQTT. I recommend **direct WebSocket to each Pi for now** (fine for 1–2 kits at AEII). I'll keep `kit_id` / `session_id` in the protocol so the same messages can move to MQTT later. I'm not building the kit files, udev rules or the Arduino handshake from that plan here.
- **Python packages to install** (I'll ask first): `websockets`, `numpy`, `pyserial`, in a venv at `pi-bridge/.venv`. Your Mac has Python 3.14; the Pi (Bookworm) has 3.11, so I'll keep the code 3.11-compatible.
- I can't test on a real Pi, radar or Arduino. I'll test the bridge on the Mac with the synthetic and loopback providers.
- Scope is fairly large. If you want it smaller, do **B + the hello/manifest part of A** first (the "Pi sends everything" half), then C.

## How we'll verify
- `npm run typecheck` + `build` pass.
- `check_bridge.py` passes against both the Python bridge and the Node mock. It must fail on purpose-broken cases: missing hello, bad frame layout, a stream in the manifest that never arrives.
- Browser pane: load the page **served by the Python bridge**. It must connect with zero typing, show labels from the manifest (change a label in the Python config → the UI changes), Start/Stop session round-trips with an ack, and stopping the bridge shows the plain-language help. Check phone width.
