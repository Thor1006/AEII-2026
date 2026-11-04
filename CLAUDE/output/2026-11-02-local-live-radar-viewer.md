# Real live radar graph delivered

Date: 2026-11-02 (Asia/Bangkok). Status: verified and left running for the user at http://127.0.0.1:8766/ in the task browser. This is a custom diagnostic host graph, NOT TI's own GUI or the project's AI dashboard.

## Approval and unchanged boundaries
The user requested the graph and explicitly approved a separate local real-data viewer. Official TI 4.7 launch and linked Windows installer both redirected to TI's error page. No alternate firmware, global package installation, browser extensions/Cloud Agent, firewall/network changes, uploads, main frontend/Pi edits, poster changes, Git commit or push were performed.

## Implementation
Source: `sandbox/radar-live-viewer/server.py`, `index.html`, `test_packets.py`, `test_http.py`, `README.md`.
- Existing isolated Python/pyserial; Python standard-library ThreadingHTTPServer, threads and JSON. Bind only 127.0.0.1:8766, with Host/origin/token checks and no CORS/external assets.
- CLI COM5/115200, data COM6/3125000; verify TI USB VID/PID and same-board serial, then returned AWR2X44P/TDM/04.07.02.01 before runtime configuration.
- Uses the unchanged already-tested official AWR2944P TDM profile. Never flashes or saves calibration.
- Bounds-check magic, packet length, platform/SDK/subframe, TLV lengths, finite point coordinates and detected-point count. Parse TLV1 x/y/z/radial velocity and TLV7 SNR/noise. This is processed OOB output, not raw ADC or a clinical/body-tracking output.
- Graph shows XY meters, frame/point counts, measured receive rate and packet age. Live requires a real packet less than 2 s old; stopped/error/stale data is not labeled live. No recording/replay/synthetic fallback exists in the server.
- Start configures/runs; Stop sends sensorStop and releases ports; Close stops acquisition and shuts the server. Loss of viewer heartbeat for 15 s or 900-s acquisition limit stops the sensor. The source currently uses a 3-m display selection in the open page (display scale only, no radar configuration change).

## Tests and observed results
- Nine unit tests passed: point units, partial frames, prefix recovery/sequence, wrong platform/count, no-data and stale truthfulness, valid zero detections and malformed packet size.
- Real-file validation accepted all 151 frames from the earlier 196192-byte capture, with no invalid/skipped data. That capture was independently validated by TI's official parser in the previous report.
- First live run visibly advanced through frames 164, 473 and 845 with measured ~10.0 Hz and 7-8 points in sampled UI observations.
- Stop returned Done and the graph displayed LAST FRAME / NOT LIVE. Close showed Viewer closed / Serial ports released. Process 15792 exited; a new server was started for final delivery.
- Unauthorized POST /api/start and GET with invalid Host returned HTTP 403; health stayed stopped before final Start. Both security tests passed.
- Final live run visibly advanced through frame 135, then health frame 615 with frames_received=615, point_count=7, 10.0 Hz, data age ~0.032 s, invalid_packets=0, frame_gaps=0. Later UI frame 740 and 998 continued advancing. These are bounded observed results, not long-run loss guarantees.
- Browser screenshot was visually inspected for actual points, axis labels and status. Compact layout was adjusted for the side-panel width. Parser test fixtures are synthetic test-only; they are never exposed to the live viewer.

## Current process and artifacts
Final server PID: **40248** (Python); URL: **http://127.0.0.1:8766/**. The graph tab was marked as a deliverable and left open. Sensor is intentionally running at handoff, subject to the safety stops above.

Runtime directory:
`C:/Users/chap_/.codex/.chatgpt-projects/g-p-69f1b1cfff0c81919aa91c82a1c098a6/tmp/radar-flash-2026-11-02`.

- Python executable: runtime directory `/.venv/Scripts/python.exe`.
- Runtime profile: `official-awr2944p-tdm.cfg` (unaltered TI profile copy).
- Final logs: `live-viewer-final-stdout.log`, `live-viewer-final-stderr.log`.
- First-run logs preserved: `live-viewer-stdout.log`, `live-viewer-stderr.log`.
- Proof screenshot: `live-radar-graph.png` (static screenshot only; actual live graph is the URL).
- Existing flash, capture, parser logs and manifests are preserved.

## Open, stop or restart
Open the URL while the server is alive; use the visible Start / Stop buttons. Close viewer shuts down the server as well. If 15-minute timeout stops acquisition, Start begins another bounded session without reflash. A page close/disconnect eventually stops acquisition through keepalive/watchdog; it does not implicitly kill the idle server.

To restart a stopped server, first confirm no existing viewer process owns COM5/COM6, then use the runtime's Python to run `C:/Users/chap_/.codex/AEII-2026/sandbox/radar-live-viewer/server.py --profile <runtime directory>/official-awr2944p-tdm.cfg --port 8766`. Launch hidden if using Start-Process and preserve logs. Do not start the bounded capture helper while the live viewer owns the ports.

The full recorded input contract, synchronized ground truth, recording sessions, main dashboard/AI integration, custom complex/Range-Doppler firmware, Ethernet and Pi deployment are separate future tasks. Both current flash and local-viewer plans are marked done based on the explicitly approved local-display substitute; TI's own GUI remains unverified.
