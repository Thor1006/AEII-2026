# TrueRehab-RF — frontend

A live dashboard for the radar rehab prototype, written in TypeScript (Vite + React, no UI framework, plots drawn on canvas).

```
AWR1843 → DCA1000 ──Ethernet──► Raspberry Pi 5 (Python: capture, FFT, models)
                                  └─ WebSocket :8765 ──Wi-Fi──► this dashboard
Arduino (sEMG / force) ──USB──► Web Serial (Chrome / Edge) ───► this dashboard
Recorded .ndjson session ───────────────────────────────────────► this dashboard (replay)
```

> **No real data yet.** Demo mode, the mock server and the Pi bridge's synthetic provider send **made-up** data, and a "Demo data" banner says so. Score names, frame shapes and rates are placeholders until the real chirp config and models exist.

**The easy way:** run the Python bridge on the Pi (`../pi-bridge/README.md`) and open `http://<pi>.local:8080`. The bridge serves this dashboard, and the page connects to its own Pi without any typing.

## Run

```bash
npm install
npm run dev        # http://localhost:5173 (also reachable on the LAN)
npm run mock       # optional: mock Pi bridge on ws://<this-mac>:8765
npm run typecheck
npm run build      # static files in dist/, can be served from the Pi
```

The page opens on a **start screen**: connect to a Pi, try demo data, or open a recording (an Arduino on this laptop is under "More options"). It connects automatically when:
- the page was served by a Pi bridge (it publishes `/truerehab-bridge.json`), or
- the URL has `?pi=<address>`, e.g. `http://localhost:5173/?pi=trh-kit-01.local`. Handy in a QR code.

Pis that connected before appear under "Recent". Two views: **Session** (what to do now, reps, scores) and **Technical** (radar map, data-stream health, connection numbers, reference signals, event log).

To test over Wi-Fi from a phone or tablet, run `npm run dev` and `npm run mock` on the Mac. Open `http://<mac-ip>:5173/?pi=<mac-ip>` on the other device. The page must be **http**. Browsers block `ws://` from https pages.

## Completed-session reports

Stopping a session opens a localized summary with repetitions, duration, score statistics and a full-session trend. Reopen it with **View session summary**, or expand **Saved sessions** to view an older report. The latest 5 completed summaries are saved, newest first, in this browser's localStorage (`trf-session-history`, versioned JSON). A sixth removes the oldest saved summary. Each entry opens its own frozen session data; CSV and printing use that selected report. History survives reloads, view changes and source changes. Duplicate session ID/start/device combinations are ignored. No report is sent to a server or shared between devices.

Records can contain the optional patient code and are visible to anyone using this browser. Clearing browser data removes them. If storage is blocked or full, the five-record history still works in memory and a warning advises downloading a copy. Malformed saved records are skipped with a warning rather than crashing the dashboard. Download CSV or choose **Print / Save as PDF** for a separate copy; PDF saving uses the browser's print dialog.

`src/state/SessionReport.ts` accumulates every valid score and rep event independently of the rolling live buffers. Trend display is bounded to 240 averaged points per score; first/last/mean use all received valid samples. Late joins, invalid values, gaps, and message loss are marked as partial data. Completed repetitions count received rep-end events. The device's counter is separate because it may include the current unfinished repetition; absent data is never presented as a measured zero. Synthetic reports are labelled as demo data, not clinical measurements. CSV quotes all fields, includes a UTF-8 BOM, and neutralizes formulas in external text.

Run `node scripts/check-session-report.cjs` for aggregation, long-session, duplicate, partial-data, reset, CSV, five-record eviction, persistence and damaged/unavailable storage tests.

## Languages

The header selector supports English (default), ไทย, and 繁體中文（香港）. The preference is saved as `trf-language` in localStorage, and `<html lang>` follows the selected language. Switching languages does not reconnect the data source or reset sessions.

`src/i18n/catalog.ts` contains canonical English messages and their Thai/Hong Kong Traditional Chinese translations; `messages.ts` provides the three dictionaries and interpolation. Each display component calls `useI18n()` and wraps its JSX output in `ui(...)`. This translates text, placeholders, tooltips and screen-reader labels while preserving input values, refs, handlers and sensor payloads. Canvas text calls `t(...)` directly. For a new component, follow that pattern and add its English text to the catalog. For a dynamic message, use named `{placeholders}`; never translate protocol keys or numerical units.

Run `node scripts/check-i18n.cjs` to check dictionary parity, placeholders, dynamic messages, preserved form values, event handlers, refs, code snippets and scientific units.

