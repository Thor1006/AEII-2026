# Plan: Show existing live radar points in an interactive 3D view

**Status:** done
**Date:** 2026-11-02

**Approval:** User replied "OK" to this specific 3D-view plan on 2026-11-02. Proceed with host-only rendering and camera controls; rate/resolution tuning remains a separate unapproved proposal.

## Result
Implemented true measured-x/y/z perspective rendering, orbit by actual browser drag/keyboard, zoom, Top/Front/Reset, stable radar-distance colors, negative/positive height reference and clipping/visible counts. Projection sanity checks and final JavaScript syntax passed. Actual browser drag changed camera angles while real frame numbers continued; presets/zoom/keyboard and truthful stopped/restarted states passed. Final sampled health: 117 consecutive frames at 10 Hz, zero gaps/invalid packets; screenshot later shows real frame 518. No browser console errors. The user subsequently requested applying all discussed changes; rate/resolution tuning is now separately approved, after this 3D implementation completed.

## Why
The user now asks for a 3D-camera-like view instead of the top-down heatmap. The existing real TI point packets already include x, y and z, so changing the host view can expose measured height/depth without modifying radar firmware or configuration. Sparse radar reflections cannot supply camera images, a complete body surface, skeletal pose or unmeasured detail.

## Approach
1. Replace the default top-down canvas presentation with a perspective 3D point view, using existing measured coordinates in meters. Label sideways x, forward y and height z, with a ground grid and marked radar origin. Keep equal world units; use a guarded camera projection and depth ordering.
2. Add mouse/touch drag to orbit, wheel/pinch or explicit buttons to zoom, and Reset view / Top / Front presets. Provide keyboard or button alternatives. Camera controls affect only the view; never send radar commands or restart acquisition.
3. Keep the requested near-warm/far-cool palette based on actual 3D range from the radar, independent of camera viewpoint. Keep the labeled distance scale. Keep precise measured dots; any halos are visual only, not a reconstructed surface.
4. Keep Start/Stop/Close, actual frame/count/receiver-rate/data-age indicators, and honest stale/stopped state. Report points visible versus total when the display volume or projection excludes points. Preserve the existing local-only security/watchdogs, official runtime profile and 10-Hz receiver/250-ms polling unless separately approved.
5. Implement inside the existing viewer using browser canvas and no external libraries/CDN/packages. Preserve unrelated repo changes, submitted poster, main dashboard and Pi bridge. No firmware flash, recording/upload, commit or push.

## Files touched
- `sandbox/radar-live-viewer/index.html` — 3D projection, drawing and camera-only controls.
- `sandbox/radar-live-viewer/README.md` — interaction and interpretation notes.
- Task-local screenshot — visible verification artifact.
- `CLAUDE/output/`, `CONTEXT.md`, `DECISIONS.md`, this plan — final results/status.

## Risks / needs OK
- This adds a non-trivial renderer/interaction change. User OK has been received for this plan; keep within the host-only scope above.
- Do not imply that a sparse 3D point cloud is a camera/depth image, body scan or improved sensing precision. Show actual measured z, including noise; do not synthesize body shapes or silently smooth away measurements.
- Guard near/behind-camera and out-of-volume points, non-finite projection values and resize/touch behavior. A camera reset must not reset the sensor.
- The earlier rate/resolution optimization plan stays proposed and unapproved; this task does not authorize that tuning.

## How we'll verify
- JavaScript syntax and focused projection sanity checks: coordinate axis direction/units, finite output near projection boundaries, and range colors independent of camera position.
- Observe real live packets and advancing frame numbers in the browser; confirm positive/negative height affects projected position and no synthetic fallback appears.
- Exercise orbit, zoom, reset and Top/Front presets, verify stable camera controls with the distance legend and current frame, and inspect narrow-window layout.
- Verify stopped/stale labels remain truthful and controls do not issue radar commands except existing Start/Stop/Close. Save a screenshot of the final 3D view and leave the local viewer open.
