# Fixed-radar front-of-room map — completed

The user clarified stationary-board accumulation of the front-of-room view, then replied OK to the written plan. Implemented the approved host-only feature in the existing localhost viewer. No backend, firmware, RF profile, CFAR/antenna setting, SDK, main dashboard or Pi changes; no package install, upload, new dataset recording, commit or push.

## Behavior
- Default Room map mode, with Live points available as rollback/view choice. Existing 3D orbit/zoom/Top/Front/Reset remain. Default display range is now 10 m for broader visualization; it does not change physical detection range or sensor configuration.
- Accumulate incoming real frame history independently of which frames the live animation displays. Repeated frames are ignored. Group observations into 10-cm display cells, with at least three distinct frames required within a 30-second observation window. Each cell's position averages its most recent three per-frame centroids; multiple detections in one frame count once per cell. This is grouping/visual persistence, not improved physical accuracy.
- Default environment filter accepts absolute radial velocity <=0.15 m/s. Include moving reflections explicitly changes this display filter and clears the map. It is not a reliable static-object/person classifier; moving people may leave trails and stationary people may appear.
- At most 2000 total candidate plus persistent cells, with least-recently-seen eviction. Old observations expire. Map snapshots cache for up to 100 ms; the latest actual measured reflections continue as a separate circle layer. Map squares use radar distance colors and fade by observation age. There is no surface interpolation, wall completion, free-space labeling, coverage percentage or synthetic-room fallback.
- Clear map, Pause/Resume and Live/Room-map selection issue no radar commands. Pause freezes the historical map while radar frames can continue; stopped/stale/disconnected maps are also clearly labeled historical/frozen. Resume expires old observations before new accumulation. New acquisition/reconnect clears the map; reload resets RAM-only data. Keep the board fixed and clear after moving it. Historical tooltip ages refer to the frozen snapshot.

## Verification
`test_room_map.js` passed all **11** focused checks and compiled the final browser script. Checks cover distinct-frame persistence, frame/cell deduplication, coordinates/range from measured data, expiry, bounded eviction, moving-return filtering, pause/resume without replay, stale freezing, clear/session reset, invalid inputs, input history independent of bounded rendering, and reconnect reset. Synthetic fixtures exist only inside the unit test and are never served as data.

Actual browser observations:
- Initial accumulation reached 67 persistent cells at frame 1327, versus five points in that current frame, with a full 30-second observation window and ~40-Hz receiver rate.
- Pause froze 90 persistent / 90 candidate cells while the live frame number advanced from 3013 through 4706. Live-points view worked and returning to Room map kept the same paused counts.
- Clear while paused produced zero cells; Include moving reflections could be checked and unchecked without starting/stopping the radar. Resume rebuilt the map from subsequent measured frames.
- Stop radar at frame 12086 showed **Frozen / radar not live**, retained 125 persistent cells (111 visible with the then-5-m view) and correctly showed no live receive/display rate. That test session had zero packet gaps/invalid packets; max valid sensor temperature 56 C. This does not erase the earlier long-run discontinuity documented during preparation.
- Reload/new Start cleared map state to zero and began a fresh unchanged 40-Hz acquisition. Final broader 10-m view showed 74/74 map cells visible at frame 4253, confirming earlier view clipping did not imply missing mapped returns. Top and Reset/Zoom presets worked with the accumulated layer.
- Final screenshot at **frame 8679** shows **128 persistent cells + 169 candidate cells**, all 128 persistent cells visible, eight current measured points, 30.0-s observed window, ~40.4-Hz received / ~40.3 displayed unique frames/s, zero gaps/invalid packets, max temperature 56 C and min timing reserve ~22.7%. Counts vary with actual returns and expiry; they are not fixed demo values.
- No browser console errors. The current narrow browser layout, mode/filter/pause/clear controls, measured map growth and frozen labels were inspected. Touch gestures were not physically retested. The full 2000-cell rendering load was not a real-scene performance test; memory bounds are checked independently.

The radar still provides a sparse reflection cloud. These tests do not establish that clusters correspond to all walls/floor/objects, validate room geometry or offer complete front-space coverage. Unseen areas remain unknown, and the stationary-board assumption is required. Packet gaps are not filled with invented map observations.

## Delivery
Same local tab: http://127.0.0.1:8766/, left live in Room map mode with Include moving reflections off, 10-m display scale and perspective camera zoom 1.2. Existing server was reused; no server restart/backend changes for this feature. Last recorded server PID in prior context is 42784; listener ownership was not re-verified (a CIM listener query returned no match while localhost health worked), so check health rather than assuming process identity.

Preview: `C:\Users\chap_\.codex\.chatgpt-projects\g-p-69f1b1cfff0c81919aa91c82a1c098a6\tmp\radar-flash-2026-11-02\live-room-map.png`. Existing session/client-loss/thermal/timing watchdogs remain unchanged. If the bounded session stops, Start resumes acquisition and a new map; no reflash is needed.

Changed files: `sandbox/radar-live-viewer/index.html`, `test_room_map.js`, README and CLAUDE handoff documents. Return to Live points for the prior single-frame graph. Source poster/proposal remain unchanged. No commit or push.
