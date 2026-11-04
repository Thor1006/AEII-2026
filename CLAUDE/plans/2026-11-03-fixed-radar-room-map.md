# Plan: Accumulate a fixed-radar 3D map of observed front-of-room reflections

**Status:** done
**Date:** 2026-11-03

**Approval:** User replied "OK" to this written plan on 2026-11-03. Implement the fixed-board front-of-room accumulation feature within the existing host viewer; keep RF/firmware settings unchanged.

## Result
Completed the bounded RAM-only Room map with 30-second retention, 10-cm display cells, three-frame persistence, low-radial-velocity option, map/live layers, clear/pause/resume and honest historical states. Eleven unit/integration checks and actual browser controls passed. Final screenshot shows 128 persistent measured cells, eight current live points, ~40-Hz reception/display and zero gaps/invalid packets in that test session. Default display span is 10 m, not a changed detection range; no RF/backend/firmware changes. See [full evidence, sparse-map limits and run state](../output/2026-11-03-fixed-radar-room-map.md). Same local tab left live. No commit/push.

## Why
The user asks to map the surroundings and clarified: keep the radar stationary and accumulate points to see the front of the room. The current display shows only individual measured frames. The existing x/y/z points and frame cursor can support a bounded accumulated reflection map in the fixed sensor coordinate system. This is not 360-degree coverage, SLAM, a complete room mesh, an occupancy/free-space survey or a camera image. No map can reveal objects not detected in the sensor's field of view.

## Current evidence
- The selected live runtime profile is `tdm-wide-points-40hz.cfg`; it retains static clutter (`clutterRemoval -1 0`), uses x/y/z/velocity point output and leaves detection thresholds/antenna geometry unchanged.
- Existing 3D projection, orbit/zoom/presets and near-warm/far-cool distance colors can be reused. Current Display range changes only camera bounds and color scale; it is not a new radar detection range or physical coverage guarantee.
- Read-only health at this task's start: approximately 644 seconds, 25763 last frame / 25762 received frames, eight current points, one sequence discontinuity and zero malformed packets. Previous short-run zero-gap evidence is therefore not an unlimited-duration claim. Preserve counters and never fill missing packets with invented observations.
- TI's EVM guide describes the 4-TX/4-RX etched antenna arrangement and azimuth/elevation estimation: https://www.ti.com/lit/ug/spruj22c/spruj22c.pdf, antenna section. Software angle filters are not evidence of uniformly reliable physical coverage across those angles. No precise physical FoV figure is asserted here.

## Approach
1. Add Live points / Room map view modes in the existing local 3D viewer. Default the newly requested mode to Room map after approval, retaining a simple return to the existing live view.
2. Accumulate each newly received real frame once, directly from the existing cursor/history delivery, independent of render rate. Use measured x/y/z in the fixed radar reference frame. Keep a recent observation window (default 30 seconds) with a hard memory bound (initially at most 2000 spatial cells), so an unattended view cannot grow indefinitely.
3. Group nearby observations into 10-cm spatial cells for display density control. Require observations in at least three distinct frames before showing a persistent map cell. Prefer low-radial-velocity returns for the environment layer; expose an explicit option if moving returns are included. These are display filters, not new sensing resolution or certified static-object classification. Moving people can still leave temporary trails, and stationary people can appear in the map.
4. Keep current live measured reflections distinguishable from the accumulated map. Retain distance colors measured from the radar, not camera position or confidence/temperature. Fade aging cells and remove expired observations; do not connect points into assumed walls, create surfaces or interpret blank regions as free space.
5. Add Clear map and Pause/Resume accumulation. A paused or stopped map must be labeled historical/frozen even if the radar continues streaming. Show accumulated cell count, accumulation duration/window and current live status separately. Clear on a new acquisition session/reconnect, and tell the user to clear the map after moving the radar. Map data stays in local browser memory; reload resets it. No export/upload or new dataset recording is included.
6. Reuse existing orbit/zoom/Top/Front/Reset and view bounds. Keep the current 40-Hz RF profile and watchdogs, unchanged firmware/CFAR/antenna settings and access controls. Bound or cache map drawing as necessary, show actual display updates honestly, and preserve the independent receiver-rate metric. Do not promise that accumulation makes the sparse radar cloud into a complete room model.
7. Verify with real incoming frames, demonstrate actual measured-map growth if returns support it, and document what was observed. Keep the existing live view as rollback. Preserve the submitted poster, main frontend, Pi bridge and unrelated changes. No package install, commit or push.

## Files touched
- `sandbox/radar-live-viewer/index.html` — bounded accumulator, map/live layers, map-only controls and honest state labels.
- Focused local tests for deduplication, persistence, expiry, bounds, pause/clear and session reset; reuse existing projection/parser tests as appropriate.
- `sandbox/radar-live-viewer/README.md` — fixed-board usage, layer meanings and limitations.
- Task-local screenshot/test outputs and `CLAUDE/output/`, `CONTEXT.md`, `DECISIONS.md`, this plan.
- No backend/radar change is expected; any necessary host-only adjustment must stay within this feature's memory/performance limits and preserve the current control/security behavior.

## Risks / needs OK
- This non-trivial map accumulator/interaction feature has received the required written-plan OK; proceed within the scope above.
- Radar must remain fixed. With no pose reference, moving it invalidates the shared coordinates; this plan does not estimate or compensate radar motion.
- Multipath, weak/specular surfaces, angular error, occlusions and residual moving returns can create incomplete or misplaced clusters. Cell grouping/persistence is not a physical-accuracy improvement. Detectable stationary objects are not automatically room structure.
- Latest 40-Hz extended health already records one gap; do not silently reset/relabel that observation or imply complete coverage. Keep raw loss counters visible and treat unobserved space as unknown.

## How we'll verify
- Unit checks: one contribution per frame/cell, repeated cursor frames ignored, distinct-frame persistence, expiry and bounded eviction, moving-return option, pause/resume/clear, new-session reset, finite coordinates and color meaning independent of camera movement.
- Real browser check: increasing frame numbers, honest receiver/display rates, map counts tied to actual measurements, working camera and map-only controls, blank/empty state, and truthful live/paused/stale/stopped labels. Verify no radar commands originate from map/camera controls.
- Compare the existing Live points mode with Room map; inspect rendering responsiveness and bounded map size in the current narrow browser view. Run relevant existing packet/state/security checks only if affected code changes require them.
- Save a screenshot of actual measured accumulated points with the accumulation status visible; report if hardware returns remain too sparse to outline room boundaries. Do not manufacture a room-shaped success image.
