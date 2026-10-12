# Project: TrueRehab-RF (AEII 2026)

<!-- Stable facts. Change rarely; log why in DECISIONS.md. -->

## What & why
A contactless AI system using 77-GHz mmWave radar to tell real movement recovery apart from fatigue-driven compensatory movement (shoulder elevation, trunk lean, reduced ROM) during physiotherapy. Aimed at home rehab (post-stroke, musculoskeletal, neuro patients) — supports physiotherapists, doesn't replace them. Entered in AEII 2026.

## Goals
- Near-term deliverable: not decided yet.
- Long-term: radar-only edge prototype that scores muscle fatigue, movement quality and compensation, predicts upcoming compensation, and recommends an action (continue / correct posture / reduce load or ROM / rest / see physio).
- Development follows the proposal's 7 phases: 1 Proof of Concept (elbow flexion) → 2 Muscle Signal Investigation → 3 Compensation Detection → 4 Signal Fusion → 5 Temporal Prediction → 6 Personalization (personal fatigue–compensation signature) → 7 Demonstration System.

## Non-goals
- Replacing the physiotherapist.
- Body-worn sensors or cameras in the final product — sEMG/IMU/force/video are development & validation ground truth only.
- Patient trials in early phases (healthy volunteers first).

## Stack
- Hardware: TI AWR1843BOOST radar + DCA1000EVM capture (raw I/Q/ADC); notebook for development → Raspberry Pi 5 for final edge AI.
- Ground truth: sEMG, IMU, force sensor/load cell, Arduino, phone camera (video pose).
- Software: not decided yet. Model is deliberately not locked (candidates: CNN, CNN-LSTM, LSTM, TCN, Transformer).

## Architecture
Radar raw signal → signal processing (Range/Doppler FFT, micro-Doppler, spectrogram, body-region tracking)
→ features (muscle micro-motion/vibration · ROM/velocity/trajectory/symmetry · shoulder/trunk/asymmetry)
→ three models: Fatigue, Movement Quality, Compensation scores (validated against ground truth)
→ temporal AI (trend → predict compensation in the next reps) → personalization → recommendation → dashboard.

## Key paths
- `T-Proposal-Radar (1).docx` — the proposal (Thai); source of truth. Read-only.
- `AEII 2026. TrueRehab-RF Poster.pdf` — competition poster. Read-only.
- `message-2.txt` — team notes on the system structure and phase roadmap. Read-only.
- `CLAUDE/` — Claude workspace (context, decisions, reports, plans).
