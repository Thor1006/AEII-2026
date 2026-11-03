# Plan: Separate car-style live radar visualization

**Status:** done
**Date:** 2026-11-03

**Approval:** User replied "ok" to this written plan. Proceed with the separate page, shared real collector and one service restart; do not change RF settings or the existing Room map HTML.

## Result
Completed `/drive/` as a separate car-style measured-radar page. Original Room map HTML hash unchanged; both share the same approved 40-Hz collector. Eleven geometry/buffer/state checks and HTTP page/auth/file-boundary checks passed. Browser verified view/range/overlay controls, shared Stop at frame 5294, restart, and Drive-page reload without stopping the sensor. Final screenshot frame 10609 shows actual returns at approximately 40-Hz receive/display with zero gaps/invalid packets in that session. One approved service restart, final PID 36636; both tabs left open. No RF/firmware/Pi/main dashboard change, commit or push. [Evidence, limitations and run paths](../output/2026-11-03-car-style-radar-demo.md).

## Why
The user requests a separate demo with a Tesla-car-style radar appearance. Interpret this as an automotive display aesthetic using the existing actual radar stream: a clean light scene, an illustrative ego-car/sensor marker, perspective distance guides and nearby measured reflections. The existing data contains points/velocity/SNR, not validated vehicle/pedestrian classes, lane markings, drivable-space estimates or ego motion. The appearance must not invent those observations.

## Concrete proposed demo
- New page at `http://127.0.0.1:8766/drive/`, with its own source folder and design. Keep the current Room map page and `index.html` intact.
- Light gray/white perspective scene, a custom car silhouette marking the radar origin near the bottom center, a subtle reference grid with meter labels, and calm blue accents. The icon is an illustrative origin marker, not detected vehicle geometry.
- Actual measured reflections appear as neutral small 3D markers/blocks, optionally grouped when points are close; any grouping is labeled reflection groups, not classified objects. Preserve an optional raw-return overlay so the measurements can be inspected. Block size is a symbol, not estimated object dimensions. Position/range/velocity come from measured coordinates.
- Range colors/proximity arcs may emphasize nearer measured returns in warm tones and farther returns in cool tones. No return means unknown; never imply a clear road or fill empty sectors with synthetic cars/people. The reference grid is not detected lanes, and there is no suggested driving path.
- Minimal readouts: actual receive rate, unique displayed measured-frame rate, latest frame, data age, return count and nearest measured-reflection distance. Keep honest Live / Waiting / Stopped / Stale labels and loss indicators.
- View controls: perspective/top view, display range, raw-return overlay and global Start/Stop. Clearly state that Start/Stop controls the single shared radar stream for all views. A link opens the existing Room map. Closing this new page should not explicitly stop another still-open viewer; the existing global session/client-loss watchdog remains.

## Approach
1. Create the separate vanilla HTML/CSS/canvas/SVG demo in `sandbox/radar-car-demo/`, using existing tools with no external packages, scripts/CDN or uploads. Use custom code-native graphics for the ego marker and scene.
2. Add one exact allowlisted GET route `/drive/` to the existing loopback server, returning only the new HTML and injecting its existing local control token. Reuse the existing Host/Origin/token checks and CSP. Do not expose filesystem directories or enable CORS/LAN access.
3. Reuse `/api/state?after=...` and the existing real-frame cursor/history. Both browser pages share the single COM5/COM6 collector; do not launch another serial reader or change the RF profile. Use bounded buffering of actual frames, not interpolated positions or synthetic fallback. Preserve stale/error semantics and frame-gap counters.
4. If grouping points for clarity, keep the method bounded and deterministic; do not derive semantic object labels, physical sizes or confidence probabilities. Preserve actual coordinates and clearly label display grouping. No claim of tracking a real car, autonomous-driving capability or improved sensor precision.
5. Stop/restart the existing local service once to load the new route, then resume the same approved 40-Hz profile. This restarts acquisition and the existing RAM-only Room map clears on its normal new-session/reconnect behavior. Keep the existing page available and open the new page in a separate tab.
6. Verify both pages against the same real stream, keep controls/watchdogs correct, save a screenshot of the new car-style view and document exact run state. Preserve unrelated changes and source poster/proposal. No firmware flash, main dashboard/Pi install, commit or push.

## Files touched
- `sandbox/radar-car-demo/index.html` — separate automotive visualization and local controls.
- `sandbox/radar-car-demo/README.md` and focused geometry/state tests — usage, interpretation and validation.
- `sandbox/radar-live-viewer/server.py` — one explicit HTML route only; shared collector/profile/security remain.
- Existing viewer README — new URL and shared-control behavior; existing viewer HTML remains unchanged.
- Task-local screenshots/logs and `CLAUDE/output/`, `CONTEXT.md`, `DECISIONS.md`, this plan.

## Risks / needs OK
- Written-plan OK has been received. This is a separate UI sharing the physical radar/session.
- Adding the route needs one service restart; the existing RAM map will reset on acquisition restart. Do not hide this or claim both displays have independent physical controls.
- The original viewer currently stops the shared sensor when its page closes/reloads. Preserve that established behavior; the new demo must truthfully show any resulting stop and allow the shared Start control. Do not silently redesign the old page's lifecycle in this task.
- Current read-only health before implementation: running, frame 20841 / 20840 received, seven returns, ~40.1 Hz, one sequence gap, zero invalid packets. Preserve this historical evidence; do not describe the stream as indefinitely lossless.
- Do not turn reflection clusters into confirmed cars, people, walls, collision risks or drivable space. The aesthetic does not add missing classification/pose information.

## How we'll verify
- Focused checks for coordinate direction/scale, finite projection/clipping, range colors, grouping bounds and measurements, cursor deduplication/new-session reset, and stale/stopped display behavior.
- HTTP checks: original `/` and new `/drive/` return their correct distinct pages; unauthorized controls and invalid Host still return 403; unlisted paths do not expose files.
- Actual browser: real frame numbers advance, measured returns are visible, received/displayed rates are truthful, the new car-style scene is readable in the current narrow viewport, and no console errors. Inspect range/view/overlay controls and global Start/Stop behavior.
- Confirm the original Room map still opens and functions with the same collector/profile. Record any restart/gaps honestly, preserve existing watchdogs, and keep the new demo as a separate deliverable tab.
- Save a screenshot of the live measured display. If the scene has few returns, show that sparse scene rather than inventing an attractive traffic image.