Product/hardware names, identifiers, scientific units, filenames, user-written markers and unrecognised custom text supplied by external kits remain as supplied. Chinese font fallbacks use installed Traditional Chinese fonts without downloading extra fonts. The interface continues to work when localStorage is unavailable (the preference then lasts only for the open page).

Localization file inventory:

- New: `src/i18n/I18n.tsx`, `src/i18n/catalog.ts`, `src/i18n/messages.ts`, `src/i18n/LanguageSelector.tsx`, `src/i18n/LanguageSelector.module.css`, `scripts/check-i18n.cjs`.
- App/header/fonts: `src/main.tsx`, `src/Root.tsx`, `src/App.tsx`, `src/home/Home.tsx`, `src/home/Home.module.css`, `src/styles/theme.css`.
- Display components: `src/components/EventList.tsx`, `HeatmapCanvas.tsx`, `Panel.tsx`, `RecommendationCard.tsx`, `ScoreGauge.tsx`, `Stat.tsx`, `TimeSeriesChart.tsx` (all in `src/components/`).
- Controls/forms/guide: `src/shell/Banners.tsx`, `ConnectionHelp.tsx`, `ConnectionPill.tsx`, `DeviceStrip.tsx`, `HelpGuide.tsx`, `PlaybackBar.tsx`, `SessionBar.tsx`, `SessionRecorder.tsx`, `SourceForm.tsx`, `StartScreen.tsx`, `ThemeToggle.tsx`, `ViewToggle.tsx` (all in `src/shell/`).
- Connected panels: `src/widgets/AuxWidget.tsx`, `EventLogWidget.tsx`, `LinkWidget.tsx`, `RadarWidget.tsx`, `RecommendationWidget.tsx`, `RepWidget.tsx`, `ScoresWidget.tsx`, `ScoreTrendWidget.tsx`, `StreamHealthWidget.tsx` (all in `src/widgets/`).
- Documentation: this `README.md`. Existing help-guide layout changes are retained; dependencies, sensor sources and protocol definitions are unchanged.

## Folder map

| Path | What |
|---|---|
| `src/sensor/protocol.ts` | Message types (the contract with the Pi). Start here. |
| `src/sensor/codec.ts` | Binary frame + JSON encode/decode |
| `src/sensor/sources/` | Inputs: `WebSocketSource`, `WebSerialSource`, `ReplaySource`, `MockSource` + registry |
| `src/state/` | `SensorStore` (bounded buffers, link stats, manifest, session), `describe.ts` (labels from the manifest, stream health), React provider/hooks |
| `src/components/` | Presentational components: data via props only |
| `src/widgets/` | Connected widgets: read the store, render components |
| `src/shell/` | Start screen, connection help, connection pill, device strip, session bar, banners, playback, recorder, theme |
| `src/lib/address.ts` | Turns "trh-kit-01.local" into a ws:// URL, recent addresses, auto-connect |
| `src/config/defaults.ts` | Fallback labels (used when the Pi sends no manifest), panel explainers, exercise list |
| `src/dashboard.config.ts` | The two layouts (Session, Technical): panels, sizes, props, ⓘ texts |
| `src/styles/theme.css` | Design tokens (colors, radius, fonts), light + dark |
| `mock-server/` | Node mock of the Pi bridge (synthetic, protocol 1.2, optional `KEY=`, `BREAK=` modes for testing the checker and the key check) |
| `samples/` | Arduino sketch and a Python bridge sketch |

## Customizing

- **Layout:** edit `layouts` in `src/dashboard.config.ts`. Add a view, or move panels between Session and Technical. `props` is type-checked against each widget. `info` is the ⓘ explanation.
- **Look:** edit tokens in `src/styles/theme.css`. Every component also accepts `className` and `style`.
- **Labels / language:** the Pi's `hello` manifest names everything, so change labels in the bridge. `src/config/defaults.ts` holds the fallbacks and the UI text. Thai works; the font stack includes Noto Sans Thai.
- **New score / signal / radar view:** add it to the provider's `manifest()` in the Pi bridge and send it. The dashboard picks it up with no frontend change.
- **New widget:** write a component in `src/widgets/` using `useSensorStore()`, then add it to the `widgets` map in `src/widgets/index.ts`. It's then usable in the config.
- **New input:** extend `BaseSource` (`src/sensor/SensorSource.ts`), call `this.emit(msg)`, and add a `SourceDefinition` to `src/sensor/sources/index.ts`. The picker builds its form from `fields`.
- **Colormap:** `registerColormap('mine', ['#000000', '#ff0000', '#ffffff'])` from `src/lib/colormaps.ts`.
- **Custom layout without the config:** import components and widgets directly inside `<SensorProvider>`.

