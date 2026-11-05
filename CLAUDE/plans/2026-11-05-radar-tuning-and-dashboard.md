# Plan: tune the radar settings for elbow curls, and show the model in the dashboard

**Status:** Part B done. Part A measured with a person on 2026-11-05 ([report](../output/2026-11-05-1921-radar-curls-measurement.md)): current settings fast enough at ~1 m; IMU wiring unreliable on the arm; left/right not determined (next: metal target). Earlier: smoke test passed, empty-room run skipped by the user ("Not now") ([report](../output/2026-11-05-1844-dashboard-replay-radar-check.md)). Approved (2026-11-05) with the user's choices: radar **"Only measure current"** (keep P0, no new profiles: Part A becomes steps 1, 2 and 4 for P0 only, plus the wrap-around check); dashboard **"Replay file"** (Part B steps 1-3; live mode later)
**Date:** 2026-11-05

## Why
The user (2026-11-05): "The sensor is here, can you optimize it? Run an optimization and verification loop until
the result look right", and "also implement the front end from the one that we make before this and tell me when
you need real people on sensor".

What's connected now:
- **Radar:** AWR2944PEVM on USB (`/dev/cu.usbmodemRA29P0551` CLI, `…0554` data), idle and waiting for its settings.
- **IMU board:** reachable over Wi-Fi.
- **MyoWare:** in Bluetooth range, but still running the old demo sketch (its record sketch has never been uploaded).

## Part A — radar settings loop (no flashing)
The radar's settings ("profile") are sent each time it starts, as the recorder already does. Nothing is flashed;
unplugging the power or sending `sensorStop` brings back the waiting state. The firmware stays as verified on Nov 2.

**What to improve.** In the current profile (`fullmap_awr2x44p.cfg`), the radar can only tell speeds up to
±1.09 m/s (0.137 m/s per Doppler bin). A hand in a brisk curl can move toward the radar faster than that. Then its
speed "wraps around" and shows as a wrong speed (aliasing), so the network would see nonsense in the fastest part
of each rep. The chirps spend 14.3 of every 16.7 ms just waiting (idle 267 µs per chirp).

**Candidates.** All keep 60 fps, 64 range bins × 5.94 cm, 16 Doppler bins and the 8 azimuth antennas, so the
network's input shape doesn't change:

| Profile | Change | Speed limit | Speed per bin | Notes |
|---|---|---|---|---|
| P0 | none (today) | ±1.09 m/s | 0.137 m/s | baseline |
| P1 | idle 100 µs | ±2.50 m/s | 0.312 m/s | coarser speeds, no wrap-around |
| P2 | idle 50 µs | ±4.06 m/s | 0.507 m/s | probably too coarse |
| P3 | 2 TX (drop the elevation TX) | ±1.64 m/s | 0.205 m/s | no height for radar-lab's 3D points |
| P4 | 2 TX + idle 100 µs | ±3.75 m/s | 0.468 m/s | |

**Loop.**
1. **Bench check, automatic.** Nobody needs to be in front of the radar; please stay out of its view for ~1 minute
   per profile. For each profile, check:
   - the radar accepts it;
   - 60.00 fps with 0 missing frames over 60 s;
   - processing margin (stats TLV) above 0;
   - frame size within the USB budget;
   - temperature under 70 °C;
   - empty-room noise floor.

   Profiles that fail are dropped. Each run is recorded with `recorder/record.py` and checked with the model's
   `check_session.py`.
2. **Person in front, ⚠ needs a real person (you).** For each profile that survives:
   - stand ~1.3 m in front of the radar;
   - do 3 shrugs, then 3 slow curls, 3 normal curls and 3 as fast as safely possible;
   - wear the IMU board on the forearm (Wi-Fi). Its gyro gives the true arm speed.

   Measured for each:
   - **Wrap-around:** the radar's Doppler speed compared with the speed the IMU says.
   - **Arm visibility:** share of rep frames where the arm is above the empty-room level.
   - **Phase channel:** how stable it is during the holds.
   - **Shrug sync:** offset against the IMU.
