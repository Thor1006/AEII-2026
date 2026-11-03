# Project: TrueRehab-RF (AEII 2026)

<!-- Stable facts. Change rarely; log why in DECISIONS.md. -->

## What & why
A contactless AI system using 77-GHz mmWave radar to tell real movement recovery apart from fatigue-driven compensatory movement (shoulder elevation, trunk lean, reduced ROM) during physiotherapy. Aimed at home rehab (post-stroke, musculoskeletal, neuro patients) — supports physiotherapists, doesn't replace them. Entered in AEII 2026.

## Goals
- Near-term deliverable: bring up a real radar, receive a documented radar representation continuously on the notebook, and connect live or replayed data to the existing dashboard. The exact representation remains open until hardware testing.
- Long-term: radar-only edge prototype that scores muscle fatigue, movement quality and compensation, predicts upcoming compensation, and recommends an action (continue / correct posture / reduce load or ROM / rest / see physio).
- Development follows the proposal's 7 phases: 1 Proof of Concept (elbow flexion) → 2 Muscle Signal Investigation → 3 Compensation Detection → 4 Signal Fusion → 5 Temporal Prediction → 6 Personalization (personal fatigue–compensation signature) → 7 Demonstration System.

## Non-goals
- Replacing the physiotherapist.
- Body-worn sensors or cameras in the final product — sEMG/IMU/force/video are development & validation ground truth only.
- Patient trials in early phases (healthy volunteers first).

## Stack
- Submitted design (frozen): TI AWR1843BOOST radar + DCA1000EVM capture for raw ADC/I-Q. This remains in the already-submitted proposal/poster.
- Selected radar implementation (received and UART/live-graph verified 2026-11-02): **Plan B**, TI AWR2944PEVM 76–81-GHz EVM, PROC194 REV. A. User-approved official SBL/TDM flash+verify and QSPI boot passed (AWR2X44P/TDM/SDK 04.07.02.01); a matching TI profile produced 151 real frames independently parsed by TI's tool. User-approved custom local graph in `sandbox/radar-live-viewer/` now displays real measured 3D points at a selected 40-Hz target, with about 40 unique displayed frames/s and nominal 3.88-cm radial range separation (not calibrated accuracy); the selected fast profile omits the unused range-profile TLV. See `CLAUDE/output/2026-11-03-radar-rate-resolution.md`. TI's own GUI, Ethernet, custom complex/Range-Doppler output and AI remain unverified. DCA1000 remains excluded; XE125 is fallback history. See `CLAUDE/output/2026-11-02-local-live-radar-viewer.md`.
- Host/deployment: notebook for acquisition and development; **Raspberry Pi 5 8GB is REQUIRED for the prototype**, together with official cooling, 27-W USB-C power and the actually purchased 64-GB A2 microSD with Raspberry Pi OS (supersedes the initial 128-GB default). Prototype deployment follows notebook bring-up and performance testing. See `CLAUDE/plans/2026-10-18-plan-b-purchase-links.md` for sourced hardware links and optional accessories.
- Required validation hardware: MyoWare 2 Muscle Sensor DEV-27924, MyoWare Wireless Shield DEV-23387 and three 10-packs of SEN-12969 disposable electrodes. USB-A-to-C cables are conditional on what the team already owns.
- Other possible ground truth: IMU, force sensor/load cell, Arduino and phone camera (video pose).
- Separate user-approved car-style diagnostic demo at `/drive/` (2026-11-03), sourced from `sandbox/radar-car-demo/`, shares the existing real 40-Hz collector. Illustrative ego car and unclassified measured reflection groups, not vehicle/person/lane/path detection. Original Room map HTML remains intact. See `CLAUDE/output/2026-11-03-car-style-radar-demo.md`.
- Local diagnostic viewer also includes the user-approved fixed-board Room map (2026-11-03): bounded RAM-only accumulation of actual front-of-radar reflections, 30-s window, 10-cm display cells and three-frame persistence, with pause/clear and live-layer controls. This is an observed reflection map, not validated full room geometry or SLAM. See `CLAUDE/output/2026-11-03-fixed-radar-room-map.md`.
- Software depends on the selected radar: Acconeer A121/XM125 tools for Plan A; TI MMWAVE-MCUPLUS-SDK firmware and Ethernet output for Plan B. Python handles acquisition/processing and the TypeScript frontend provides the dashboard. The temporal model remains unlocked (CNN-LSTM, LSTM, TCN or Transformer candidates).

## Architecture
Radar measurement → signal processing (Range/Doppler FFT, micro-Doppler, spectrogram, body-region tracking)
→ features (muscle micro-motion/vibration · ROM/velocity/trajectory/symmetry · shoulder/trunk/asymmetry)
→ three models: Fatigue, Movement Quality, Compensation scores (validated against ground truth)
→ temporal AI (trend → predict compensation in the next reps) → personalization → recommendation → dashboard.

With AWR1843BOOST + DCA1000, FFT processing can start from captured raw ADC on the host. Plan A instead provides Acconeer-supported A121/XM125 outputs over USB, while Plan B runs initial FFT/detection on AWR2944P and sends reduced output over Ethernet. These inputs are not interchangeable; the encoder `InputContract` must be frozen from the selected real implementation output.

## Key paths
- `T-Proposal-Radar (1).docx` — the proposal (Thai); source of truth. Read-only.
- `AEII 2026. TrueRehab-RF Poster.pdf` — competition poster. Read-only.
- `message-2.txt` — team notes on the system structure and phase roadmap. Read-only.
- `CLAUDE/` — Claude workspace (context, decisions, reports, plans).
- `CLAUDE/plans/2026-10-18-hardware-procurement-options.md` — required validation equipment, Plan A/Plan B prices and purchase gates.
- `CLAUDE/plans/2026-10-18-awr2944-no-dca.md` — Plan B firmware/data-path details.
