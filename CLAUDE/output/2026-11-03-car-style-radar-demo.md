# Separate RF Drive car-style demo — completed

User replied "ok" to the written plan. Added the separate car-style page at **http://127.0.0.1:8766/drive/**, in `sandbox/radar-car-demo/`, while retaining the existing Room map at `/`.

## Result
Custom light automotive scene with an illustrative ego car at the sensor origin, perspective/top views, meter reference grid, measured-return display groups, optional raw-return dots, range colors and left/center/right nearest-return arcs/readouts. Gray arcs mean no measured return, not clear space. There are no inferred cars/people, lanes, ego velocity, object dimensions, collision predictions or drivable paths. The car and marker dimensions are symbolic; group positions/velocity derive from measured points.

Display grouping associates nearby returns within 0.28 m of a running centroid, at most 64 groups. Raw overlay remains inspectable. Geometry display bounds accept front returns only and cap displayed input at 1024 returns; clipping/grouping is not a physical accuracy or semantic-classification improvement. Sparse real scenes remain sparse. No interpolation or synthetic traffic fallback.

Both pages share one existing collector and `tdm-wide-points-40hz.cfg`. The backend change is only one allowlisted GET route returning the new HTML with its existing local token. Host/Origin/token checks, CSP, loopback binding and global watchdogs remain. No additional serial reader, RF/CFAR/firmware/SDK change, package installation, external scripts/upload, main dashboard or Pi change.

Start/Stop in either page affects the shared sensor. The new page has no stop-on-close/unload hook and no service-shutdown button. Original Room map close/reload lifecycle remains; its Close viewer button ends the shared service. Adding the new route required the approved one service restart, so the RAM map reset on a new acquisition as expected.

## Verification
- **11 focused Node checks passed**, compiling the final browser script and checking axes/scale, finite/behind-camera projection, supported ranges/views, clipping without fabricated returns, measured group centroids/velocity and bounds, distance colors/sectors, cursor order/deduplication, queue bounds/expiry, stop/disconnect/session reset, and unique-frame-rate warm-up. The display-rate counter waits for at least a 750-ms span to avoid misleading startup catch-up bursts. Fixtures remain offline-only.
- HTTP: `/` and `/drive/` each returned 200 with the correct distinct page and substituted token (token values not logged). Unauthenticated Start and invalid Host on the new route returned 403. `/drive/README.md` and an unlisted traversal-like path returned 404. No filesystem-directory exposure or CORS expansion.
- Original Room map HTML SHA256 remained **CC0B9E036F76C33B03EC7E34BB947117D7DAFB9315FE43F24E206F32D5455C9E**. Its README gained only the new URL/shared-control note.
- Browser verified actual measured frames, full vehicle layout, 3D/Top, range 5/10 m and Raw returns on/off. New Stop froze both pages at exactly **frame 5294**; original Room map retained 77 measured persistent cells, zero sequence gaps and zero malformed packets for that test session. New Start resumed a fresh session with the same profile.
- Reloading `/drive/` during acquisition did not stop/reset the shared radar. The original Room map later showed frame 10030, 73 accumulated cells, ~40-Hz receive/display, and zero gaps/invalid packets. No second serial reader was started.
- Final new-page DOM: frame **10602**, three actual returns/groups, nearest measured return **0.42 m**, ~40.1-Hz receiver / ~40.3 displayed unique frames/s, data age 0.0 s and zero gaps/invalid packets in the current session. The saved screenshot is **frame 10609**, displayed rate 39.8/s. Values naturally vary with incoming measurements.
- No browser console errors. The actual default desktop viewport was inspected; responsive CSS is included, but no forced viewport override/device-size test was performed. Body graphics were adjusted after initial inspection so the whole illustrative car fits in the scene. No claim of exhaustive scene/duration/performance or clinical/driving validation.

Before restart, the old service had reached its existing 15-minute safety stop at frame 36016 with **two historical sequence gaps** and no malformed packets. Preserve that observation; current clean-session checks do not prove indefinite losslessness or fix the underlying intermittent link behavior.

## Run state and files
Shared server **PID 36636**, bound to 127.0.0.1:8766, same approved 40-Hz profile. Both browser tabs left open; Drive view is a separate deliverable at `/drive/`, 3D / 5-m display range / raw returns on. Existing session/client-loss/thermal/timing stops still apply.

Task runtime: `C:\Users\chap_\.codex\.chatgpt-projects\g-p-69f1b1cfff0c81919aa91c82a1c098a6\tmp\radar-flash-2026-11-02`.
- Logs: `car-demo-server-stdout.log`, `car-demo-server-stderr.log`.
- Preview: `car-style-demo.png` (actual measured live scene).
- Runtime: existing `.venv\Scripts\python.exe`; no new dependency.

Changed: separate `sandbox/radar-car-demo/index.html`, `test_geometry.js`, README; two-line allowlisted route in existing `server.py`; existing viewer README; CLAUDE handoff docs. Submitted poster/proposal, existing Room map HTML and unrelated user changes remain intact. No commit or push.
