# Plan: FMCW chain + ML example sandbox (learning, no hardware)

**Status:** approved
**Date:** 2026-10-07

## Why
The user wants to see the FMCW processing chain and an example ML model as runnable code, to work out what they need to learn, before any hardware work. They asked for it directly ("write the chain into this folder for now").

## Approach
1. `sandbox/fmcw_chain.py`: example radar config, a point-reflector body simulator (trunk, shoulder, arm, dumbbell, breathing, shoulder elevation, trunk lean), and the processing chain: range FFT, static removal, Doppler FFT, range-azimuth, CA-CFAR, micro-Doppler, phase displacement. Demo figures go to `sandbox/out/`.
2. `sandbox/ml_example.py`: synthetic dataset (8 simulated subjects × 3 conditions: correct / shoulder elevation / trunk lean). Baseline is logistic regression on hand-crafted features; then a small 2D CNN with AdamW. Leave-one-subject-out evaluation.
3. `sandbox/README.md`: how to run, plus a learning map (concept → where it appears in the code).
- Uses only numpy, matplotlib and torch (already installed). No installs.

## Files touched
- `sandbox/` (new): learning code only, not the future repo layout.

## Risks / needs OK
- The example config is not the real AWR1843 profile. Nothing touches hardware.
- Synthetic accuracy says nothing about real-data performance; this is stated in the code and README.

## How we'll verify
- Chain demo: the micro-Doppler track matches the simulated hand velocity; the phase method recovers simulated breathing; CFAR finds the body.
- ML example runs end to end and prints per-fold LOSO results.