## Kit key (protocol 1.2)

A kit can be protected with a 64-character key. Nothing is sent before the handshake:

1. Pi → `{"type":"challenge","nonce":"<32 hex>","kitId":"KIT-01"}`
2. page → `{"type":"auth","cnonce":"<32 hex>","proof":"<hex>"}` with `proof = HMAC-SHA256(key, "trf-client|nonce|cnonce|kitId")`
3. Pi → `{"type":"authok","proof":"<hex>"}` with `"trf-server|…"` in place of `"trf-client|…"`. The page checks it, so a fake Pi is caught. A wrong key gets `{"type":"autherr","error":"wrong-key"}` and close code 4401.
4. Then `hello` (with `"auth":"hmac-sha256"`) and the normal stream. `sessionKey = HMAC(key, "trf-session|nonce|cnonce")`.

Commands then look like `{"type":"command","id":1,"ctr":1,"payload":"{\"name\":\"marker\",\"args\":{}}","mac":"<hex>"}` with `mac = HMAC(sessionKey, "<ctr>|<payload>")`. `ctr` must keep increasing. The Pi signs nothing back and the stream isn't signed or encrypted. A kit with no key skips all this and says `"auth":"none"` in `hello`.

The page keeps keys per kit address in `localStorage` (`src/lib/keystore.ts`) and uses its own SHA-256/HMAC (`src/lib/hmac.ts`), because browsers don't offer `crypto.subtle` on plain `http://` pages. Tests: `node scripts/check-hmac.ts` (known answers) and `node scripts/check-auth.ts` (starts the mock with a key and tries every way in). To try the mock with a key: `KEY=$(node -e "console.log(require('crypto').randomBytes(32).toString('hex'))") npm run mock`.

## Protocol 1.1 (for whoever writes the Pi bridge)

The reference implementation is `../pi-bridge/`. Check any sender with `python pi-bridge/check_bridge.py <address> --commands`. 1.1 is backward compatible: a 1.0 sender (no `hello`) still works, with default labels.

Every message has an envelope:

| Field | Type | Meaning |
|---|---|---|
| `v` | int | Protocol major version (1) |
| `type` | string | `hello` · `frame` · `scores` · `event` · `aux` · `status` |
| `seq` | int | +1 per broadcast message per sender. Gaps count as drops. `-1` = not sequenced (`hello`) |
| `t` | number | Sensor timestamp, ms since epoch (Pi clock). Charts use this, not arrival time. |
| `src` | string? | Sender id; sequence numbers are tracked per sender |
| `kitId` | string? | Which kit, e.g. `KIT-01` |
| `sessionId` | string? | Set while a session runs |

**`hello`: the first message to each viewer.** It describes the sender and everything it will send:

```jsonc
{"v":1,"seq":-1,"t":1760000000000,"type":"hello","protocol":"1.1",
 "device":{"name":"TrueRehab kit 01","kitId":"KIT-01","bridgeVersion":"0.1.0"},
 "synthetic":false,
 "session":null,
 "manifest":{
   "frames":[{"view":"range_doppler","label":"Range–Doppler","shape":[64,64],"fps":20,"unit":"dB",
              "axes":{"x":{"label":"Velocity","unit":"m/s","min":-2,"max":2},"y":{"label":"Range","unit":"m","min":0,"max":3}}}],
   "scores":[{"key":"fatigue","label":"Fatigue","higherIsWorse":true,"thresholds":[0.4,0.7],"rateHz":4,"description":"…"}],
   "aux":[{"key":"emg_rms","label":"sEMG (biceps)","unit":"RMS","rateHz":100,"device":"arduino"}],
   "events":["rep_start","rep_end","compensation","recommendation","session_start","session_end","marker"],
   "actions":[{"key":"rest","label":"Rest","hint":"Take a break before the next set.","tone":"bad"}],
   "commands":["session.start","session.stop","marker"],
   "statusIntervalMs":1000}}
```

The dashboard labels itself from the manifest and checks that every listed stream arrives (Technical → Data streams). An aux channel's `device` links it to `status.devices`, so a missing Arduino shows as "Device off: Not plugged in" instead of an error.

**Commands (dashboard → Pi)** get an `ack` with the same id:

```jsonc
{"type":"command","id":3,"name":"session.start","args":{"exercise":"elbow_flexion","side":"right","targetReps":12,"userId":"U-0007"}}
{"type":"ack","id":3,"ok":true,"result":{"session":{"id":"S-1a2b","state":"running","exercise":"elbow_flexion","targetReps":12,"startedAt":1760000000000}}}
{"type":"command","id":4,"name":"marker","args":{"label":"Patient reports pain"}}
{"type":"ack","id":5,"ok":false,"error":"No session is running"}
```

After a successful command, send the resulting `event` (`session_start` / `session_end` / `marker`) and a fresh `status`, in sequence order. `userId` is a pseudonymous code, never a name.

**Text messages (JSON):**

```jsonc
{"v":1,"type":"scores","seq":12,"t":1760000000000,"scores":{"fatigue":{"value":0.42,"confidence":0.8},"quality":0.77}}
{"v":1,"type":"event","seq":13,"t":1760000000100,"kind":"rep_end","data":{"rep":5,"romDeg":104}}
{"v":1,"type":"event","seq":14,"t":1760000000100,"kind":"recommendation","data":{"action":"correct_posture","reason":"Trunk lean"}}
{"v":1,"type":"event","seq":15,"t":1760000000200,"kind":"compensation","data":{"pattern":"trunk_lean","severity":0.7}}
{"v":1,"type":"aux","seq":16,"t":1760000000200,"channels":{"emg_rms":0.31,"force_n":20.4}}
{"v":1,"type":"status","seq":17,"t":1760000001000,"fps":20,"synthetic":false,"clients":2,"cpuTempC":51.2,
 "session":{"id":"S-1a2b","state":"running","exercise":"elbow_flexion","startedAt":1760000000000},
 "devices":{"radar":{"state":"ok","label":"Radar"},"arduino":{"state":"missing","label":"Arduino (sEMG / force)","message":"Not plugged in"}}}
```

- Device `state` is `ok` · `missing` · `error` · `off`. `message` is shown to users, so write it in plain words.

- Scores are open keys, normally 0–1. A bare number is shorthand for `{value}`.
- Recommendation actions: `continue`, `correct_posture`, `reduce_load`, `rest`, `see_physio`. Others display with a humanized name.

**Radar frames: binary WebSocket message (`TRF1`)**

```
offset  size  content
0       4     ASCII "TRF1"
4       4     uint32 little-endian: header length N
8       N     UTF-8 JSON header: frame envelope without data, plus
              "view", "shape":[rows,cols], "dtype":"f32"|"u8"|"u16",
              optional "scale":[min,max] (integers), "unit", "axes", "frameIndex"
8+N     0–3   zero padding to a multiple of 4
...           rows*cols values, little-endian, row-major
```

Python:

```python
header = json.dumps({"v":1,"type":"frame","seq":seq,"t":time.time()*1000,
                     "view":"range_doppler","shape":list(m.shape),"dtype":"f32"}).encode()
pad = (-(8 + len(header))) % 4
ws.send(b"TRF1" + struct.pack("<I", len(header)) + header + b"\0"*pad + m.astype("<f4").tobytes())
```

Bandwidth: 64×64 float32 at 20 fps ≈ 2.6 Mbit/s; `u8` cuts that by 4×. Frames can also be sent as JSON with `data` as an array or base64 float32 (`"encoding":"base64-f32"`). That's fine for testing, but too heavy for live use.

**Round-trip time (optional):** the dashboard sends `{"type":"ping","id":n,"clientT":x}` every 2 s. Reply with `{"type":"pong","id":n,"clientT":x}` to show RTT.

`samples/python_bridge_sketch.py` is a minimal 1.0 sender. Use `../pi-bridge/` for real work.

## Web Serial (Arduino on this computer)

Chrome/Edge only. One sample per line, any of:

```
{"type":"aux","channels":{"emg":512}}
{"emg":512,"force":20.3}
emg:512,force:20.3
512,20.3            ← names from the "CSV columns" field
```

Timestamps use the host clock. See `samples/arduino_aux.ino`. If the Arduino is on the Pi instead, forward it as `aux` over the WebSocket.

## Recording and replay

**Record** saves the incoming stream as `.ndjson` (one message per line; frames as base64). Load it from the start screen with **Open a recording** to play it back at 0.25–4×. Frames take about 25 MB/min at 64×64, 20 fps. Untick "frames" to record only scores, events and aux.
