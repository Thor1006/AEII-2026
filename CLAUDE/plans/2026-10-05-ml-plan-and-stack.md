# Plan: TrueRehab-RF — ML plan & stack (to Nov 15, 2026)

**Status:** approved
**Date:** 2026-10-05

## Context
The team has a proposal and a poster, but no code, no data and no assigned roles. The next hard deadline is **15 Nov 2026, about 6 weeks away**. The user wants a concrete ML plan and stack they can bring to the team. Their level is basic PyTorch training (Adam), and they work with a partner who knows the field well.

**Honest scope call:** 6 weeks from zero data can't produce all 7 phases. Realistic target:
- **Phase 1 (detect elbow flexion) + Phase 3 (compensation detection): working**, with real results.
- **Phase 2 (fatigue from radar): exploratory**, showing correlations against sEMG and force, not a validated model.
- **Phases 4–7: a demo dashboard plus "future work".** Temporal prediction and personalization need many sessions per person that we won't have.

Data is the bottleneck, not models. About half the time goes to getting clean, synced, labelled recordings.

## Stack (recommended)
| Layer | Choice | Why |
|---|---|---|
| Language/env | Python 3.11+, `uv` (or conda), git + GitHub | One language from capture to Pi 5 |
| Radar capture | TI **mmWave Studio** + DCA1000 first; move to Python capture (OpenRadar / `mmwave` UDP reader) once it works | Studio is the known-good path. Note: the AWR1843 may need firmware/SOP changes, which is a human step, not Claude's |
| Signal processing | numpy, scipy (+ OpenRadar helpers) | Range FFT, Doppler FFT, micro-Doppler spectrograms (STFT) |
| Ground truth | Phone video → **MediaPipe Pose** (joint angles, shoulder height, trunk lean). sEMG/force via Arduino → serial CSV. IMU optional | Video gives cheap automatic labels for movement and compensation |
| Sync | **LSL (`pylsl`)** for shared timestamps + a physical sync event (clap/tap visible in all streams) at session start | Sync errors silently ruin labels |
| Data format | One folder per session: raw `.bin`, processed `.npz`/HDF5, `meta.json` (subject, exercise, condition, rep markers) | Reproducible, easy to split by subject |
| Exploration | Jupyter + matplotlib | Look at the signals before modelling |
| Baseline ML | scikit-learn (+ XGBoost): hand-crafted features → classifier | Fast, interpretable, works on small data |
| Deep learning | PyTorch: small 2D CNN on micro-Doppler / range-Doppler windows; CNN-LSTM later | Matches the proposal's candidates; keep models small (little data) |
| Evaluation | **Leave-one-subject-out** (`GroupKFold`) | The #1 trap: random splits leak the same person into train and test and inflate accuracy |
| Tracking | YAML config per run + results CSV (MLflow optional) | Simple enough for a student team |
| Edge | Export to ONNX → `onnxruntime` on Raspberry Pi 5 | Only if time allows; otherwise run on the notebook for the demo |
| Dashboard | Streamlit (replay a recorded session; live if capture is ready) | Demo in days, not weeks |

## Proposed repo layout
```
truerehab-rf/
  capture/        radar + Arduino + LSL recording scripts
  processing/     range/doppler/micro-doppler, MediaPipe labelling, sync
  datasets/       build windows + labels from sessions
  models/         sklearn baselines, PyTorch CNN
  eval/           LOSO evaluation, metrics, plots
  dashboard/      Streamlit app
  notebooks/      exploration only
  data/           (gitignored) raw + processed sessions
  configs/
```

## Experiment protocol (v1, healthy volunteers)
- **Exercise:** seated elbow flexion with a light dumbbell, radar at a fixed position and distance (record it).
- **Conditions per subject:** (a) correct form, (b) scripted shoulder elevation, (c) scripted trunk lean, (d) repetitions to failure (fatigue) with sEMG on the biceps if available.
- **Target:** 8–12 subjects × all conditions. Log RPE (perceived exertion) every few reps.
- **Caveat to state in results:** scripted compensation isn't fatigue-driven compensation. The proposal itself lists "separating fatigue from intentional posture change" as a challenge.
- **Ethics check first:** ask the advisor whether the institution needs ethics approval or a consent form even for healthy volunteers.

## Timeline
| Week | Dates | Goal | Done when |
|---|---|---|---|
| 1 | Oct 6–12 | Repo/env, radar streaming via mmWave Studio, first raw capture | Range-FFT plot shows a moving arm |
| 2 | Oct 13–19 | Processing pipeline (range-Doppler, micro-Doppler), MediaPipe labels, LSL sync | One session: radar spectrogram and video joint angle line up in time |
| 3 | Oct 20–26 | Data collection v1 (protocol above) | ≥ 8 subjects recorded, metadata complete |
| 4 | Oct 27–Nov 2 | Phase 1: rep detection + ROM from radar vs video. Phase 3: sklearn compensation classifier, LOSO | Baseline numbers (rep-count error, ROM error, compensation F1) |
| 5 | Nov 3–9 | PyTorch CNN on spectrograms vs baseline. Phase 2 exploration: radar features vs sEMG median frequency / rep index | Comparison table; fatigue correlation plots |
| 6 | Nov 10–15 | Streamlit dashboard (replay), results figures and slides, freeze code | Demo runs end-to-end on a recorded session |

## Suggested split (roles are open)
- **Partner (domain expert):** radar configuration and signal processing (weeks 1–2), protocol and physiology checks.
- **You:** data pipeline + labelling (MediaPipe, sync, dataset builder), then the sklearn → PyTorch models and LOSO evaluation. This stretches your current PyTorch level just enough.
- **Others:** data collection logistics, Arduino/sEMG, dashboard, slides.

## Risks
- Radar capture setup slips (most likely). Mitigation: start week 1 on day 1. If capture is blocked, develop the processing code on TI or public sample data in parallel.
- Too few subjects. Mitigation: windowed samples per rep, small models, sklearn first.
- The fatigue signal in radar may be weak. This is a research question, and a null or partial result is still reportable.

## Verification
- Every stage has a "done when" check (table above) that can be shown to the team.
- Model results are reported only with leave-one-subject-out, next to a trivial baseline (majority class / video-free heuristic).
- Final check: the dashboard replays one held-out subject's session end-to-end.

## After approval
Save this as `CLAUDE/plans/2026-10-05-ml-plan-and-stack.md` (status `approved`) in the AEII-2026 project. Log the stack choice in `CLAUDE/DECISIONS.md`. No code until the team agrees.