3. **Pick and verify.** Choose the profile with no wrap-around at your fastest curl (peak below 80 % of the limit)
   and the best arm visibility. Re-record 2 minutes and confirm 0 missing frames, all checks green, and the shrug
   sync within 17 ms.
4. **Left/right check, ⚠ needs a person:** stand left of the radar, then right, 10 s each. This confirms the angle
   axis direction, an open item in CONTEXT.
5. **Results.** Save the chosen profile as a new file, `radar-lab/configs/rehab_awr2x44p.cfg`; the existing file
   stays unchanged. Update the model contract if the speed scale changes (`v0-draft` → `v0.2-draft`), and
   recalibrate.

**"Looks right" means:**
- 0 missing frames in 2 minutes;
- no Doppler wrap-around at the fastest curl;
- the arm visible in ≥ 90 % of rep frames;
- left/right confirmed;
- `check_session.py` usable with all sensors present.

## Part B — the model in the dashboard (`frontend/`)
The dashboard already speaks a matching protocol (1.2):
- radar frames per view;
- named scores;
- `rep_start`/`rep_end` with ROM;
- `recommendation` events with exactly our 5 actions;
- a manifest that labels everything.

It can also replay a recorded `.ndjson` file.

1. **`model/export_dashboard.py`** runs the network on a session and writes a protocol-1.2 `.ndjson` recording:
   - `hello` + manifest listing:
     - 3 radar views (where things are, tiny motion/phase, speed);
     - the 6 scores with thresholds;
     - the actions;
   - frames at 15 fps;
   - scores and events after each rep;
   - a status message once per second, with `synthetic: true` for fake sessions so the dashboard's "Demo data"
     banner shows.

   No installs; it works for fake sessions now and for real sessions later.
2. **Dashboard changes, kept small:**
   - make sure the radar panel can switch between the 3 views and the scores panel shows our 6 scores;
   - add the new English text and its Thai and Traditional Chinese translations to `src/i18n/catalog.ts`;
   - run the existing checks (`npm run typecheck`, `check-i18n`, `check-session-report`).
3. **Verify in the browser:** open the replay in the dashboard (`npm run dev`), watch it play, and check both the
   Session and Technical views and the summary at the end. Screenshot as proof.
4. **Later (not in this plan): live mode.** A model provider in `pi-bridge/` (radar → network → WebSocket). It
   needs `websockets`/`numpy` installed for the bridge, which you paused until the Pi setup, so I'll ask then.

## When I need real people
- **Part A step 1:** nobody in front of the radar, ~1 minute per profile, about 5 minutes in all.
- **Part A step 2:** one person (you) for curls in front of the radar with the IMU on the forearm, ~3 minutes per
  surviving profile.
- **Part A step 4:** one person, 30 s.
- **Not yet:**
  - The MyoWare sEMG needs its record sketch uploaded first (USB cable, nobody wearing it, your "upload it").
    After that, a person wears it on battery.
  - Recording other people (classmates) for training needs their consent and your teacher's OK first.

## Risks / needs OK
- **Radar settings:** sending modified profiles at start (P1–P4) is a configuration change, and CLAUDE.md says
  to ask first. No flashing. A power cycle restores the waiting state.
- **Heat:** the radar's temperature is watched; a run stops at 85 °C.
- **Contract change:** if a new profile changes the speed scale, the fake data and the contract follow it
  (`v0.2-draft`). The current `v0-draft` stays reproducible.
- **Front end:** small changes in `frontend/`. The existing tests and checks must still pass.

## How we'll verify
- **Part A:** per-profile table (fps, missing frames, margin, temperature, speed limit vs IMU speed, arm visibility,
  left/right), plus `check_session.py` on the final recording.
- **Part B:** replay plays in the dashboard with no console errors; the scores, reps and recommendation match
  `model/demo.py`; typecheck and the i18n and report checks pass; screenshots.
