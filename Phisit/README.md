# TrueRehab-RF

A presentation-ready research prototype for contactless rehabilitation monitoring. It shows a standing biceps curl, a synthetic 77-GHz-class radar stream, peak-detected repetitions, changing movement indices, and a demo rule-based recommendation. The system distinguishes **current compensation level** from **future compensation risk**; in the demonstration, risk rises first.

All radar imagery and AI-derived values are **simulated**. There is no trained model, physical radar connection, measured muscle fatigue, or clinical validation in this release. The site does not use a camera.

## Run locally on Windows

This folder contains the complete TrueRehab-RF simulation prototype. Install Node.js 20+ and Python 3.11+, then open PowerShell in the repository's `Phisit` folder and run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm ci
```

If the `py` launcher is unavailable, run the installed Python executable with `-m venv .venv` instead.

For the simplest exhibition run, build and serve both the dashboard and API from one process:

```powershell
.\scripts\start-local.ps1
```

Open **http://127.0.0.1:8000/**. The same server exposes the REST API and WebSocket stream. Stop it with Ctrl+C.

For frontend development, use two PowerShell terminals:

```powershell
# Terminal 1
.\scripts\start-backend.ps1

# Terminal 2
.\scripts\start-frontend.ps1
```

Open **http://127.0.0.1:5173/**. Vite proxies `/api` and `/ws` to FastAPI on port 8000.

## Demo controls

- **Start** begins a new synthetic curl sequence (or resumes a stopped one). The movement waveform runs at roughly one cycle per three seconds. A peak detector counts each repetition.
- **Stop** pauses the stream and preserves the session; **Reset** clears it.
- **Export CSV** downloads every recorded telemetry frame after a session has begun. **Save** writes `data/sessions/<session_id>/telemetry.csv` and `session.json` through the Python backend.
- **Exhibition Mode** enlarges the essential story and hides development information. **How It Works** explains the conceptual pipeline and scientific limits.
- The **Developer Details** panel exposes stream and session diagnostics. Hardware and ground-truth sensor statuses are explicitly marked simulated or disconnected.

The [private hosted demonstration](https://truerehab-rf-demo-2026.paragon-chat-0642.chatgpt.site) uses a browser-local simulation adapter because Sites hosts the static frontend, not a persistent Python service. It presents the same telemetry contract and can export CSV; its Save action stores a demo session in that browser's local storage. For backend streaming and files on disk, run the application locally as above. Installed dependencies, recorded sessions, temporary test outputs, and account-specific Sites hosting metadata are excluded from this GitHub copy.

## Data and architecture

`backend/app/schemas.py` and `src/telemetry/types.ts` define the shared telemetry shape. The React UI reads only that shape. `src/telemetry/backendSource.ts` receives frames over `/ws/telemetry`; `src/telemetry/browserSource.ts` implements the same source interface for static demos.

The Python flow is:

```text
RadarSource → SignalProcessor → AIModel → recommendation rule → TelemetryFrame → WebSocket → React
```

`SimulationRadarSource`, `SimulationSignalProcessor`, and `SimulationAIModel` provide the current illustrative stream. `DCA1000RadarSource` and `PyTorchAIModel` are deliberate placeholders that raise `NotImplementedError`; they cannot silently imply hardware support. The architecture is model-agnostic and can add subject-specific calibration and synchronized IMU/sEMG reference data after dataset collection.

REST endpoints: `/api/health`, `/api/state`, `POST /api/session/start`, `POST /api/session/stop`, `POST /api/session/reset`, `GET /api/session/export.csv`, `POST /api/session/save`. WebSocket endpoint: `/ws/telemetry`. Interactive API documentation: **http://127.0.0.1:8000/docs**.

`sample-data/demo-session.csv` is an illustrative ten-repetition story, not recorded human or radar data. Live CSV exports contain sampled frames, not only rep peaks.

## Checks

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
cd backend
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd ..
npm run build
```

The browser QA also covers Python WebSocket connection, waveform-based rep counting, Stop, Reset, CSV download, Save, the explanation modal, exhibition mode, and desktop/mobile overflow.

## Scientific boundary

Future hardware can provide raw ADC/I-Q samples from the TI AWR1843BOOST through DCA1000EVM. Signal processing, feature extraction, data collection, subject calibration, and trained temporal AI still require implementation and validation. Current fatigue, quality, compensation, risk, and recommendation values are hand-designed simulation outputs, not direct radar measurements or medical advice.
