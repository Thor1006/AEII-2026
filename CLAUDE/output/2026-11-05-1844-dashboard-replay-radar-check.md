# Report: the model in the dashboard (replay) and a first radar check

<!-- Filename: YYYY-MM-DD-HHMM-<slug>.md -->

**Date:** 2026-11-05 18:44 · **Result:** ⚠️ partial: dashboard done; radar measurement waits for a person · **Plan:** [plans/2026-11-05-radar-tuning-and-dashboard.md](../plans/2026-11-05-radar-tuning-and-dashboard.md)

## Goal
- Show the model in the existing dashboard.
- Optimize and verify "the sensor": the radar, plugged in at 18:19.
- Tell the user when real people are needed.

The user chose to keep the current radar settings and only measure them, and to show the model through a replay
file first.

## What changed
- **`model/trnet/inference.py`:** runs a trained fold model over a session, scoring each rep from the reps before
  it, as it would run live, and adds the rules' advice.
- **`model/export_dashboard.py`:** writes a protocol-1.2 `.ndjson` recording:
  - `hello` + manifest: 3 radar views, 6 scores with thresholds, 5 actions, the elbow angle as an aux channel;
  - frames at 15 fps, as base64 float32;
  - rep, compensation and recommendation events;
  - scores and status once per second (synthetic for fake data);
  - session start and end.

  Messages are numbered in time order. It also copies the file to `frontend/public/replays/`.
- **`model/tests/test_export.py`:** format test (hello first, numbering, frames, scores, events). 60 model tests
  in total.
- **`model/demo.py` + `demo_page.html`:** the stand-alone demo page from earlier today.
- **`frontend/`:**
  - `?replay=` link: `src/lib/address.ts` (same-origin `.ndjson` only), `src/App.tsx`, `src/Root.tsx` (goes
    straight to the dashboard).
  - Radar panel view buttons and an automatic two-sided colour scale for signed maps
    (`src/widgets/RadarWidget.tsx`, `widgets.module.css`, `src/lib/colormaps.ts` `diverge`).
  - Updated panel help texts in `src/config/defaults.ts`.
  - New Thai and Traditional Chinese text in `src/i18n/catalog.ts`. "Speed" was already used for playback speed
    (播放速度), so the radar view is called "Movement speed".
  - `vite.config.ts` removes `dist/replays` after a build; `.gitignore` ignores `public/replays/`.
- **`.claude/launch.json`:** `model-demo` (the stand-alone page on 127.0.0.1:8770).
- **Recordings:** the smoke session `recorder/data/sessions/2026-11-05_183108_TEST_radar_smoke`. A failed first
  start left an empty session folder, which I removed.

## Verified by
- **Front end:**
  - `npm run typecheck` passes;
  - `check-i18n`: PASS, 489 pairs;
  - `check-session-report`: PASS;
  - `npm run build`: 552 KB, with no replay inside `dist/`.
- **Model tests:** 60/60.
- **In the browser** (`npm run dev`, `?replay=` link, fake person F06, held out of training):
  - opens straight on the dashboard: "Demo data" banner, "Signal good", badges for fake radar, network and
    camera pose;
  - Session view at rep 16: "Rest — fatigue 0.85 ≥ 0.85", ROM 99° (−14 % since the first rep), the score gauges;
  - Technical view: buttons switch between "Where things are", "Tiny motion" (blue–orange, −1…1 ×π rad) and
    "Movement speed"; Data streams lists all 11 model streams;
  - at the end, the dashboard's own summary opens: 24 reps, 2:00, "Demo report", fatigue 18 % → 77 %;
  - no console errors.
- **Radar smoke test (10 s, current settings):**
  - 653 frames at 60 fps, 0 missing;
  - IMU over Wi-Fi at 200 samples/s with no drops.
  - The first start failed: the radar rejected a stray byte waiting on its command port. The retry worked.

## Issues / not done
- **Radar measurement still to do:**
  - The empty-room run was skipped ("Not now"); the Nov 4 empty-room recordings stand in.
  - The curls run and the left/right run need a person. So the wrap-around check of the current ±1.09 m/s limit
    and the angle-axis direction are not measured yet.
- **Dashboard:**
  - Live mode (bridge model provider) waits for the Pi setup and its package installs.
  - After a replay ends, Restart waits for Play. This is existing dashboard behaviour, not changed.
- **MyoWare:** its record sketch is still not uploaded.
- **Nothing committed.**

## Next
1. **With a person (the user):** wear the IMU board on the forearm and stand ~1.3 m in front of the radar. Record
   ~75 s: 3 shrugs, 3 slow, 3 normal and 3 fast curls. Then 30 s of standing left, centre and right.
2. Measure the wrap-around (IMU speed vs the ±1.09 m/s limit), the arm visibility, the left/right direction and
   `check_session.py`.
3. Upload `myoware_record` when the MyoWare is on USB, with nobody wearing it and the user's "upload it".

**Uncommitted work:** yes.
