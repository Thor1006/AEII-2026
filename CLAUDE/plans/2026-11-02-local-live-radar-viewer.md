# Plan: Show the verified radar point cloud in a local live graph

**Status:** done
**Date:** 2026-11-02

## Why
The user asks for the radar graph to appear after a real 151-frame UART test passed. The official TI visualizer 4.7 page and its linked Windows application download both redirect to TI's error page. Do not reflash working firmware or claim that a recorded/synthetic graph is live.

User explicitly approved the separate local live graph through the confirmation question on 2026-11-02. Approval covers using existing tools, runtime radar configuration and a local-only display, without reflashing, modifying the original dashboard or sending data off-machine.

## Result
Implemented `sandbox/radar-live-viewer/` and verified actual hardware frames and visible live points in the task browser. Start, Stop, clean server shutdown and restart passed. Nine packet/state unit tests and all 151 real recorded packets passed; unauthenticated controls and invalid Host are rejected with HTTP 403. Final health sample: 615 consecutive frames, 10.0 Hz, zero invalid packets/gaps. Viewer left live at http://127.0.0.1:8766/ in process 40248 with a 15-minute acquisition limit and a 15-second client-loss stop. See `CLAUDE/output/2026-11-02-local-live-radar-viewer.md`.

## Approach
1. Obtain approval before adding this small custom diagnostic viewer, as required by the repository's plan-before-code workflow.
2. Add a separate local-only viewer with the existing isolated Python/pyserial runtime and Python standard library. Keep the application outside the main frontend and Pi bridge. No additional packages, TI Cloud Agent, browser extensions or system settings.
3. Reuse the known-good official AWR2944P TDM profile and verified header/TLV structure. Use COM5 at 115200 for runtime start/stop and COM6 at 3125000 for the actual point cloud. No firmware writes, calibration saves, raw ADC claims or AI/fatigue scores.
4. Serve the graph only on 127.0.0.1, not LAN/public interfaces. Clearly label real live data, connection state, frame number and data age. Never substitute the previous capture or synthetic data silently. A stale/disconnected display must say so.
5. Show a simple point-cloud graph with axes in meters, plus start/stop controls. Keep layout compact and readable. Stop acquisition when the viewer closes/disconnects or its bounded session expires; release COM ports on exit/failure.
6. Launch the local process hidden, record its PID/logs/stop mechanism and open the viewer in the task browser. Verify actual frame numbers advance and the graph is nonempty with real data before calling it complete.
7. Test stop/restart, stale/error states and clean shutdown, then leave the graph running for the requested live demonstration with clear stop control and a timeout. Update context/report and do not commit or push.

## Files touched
- Separate task-owned local viewer code, configuration copies, test evidence and logs.
- CLAUDE context, decisions and output report, without changing the existing frontend, Pi bridge, installed TI SDK or submitted documents.

## Risks / needs OK
- Only one process can own the radar COM ports at a time; keep other serial tools closed.
- Starting the viewer sends the same already-tested runtime profile/start command, not new firmware. Provide a visible stop control and no unattended indefinite acquisition.
- This is a custom host graph for TI demo output, not the official TI visualizer and not validated clinical/AI functionality.
- No network/firewall/security changes, upload, public hosting or additional purchase.

## How we will verify
- Match the connected platform/chain/SDK against AWR2X44P/TDM/04.07.02.01 before starting.
- Receive valid packets and increasing frame numbers from COM6; compare point count against TLV/header metadata.
- Inspect the graph in the browser and verify live, stopped and stale states are truthful and stop/restart works.
- Record exact run/stop paths and final acquisition/process state. Preserve all existing user changes.
