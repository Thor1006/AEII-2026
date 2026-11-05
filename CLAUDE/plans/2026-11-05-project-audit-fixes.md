# Plan: project-wide check and clean-up, pushed as small commits

**Status:** done (2026-11-05, [report](../output/2026-11-05-2040-project-audit.md)); was approved (2026-11-05) with the user's choice **"Only the bug fixes"**: chunks 1 (warning only, the unused import stays), 4 (the config-file fix only; the model's workaround stays), 5 (test leaks only; the unused import stays), 6 and 8. Skipped: chunks 2, 3 and 7.
**Date:** 2026-11-05

## Why
The user asked: "optimize the codebase project wide and also check for any error and report back. Push it in a
frequent chunk not a big one."

## What the check ran (read-only)
- **Tests:**
  - `model/` 60 tests, `recorder/` 13, `radar-lab/` 6, `pi-bridge/` 26;
  - live-viewer packet and HTTP tests (the packet test needs `pyserial`: 17/17 with the recorder's Python; see report), room-map and car-geometry JS tests;
  - Encoder_0.1 check (17).
- **Front end:** typecheck, i18n, session-report, HMAC and auth checks, build.
- **Firmware:** compiled both IMU modes and both MyoWare sketches (no upload).
- **Code:** a static check of all 82 Python files; timing of the slowest tests; a profile of the dataset build on
  the real 75-s recording.

## Results
- **Pass:**
  - model 60/60, recorder 13/13, radar-lab 6/6, Encoder 17/17;
  - all front-end checks and the build;
  - room-map 11/11, car-geometry 11/11;
  - live-viewer packet test;
  - all 4 firmware builds (IMU Wi-Fi 75 %, IMU USB 25 %, MyoWare demo 81 %, record 83 % of flash), with no sketch
    warnings.
- **Real bugs:** `sandbox/ml_Try-1.py`.
  - It crashes at line 56: `make_model.paramerters`, a typo, and the function used instead of a model.
  - The built model is thrown away.
  - `make_model(...)` is used as if it were the model in 3 more places.
  - There's no `loss.backward()`, so it never learns.
  - It prints the answer for x² + 5 when it trains on x³ + 5.
  - The learning rate is 0.00001, too small to fit in 3,000 steps.
- **Warnings and clean-ups:**
  - `model/trnet/training.py` turns a tensor that still tracks gradients into a number (PyTorch warning in every
    training run).
  - `radar-lab/radarlab/cfg.py` leaves its config file open (ResourceWarning; the model works around it).
  - The `recorder` tests leave a fake Wi-Fi server's sockets and one session file open (test-only: the recorder
    itself closes its sockets).
  - Unused imports: `model/trnet/inference.py`, `recorder/pose_check.py`, `pi-bridge/.../server.py`,
    `sandbox/Encoder_0.1/frame_encoder.py`.
- **Slow:** one test (`test_overfits_a_tiny_batch`) takes 41 of the model suite's 55 s. The pipeline itself is fast
  (0.53 s for the real 75-s session, 40 % of it compressing the cache).
- **Duplicate code:** `model/demo.py` repeats what `trnet/inference.py` now does.
- **Can't run here (reported only, nothing installed):**
  - `pi-bridge` `test_protocol` needs `websockets`, which you paused until the Pi setup.
  - `Phisit/` backend tests need `fastapi`, and its front end has no `node_modules` (teammate's code).
  - `sandbox/radar-live-viewer/test_http.py` only works while the Windows viewer is running on 127.0.0.1:8766.
- **Repo housekeeping (reported only):**
  - an old worktree, `.claude/worktrees/project-build-setup-c2eb20` (branch `claude/project-build-setup-c2eb20` at
    ff70b11, Oct 17);
  - large tracked files: `TrueRehub-RF .pdf` (10.6 MB) and `sandbox/out/sim_dataset.npz` (2.3 MB, generated).

## Approach: one small commit + push per chunk
1. **model:** silence the tensor-to-number warning; drop the unused import.
2. **model tests:** make the tiny-batch overfit test fast (41 s → a few s) without weakening what it checks.
3. **model:** `demo.py` reuses `trnet/inference.py`.
4. **radar-lab + model:** close the config file properly, then remove the model's workaround.
5. **recorder:** tests close their fake server and sessions; drop the unused import in `pose_check.py`.
6. **sandbox:** fix `ml_Try-1.py`, keeping its questions and its idea, and fixing the 7 bugs.
7. **pi-bridge + sandbox Encoder:** drop the unused imports.
8. **Notes:** report, CONTEXT (`ml_Try-1.py` now runs), decisions if any.

Teammate-only code (`Phisit/`, the live-viewer HTTP test) is not changed.

## Risks / needs OK
- **Commits and pushes:** the user asked for small frequent ones. I run each chunk's tests before pushing it.
- **`ml_Try-1.py`:** it's your learning script. The fixes keep its structure and prompts, and each bug is explained
  in the report.

## How we'll verify
- Each chunk: its own tests pass before the commit (model 60, recorder 13, radar-lab 6, Encoder 17, `ml_Try-1.py`
  runs with input piped in), and no new warnings.
- At the end, everything again, with times.
