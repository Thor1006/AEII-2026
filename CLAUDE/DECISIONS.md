# Decisions

<!-- Newest on top. One short entry per decision that someone might later ask "why did we do it this way?" about. -->

## 2026-11-08 — Wi-Fi pauses: hide them in the dashboard, measure them, keep TCP for now (Pi set v0.3)
- **Decision:**
  - The live reference-signal charts run on the Pi's clock, 0.25–1.5 s behind (adaptive, gradual), and keep moving
    through a pause. Recordings are unchanged.
  - The bridge counts Wi-Fi pauses (held data, nothing missing).
  - It backs off 5/15/30/60 s when another program takes the MyoWare (detected by `link_clients` jumps).
  - Dashboard stream defaults: `frame_dtype = "u8"`, radar `fps = 10`, `env_hz = 25`.
  - The MyoWare reports `link_stall_ms` / `link_buf_max` and marks its packets CS4.
  - The sensors stay on TCP: UDP, ESP-NOW and a resumable stream only if tomorrow's check shows they're needed.
  - See [plan](plans/2026-11-08-wifi-drop-fixes.md).
- **Why:**
  - Five reviewers challenged the first draft. The ~1-s pauses fit the ESP32's TCP resend timer (1.0–2.0 s in this
    lwIP build, not tunable from Arduino), not the dashboard's ~1 Mbit/s stream. They found two "on connect" causes:
    two readers on one board, and a bridge list that grew while nobody watched.
  - A display delay fixes what the user sees whatever the cause, without hardware.
  - The measuring tools (health counter, `link_report.py`, firmware numbers) tell the causes apart on the real Pi.
- **Alternatives:**
  - Fixed 1.5-s delay (always laggy).
  - Delaying the radar maps too (adds latency to a USB stream that has no pauses).
  - Rebuilding lwIP (too risky before the competition).
  - Per-viewer view subscription (breaks the lost-message counter).
  - Doing nothing until measured (the user wanted it built tonight to test tomorrow).

## 2026-11-08 — Model input v1: heatmaps + the radar's own points; a finer range profile to try; radar stays on USB
- **Decision:**
  - Contract `v1`: H `[4, 64, 32]` = angle-FFT magnitude, phase change, and two point layers (height, presence)
    pooled over 0.25 s; 32 angle bins (zero-padded); D unchanged.
  - The points come from the same UART frames (TLV 1/7), mapped onto the heatmap grid. `points_az_sign = +1`,
    measured: still points sit +11 dB above their range row with +1, about 0 dB with −1.
  - A finer profile `fullmap_fine_awr2x44p.cfg`: 3.88 instead of 5.94 cm per range bin, out to 2.48 m. Same bytes,
    60 fps and speed steps. It becomes the default only after the board accepts it.
  - The radar stays on USB (TDM demo). No Ethernet firmware.
  - See [plan](plans/2026-11-08-points-and-finer-heatmap.md).
- **Why:**
  - The user asked for "both and cross references" and a finer heatmap. They chose USB over the Ethernet demo,
    whose stream holds only bare points.
  - The heatmap holds only the azimuth antennas, so it has no height; the points have z.
  - The USB link is ~84 % full, so finer range had to keep 64 bins; the cost is the farthest distance.
- **Alternatives:**
  - Points only (sparse, ~7 per frame, no phase).
  - DDM_ENET over Ethernet (points only, no frame numbers).
  - 128 range bins (doesn't fit the USB link at 60 fps).
  - More speed bins (same problem).
  - A sharper angle method (Capon), left for later.

## 2026-11-07 — sEMG: MyoWare over Wi-Fi, one bridge recording for all sensors, sEMG-envelope reps as a fallback
- **Decision:**
  - The MyoWare record sketch sends over Wi-Fi (TCP 3334), the IMU fw 2.1 design; Bluetooth stays as `WIFI_LINK 0`.
  - The Pi bridge owns one session folder per Start/Stop; each provider (radar, `emg`) adds its files on the shared
    clock. `record_dir` moves to `[bridge]`.
  - Live sEMG: envelope 50/s and median frequency 4/s with the model's own `window_mdf`; the median frequency only
    during movement, announced with a new optional manifest flag `intermittent`.
  - Without pose or IMU, the model cuts reps from the sEMG envelope's bursts (fatigue labels only).
  - See [report](output/2026-11-07-1535-semg-support.md).
- **Why:**
  - The user chose "Wi-Fi like the IMU" and "All 5 parts". The IMU loses data on the arm, Bluetooth didn't connect to
    the Mac, and Wi-Fi needs no pairing on a Pi.
  - One folder and one clock are what `check_session.py` needs to line the sensors up.
  - At rest the median frequency measures noise, so it is only sent during movement; the flag stops the dashboard
    and `check_bridge` from calling that silence a fault.
- **Alternatives:**
  - Bluetooth (no connection on Nov 4; extra Linux setup).
  - Each provider recording its own folder (two clocks to align).
  - Sending the median frequency at rest (meaningless values) or guessing from other signals (hides real faults).
  - Rep timing from the space markers (depends on someone pressing space for every rep).

## 2026-11-05 — Raspberry Pi set: one tarball + installer; the bridge gets the real radar and records in the recorder's format
- **Decision:**
  - `deploy/pi/build_bundle.py` packs a versioned tarball with file hashes: git-tracked sources, the built dashboard,
    and every .py checked against Python 3.11 syntax.
  - `install.sh` makes a venv, installs `websockets`/`numpy`/`pyserial` (`--with-model` adds PyTorch), sets up
    `dialout` and a systemd service.
  - The bridge's radar provider reuses the model's preprocessing for its 3 maps and starts the radar with the
    existing profile. Dashboard Start/Stop writes recorder-format sessions.
  - Live model scores are left out of v0.1.
  - See [report](output/2026-11-05-2119-pi-software-set.md).
- **Why:**
  - One file to copy (SSD or `scp`) and one script to run suits a Pi with no screen.
  - The recorder format means `check_session.py`/`export_dashboard.py` work on Pi recordings unchanged.
  - Live scores would need a radar-only rep finder that doesn't exist, and a real-trained network.
- **Alternatives:**
  - A Debian package (more work, little gain now).
  - Docker (heavy on a Pi, serial-port passthrough).
  - Cloning the git repo on the Pi (needs git, a network and credentials; brings development files).
  - The bridge writing its own format (two formats to maintain).

## 2026-11-05 — Show the model through dashboard replays (`?replay=`) first; keep the radar's current settings for now
- **Decision:**
  - `model/export_dashboard.py` writes protocol-1.2 `.ndjson` replays. The dashboard opens them with a same-origin
    `?replay=` link, and the radar panel gets buttons for multiple views.
  - Replays live in the git-ignored `frontend/public/replays/` and are removed from `dist/` after a build.
  - The radar keeps `fullmap_awr2x44p.cfg` (P0). It gets measured with a person, not retuned.
  - See [report](output/2026-11-05-1844-dashboard-replay-radar-check.md).
- **Why:**
  - The user chose both: "Replay file" and "Only measure current".
  - A replay needs no installs (the bridge's packages wait for the Pi setup), and it already uses the dashboard's
    protocol, so the same messages can come live later.
  - P0's ±1.09 m/s limit may be too low for brisk curls, but that has to be measured before changing anything.
- **Alternatives:**
  - The bridge running live on the Mac (needs `websockets`/`numpy`).
  - Profiles P1–P4 (shorter idle or 2 TX, ±1.6–4.1 m/s at coarser speed bins).
  - Separate radar panels per view (empty panels for sources without them).

## 2026-11-05 — Radar-only network in `model/`: angle-FFT + phase input, session baseline, radar-time sync, fake data from real recordings
- **Decision:**
  - The network lives in a new `model/` (package `trnet`), untrained, with ~239.5k parameters. Its input
    (`v0-draft` contract):
    - `H [2,64,16]`: host angle FFT of the 8 azimuth antennas at their real columns (16 bins), as magnitude dB
      plus the frame-to-frame phase change (only in cells within 30 dB);
    - `D [1,64,16]`: range-Doppler (log2 Q8 → dB);
    - 128 frames per rep.
  - One sample = one set plus the **session's** first 3 reps as the baseline. Labels compare every rep with
    those reps; the MDF is smoothed over 3 reps.
  - The radar is the time reference. Pose and IMU offsets come from the 3 shrugs, using speed-like signals;
    sEMG is reported only.
  - Fake data replays real empty-room radar frames and the real jitter and Wi-Fi delay sequences.
  - Training: heads start at the training average, smooth-L1 for scores, positive weight ≤ 5×, Apple GPU.
  - See [report](output/2026-11-05-1316-neural-network-pipeline.md) and [plan](plans/2026-11-05-neural-network.md).
- **Why:**
  - Measured: the static heatmap's 8 values per range bin are antennas, not angles (a 13-wide aperture), so
    their raw magnitude holds almost no left/right information. The values are complex, so phase is available
    at 60 fps.
  - Fatigue builds across sets, and a per-set baseline would reset it.
  - Webcam delay (~60 ms) is the largest unknown offset, and labels must line up with the frames the network
    sees.
  - Real radar noise is coherent across antennas and slow, which independent noise doesn't reproduce.
  - The first fake run with plain Huber and 0.5 starting points didn't beat the mean baseline.
- **Alternatives:**
  - Raw 8-antenna magnitudes as the input (discards angle information).
  - Zero-padding to 64 angle bins (only interpolates).
  - A per-set baseline (resets fatigue).
  - Pose or IMU as the time reference.
  - Independent Gaussian noise for the fake radar (off by up to 6 dB).
  - Time-normalised reps (would break the phase/tremor timing).

## 2026-11-05 — IMU goes wireless over Wi-Fi (TCP), not Bluetooth; recorder clock fit through the lower edge
- **Decision:**
  - The IMU board streams over Wi-Fi with `WIFI_LINK 1`: one TCP client, port 3333, at `truerehab-imu.local`. A 32 KB buffer is sent by a core-0 task; USB output is unchanged.
  - The recorder reads `tcp://` with a plain socket (IPv4 lookup) and reconnects with marker rows.
  - `align_device_time` fits the drift through the least-delayed sample of each 2-s window.
  - See [report](output/2026-11-05-0012-imu-wifi-link.md) and [plan](plans/2026-11-04-imu-wireless.md).
- **Why:**
  - The user picked the recommended option. The Mac's Bluetooth serial link to the MyoWare wasn't connecting, TCP keeps every byte in order, and the build is 75 % of flash vs 85 % for Bluetooth.
  - Measured: Wi-Fi delivers in bursts with ~1-s pauses. The all-sample fit wandered 37 ms against the USB copy; the lower-edge fit stays a constant 4.1 ms apart.
- **Alternatives:**
  - Bluetooth Classic SPP: no recorder change, but it relies on the same flaky Mac Bluetooth path.
  - UDP: no retransmission, and the board would need the host's address.
  - BLE: GATT plus new host code.
  - IMU wired into the MyoWare ESP32: one shared clock, but the placement and wiring are limiting.

## 2026-11-04 — IMU firmware: one sketch, OLED on its own core, register driver, wide-range record counts
- **Decision:** One sketch (`sandbox/imu-mpu6050-oled/imu_mpu6050_oled/`) with LIVE and RECORD modes. IMU sampled in `loop()` on core 1; OLED drawn by its own task on core 0 on its own I2C bus. Registers driven directly; any chip whose settings read back is accepted. RECORD sends counts at the recorder's 16384/g and 131/(°/s) but measures ±4 g/±500 °/s (2 × register value), with `RECORD_WIDE_RANGE 0` for the old ±2 g/±250 °/s int16. Missed slots are skipped and counted, never burst. Accel calibration is stored in flash and applied to LIVE/OLED only; RECORD stays raw with the numbers in `#` lines. See [report](output/2026-11-04-2232-imu-firmware-fix.md).
- **Why:** Measured on the board: OLED writes stalled sampling ~29 ms (would lose ~25 % at 200 Hz); the chip is a 0x74 clone the Adafruit library rejects; |a| 0.88–1.05 g at rest. Elbow curls can pass 250 °/s, so ±250 °/s could clip, while the count scale stays the documented one. Raw record data keeps offline processing free to choose its own corrections.
- **Alternatives:** Adafruit MPU6050 library (rejects the chip); OLED split into page writes in the same loop (more fragile); MPU FIFO (clone FIFO sizes differ, harder timestamps); plain ±2 g/±250 °/s in RECORD (clips fast reps); applying calibration to RECORD lines (bakes one estimate into the data).

## 2026-11-03 - Synchronize local and teammate radar work
- User explicitly requested pull then push. Preserve a named local safety stash, pull through cc97005, reconcile context/decision conflicts and publish local radar demos/plans/reports with the unchanged poster reference.
- Keep both independent configurations: upstream radar-lab reports a 60-Hz heatmap benchmark; Windows browser demos use their separately verified 40-Hz point/health profile. Do not replace one benchmark with the other or run both serial collectors together. Plan B/no-DCA remains selected.
- Ignore generated Python bytecode; do not publish caches or environments. No hardware commands, firmware changes, installs or Pi setup for this Git operation. See [sync report](output/2026-11-03-repository-sync.md).

## 2026-11-03 — radar-lab: on-chip heatmaps over USB, 3D in pyqtgraph, 60 fps with both heatmaps
- **Decision:** A standalone `radar-lab/` folder reads the AWR2944PEVM's mmWave demo over USB serial. Clutter removal is off and the static (range-azimuth) and range-Doppler heatmaps are on, so still objects show. 3D = that map as a floor + the point cloud at its measured height, in `view3d.py` (pyqtgraph/PyQt6/PyOpenGL in `radar-lab/.venv`). It runs at 60 radar fps with both heatmaps; redraws follow the display. See [plan](plans/2026-11-03-radar-lab-fullmap.md), [plan](plans/2026-11-03-radar-lab-3d-60fps.md).
- **Why:** The board we have runs TI's UART demo (no Ethernet command), and the demo's point cloud drops everything still. Heatmaps need no flashing and no DCA1000. Measured: 601/601 frames at 60 fps with spare time. matplotlib can't draw 3D at 60 fps.
- **Alternatives:** LAN via TI's Ethernet firmware (needs flashing, sends points only); raw ADC via DCA1000 (not on hand); a browser three.js viewer with Web Serial (no install, but a JS rewrite); dropping the range-Doppler heatmap for 60 fps (not needed after measuring).

## 2026-11-03 — Complete separate car-style measured radar page
- User approved the written plan. `/drive/` now serves a separate automotive-style page from `sandbox/radar-car-demo/`, with an illustrative ego car, actual reflection groups/raw overlay, meter guides, nearest-return sectors and truthful live/stale metrics. No semantic vehicle/person/lane/path or physical-size inference.
- Same collector/profile, one approved service restart, new PID 36636. Start/Stop shared across pages; original Room map HTML hash unchanged. New page reload does not stop the stream. Original Close viewer still ends the shared service. Eleven focused checks and HTTP boundaries passed; both pages stopped at the same frame 5294, then restarted. Final screenshot frame 10609 is ~40-Hz live data with zero gaps/invalid packets in that session; earlier two-gap extended run remains recorded.
- Both localhost tabs left open. [Report, preview, run state and limits](output/2026-11-03-car-style-radar-demo.md). No firmware/SDK/main dashboard/Pi/source-poster changes, package install, commit or push.

## 2026-11-03 — Propose a separate car-style measured-radar demo
- User requests Tesla-car-style appearance as a separate demo. Proposed `/drive/` with its own source folder and an automotive scene, illustrative ego/sensor icon and unclassified measured reflection markers. Same collector/40-Hz profile; no second COM reader, synthetic traffic or inferred semantic classes/lanes/path.
- [Written plan](plans/2026-11-03-car-style-radar-demo.md) remains proposed awaiting repo-required OK. One server restart will load the route and reset the existing RAM map via its normal session reset. Existing Room map HTML/lifecycle stay intact. [Preparation](output/2026-11-03-car-style-demo-preparation.md).
- Current extended-run health includes one sequence gap; retain that fact. No implementation/runtime/firmware changes, commit or push in this preparation.

## 2026-11-03 — Complete approved stationary-board reflection mapping
- User replied OK to the written fixed-front-room map plan. Added bounded browser-only accumulation from actual incoming frame history: 30-s window, 10-cm display cells, >=3 distinct frames, max 2000 total cells, optional moving-return inclusion, separate accumulated/live layers and clear/pause/resume. Default view span 10 m changes only visualization. No RF/CFAR/firmware/backend change.
- Eleven focused checks passed; real browser verified growth, pause preserving 90 cells while frames advanced, zero after clear, mode/filter controls, frozen state on sensor stop, and new-session reset. Final preview frame 8679 shows 128 persistent cells, eight current points, ~40-Hz receive/display and zero gaps/invalid packets for that session. Existing earlier long-run gaps remain in the record.
- No SLAM, wall/mesh/free-space/complete-room or improved accuracy claim. Keep the board fixed and clear after moving. Map is RAM-only and paused/stopped maps are historical; same localhost tab left live. [Report, limits and screenshot](output/2026-11-03-fixed-radar-room-map.md). No poster/Pi/main frontend changes, commit or push.

## 2026-11-03 — Clarify fixed-board front-of-room mapping before implementation
- User chose stationary radar with accumulated front-of-room points, rather than moving/rotating 360-degree mapping. Proposed a bounded recent reflection map with clear/pause controls, measured-distance colors, persistent display cells and truthful unknown regions. No surfaces, SLAM or complete-room/physical-accuracy claim.
- [Map plan](plans/2026-11-03-fixed-radar-room-map.md) is proposed pending the repo's written-plan OK; no new code/RF/firmware changes yet. [Preparation](output/2026-11-03-fixed-radar-map-preparation.md).
- Extended 40-Hz health at this request shows one sequence gap after ~644 s; preserve this fact and loss counters. Prior short zero-gap runs do not guarantee losslessness or full spatial coverage. No commit/push.

## 2026-11-03 — Extended validation selects 40 Hz over experimental 45 Hz
- Supersedes the initial 45-Hz selection below. Extended live GUI operation logged one sequence discontinuity, `9354 -> 9356 during running`, despite a clean bounded benchmark and enlarged receive buffers. Root cause was not established; do not describe 45 Hz as lossless. The SDK still sends stats for zero detections, so this was not intentional zero-object suppression.
- Final default is `tdm-wide-points-40hz.cfg`, target 40 Hz with more reserve; nominal 3.8839-cm range separation, true 3D coordinates, warm/cool distance colors and actual-frame queue delivery are retained. 45/48-Hz profiles remain experimental. Current process PID 42784, same localhost URL. [Evidence and limits](output/2026-11-03-radar-rate-resolution.md). No firmware flash/commit/push.
- Final 40-Hz health: 4748 consecutive frames over 118.6 s, zero gaps/invalid packets, 25.0% minimum reserve and maximum valid sensor temperature 56 C. Final browser preview later shows frame 5164, about 40 displayed unique frames/s and zero gaps. Seventeen final tests, 151-frame regression, syntax and access rejection checks passed.

## 2026-11-03 — Apply approved tuning: 45-Hz measured 3D view with nominal 3.88-cm range separation
- User said "apply all those changes please" after the 10-Hz explanation; the existing tuning plan is now completed. Selected `tdm-wide-points-45hz.cfg`, wider sampled bandwidth 3.8595 GHz, nominal radial separation 3.8839 cm. Same antenna geometry/detection thresholds; unused range-profile telemetry disabled in this viewer profile. Original 10-Hz waveform/output remains rollback. No absolute/angle/body accuracy or full-5-GHz-chirp claim.
- Bounded 45-Hz 60-second test passed with 2709 frames, zero gaps/invalid packets, 10.67% minimum transport-inclusive reserve and confirmed stop. 48 Hz was rejected below the 10% margin criterion. Final GUI reached frame 7062 at about 45 receive / 45 displayed unique frames/s, zero gaps/invalid packets after enlarged receive buffers; one earlier UI-run discontinuity remains documented in the report.
- Added real-frame cursor/queue delivery, HTTP latency improvements, timing/temperature/profile indicators, paced/acknowledged stop and explicit stop errors. Seventeen tests, 151-packet regression, queue/projection checks and local access rejection passed. Final process PID 46872, same localhost URL. [Report and limits](output/2026-11-03-radar-rate-resolution.md). No firmware flash, source poster edit, Pi install, commit or push.

## 2026-11-02 — Propose camera controls for measured 3D radar points
- User asks for a 3D-camera-like view after the distance heatmap. Existing packets have x/y/z, so the proposed host-only change adds perspective, orbit/zoom and view presets, keeping measured range colors and truthful point-cloud limitations.
- [Plan](plans/2026-11-02-3d-radar-view.md) remains proposed awaiting OK under the repo's explicit non-trivial-work gate. No 3D code, acquisition tuning or firmware changes made yet; completed distance heatmap remains active.

## 2026-11-02 — Use existing measured distance for the requested heatmap colors
- User explicitly requested nearby reflections appear hotter and distant reflections cooler. Applied a small reversible rendering change to the existing local graph: 3D range controls color, with an updated distance legend and illustrative halos around measured dots. Empty areas remain unmeasured; colors do not represent temperature, intensity, body segmentation or fatigue.
- Actual browser verified the new graph and increasing live frames at unchanged 10-Hz receiver rate. This request does not approve the separate proposed rate/resolution optimization. No firmware/profile/server changes, commit or push. [Report](output/2026-11-02-distance-heatmap.md).

## 2026-11-02 — Separate measurement FPS, display refresh, resolution and accuracy
- User requested near-limit frame rate and precision. Read-only audit found 10-Hz measurement but 250-ms browser polling (~4 visible updates/s). Previous graph-rate wording described receiver throughput, not actual display refresh.
- Existing 151-frame timings imply a rough ~46-Hz waveform+processing+UART ceiling before headroom in the tested scene; 64.26 Hz excludes processing/transport. Range separation is ~4.36 cm, not guaranteed accuracy. No runtime change made.
- [Staged tuning plan](plans/2026-11-02-radar-rate-resolution.md) remains **proposed**, awaiting OK under the explicit repository plan gate. No reflash, commit or push. [Audit](output/2026-11-02-radar-rate-resolution-audit.md).

## 2026-11-02 — User-approved separate local live graph substitutes for unavailable TI GUI
- **Authority:** User explicitly approved adding a local real-data graph through the confirmation question. Both official TI 4.7 launch and linked Windows application-download URLs redirected to TI's error page; do not imply a global outage or reflash working firmware for a host-site problem.
- **Implementation:** Separate `sandbox/radar-live-viewer/` uses existing isolated Python/pyserial plus standard-library loopback HTTP; unchanged official TDM profile; COM5/COM6. No new packages, browser extension, Cloud Agent, external upload, firewall setting, main frontend or Pi bridge changes. It clearly labels real/stopped/stale states; never uses replay/synthetic fallback or clinical scores.
- **Verification:** Nine parser/state unit tests and all 151 independently TI-validated captured packets passed. Actual visible graph updates ~10 Hz; Stop released ports, Close exited the first process and restart succeeded. HTTP control without token and invalid Host both returned 403. Final sampled 615 frames with zero invalid packets/gaps. Final server PID 40248, http://127.0.0.1:8766/, left live with 15-min limit and 15-s client-loss stop.
- **Scope:** This completes approved hardware/data/graph bring-up via the user's alternative display, not TI GUI compatibility or AI/dataset readiness. [Report](output/2026-11-02-local-live-radar-viewer.md). No commit or push.

## 2026-11-02 — Verify real UART output independently of GUI availability
- **Result:** After the user restored functional mode and asked to test directly, COM5 returned AWR2X44P/TDM/SDK 04.07.02.01. The unchanged TI AWR2944P TDM profile ran successfully. A 15-second COM6 capture contains 196192 bytes, 151 consecutive frames (1-151), 3-8 points/frame, and no observed sequence gaps or malformed packets. TI's official parser independently accepted all 151 frames.
- **Boundary:** This is real processed point cloud/range-profile/stats output, not raw ADC, a Range-Doppler heatmap or validated muscle-fatigue inference. Stop the sensor and release ports after the bounded test. TI GUI success is not claimed: the exact official 4.7 visualizer URL redirected to TI's unavailable-page notice. Do not reflash to solve a website problem.
- **Evidence:** [Test report](output/2026-11-02-awr2944p-real-data-smoke-test.md), task-local binary capture, CLI log, JSON metrics, official parser log and point CSV. No remote writes or Git commit/push.

## 2026-11-02 — Official AWR2944P demo written and verified; require normal boot before claiming a live demo
- **Result:** With explicit user approval, a matching jumper photo and user-confirmed power/reset, COM5 returned ROM CCC. The unmodified TI utility wrote the official QSPI SBL at 0x0 and AWR2x44P TDM demo at 0xA0000; each region separately passed flashverify. Four log files each contain SUCCESS and no ERROR/traceback.
- **Next gate:** Power off BOTH supplies before returning SOP2/SOP1/SOP0 to 0/0/1, then restart and prove the version/banner and live packets. No live radar or visualizer success is claimed merely from successful flash.
- **Boundary:** No mass erase, alternate/security image, custom firmware, Pi setup, network/firewall changes, SDK modification, poster edit, commit or push. [Evidence report](output/2026-11-02-awr2944p-flash-success-awaiting-qspi.md).

## 2026-11-02 — Approve official AWR2944P TDM demo flash with physical boot-mode gate
- **Decision:** User explicitly approved the TI demo flash plan and supplied photos identifying AWR2944PEVM PROC194 REV. A with dedicated 12-V power and XDS_USB. Use SDK 04.07.02.01's AWR2x44P TDM demo and matching flash writer/SBL, not non-P/ECO/LC/HS images or the SDK default CCS-debug image.
- **Prepared:** Task-isolated Python environment and pyserial/tqdm/xmodem, copied vendor binaries with SHA-256 checks, separately parsed bootloader/app flash and verify configurations. Do not alter installed TI files or paused Pi bridge dependencies.
- **Gate:** No device flash write has occurred. Require photo/physical confirmation of UART SOP mode, stable power during writing, successful verification after each region, then a user-controlled return to QSPI boot and actual demo output verification. No commit/push, network changes or poster edits.
- **Details:** [Approved plan](plans/2026-11-02-awr2944p-demo-flash.md), [preparation report](output/2026-11-02-awr2944p-flash-preparation.md).

## 2026-10-18 — Raspberry Pi is required; source the full no-DCA hardware list
- **Decision:** Per the user, add Raspberry Pi 5 8GB to REQUIRED for the prototype, including official Active Cooler, 27-W USB-C power and default 128-GB microSD. Keep notebook acquisition first. Case/display/reader and NVMe remain recommended or conditional, not automatic duplicate purchases.
- **Sources:** [Purchase-link register](plans/2026-10-18-plan-b-purchase-links.md) includes the four fixed MyoWare SKUs, Pi sources in Thailand and candidates for the infographic's other hardware. New accessory candidates are not marked ordered, and availability/delivery must be checked at checkout.
- **Boundary:** DCA1000 stays excluded. Existing quote totals are subsets and omit Pi and many accessories. The poster is unchanged; no commit or push.

## 2026-10-18 — Plan B excludes DCA1000 entirely
- **Decision:** The user clarified that Plan B will not use DCA1000, including as a deferred upgrade. Remove the capture card, its 5-V supply and Samtec/LVDS capture cable from the active purchase list and graphic. Earlier deferred-upgrade wording below is superseded.
- **Implementation:** AWR2944PEVM performs onboard processing and sends supported or custom reduced output over Ethernet. Start with official OOB output, then develop and verify the Range-Doppler/complex-phase representation required by the model. Full DCA-equivalent raw ADC is not promised.
- **Boundary:** Retain Raspberry Pi, MyoWare, IMU and experiment equipment in their respective development/prototype stages. DCA1000 remains mentioned only to explain the frozen submitted design and historical decisions. No poster edit, commit or push.

## 2026-10-18 — Plan B AWR2944PEVM selected
- **Decision:** Use Plan B, AWR2944PEVM without DCA1000 for initial bring-up. Plan A XE125 is rejected for the current build. This is selected, not ordered, until an order confirmation and delivery date are recorded.
- **Why:** AWR2944PEVM preserves the poster's TI 76–81-GHz FMCW class, 4TX/4RX angular sensing and Range/Doppler architecture better than the 60.5-GHz single-channel XE125. It is directly compatible with DCA1000 if raw capture hardware becomes available later.
- **Complete hardware:** AWR2944PEVM; GST60A12-P1J; grounded IEC C13 mains cord; MyoWare 2 DEV-27924; Wireless Shield DEV-23387; three SEN-12969 electrode packs; conditional USB-C cables; Windows notebook with USB and wired Ethernet. See [complete list](plans/2026-10-18-hardware-procurement-options.md#final-plan-b-complete-hardware-list).
- **Boundary:** The poster remains unchanged. AWR2944PEVM replaces AWR1843BOOST, and initial onboard processing plus Ethernet replaces DCA1000 raw capture. Disclose both changes. Do not attempt a homemade DCA card within the schedule.

## 2026-10-18 — The submitted poster's 77-GHz and TI-hardware commitments count against Plan A
- **Decision:** Treat consistency with the submitted poster as a radar selection criterion. Plan A (XE125, 60 GHz) contradicts the poster's 77-GHz radar label and its operation flowchart naming AWR1843BOOST + DCA1000EVM. Plan B (AWR2944PEVM, 76–81 GHz, one radar) is still a substitution but remains within the TI 76–81-GHz FMCW ecosystem and is the closer emergency implementation. See [procurement plan](plans/2026-10-18-hardware-procurement-options.md).
- **Why:** The submitted `TrueRehub-RF .pdf` must not be edited. Its flowchart says `Connect AWR1843BOOST`, `Connect DCA1000EVM`, and `Collect radar data (AWR1843BOOST + DCA1000EVM)`, followed by Range FFT, Doppler FFT and a Range-Doppler map. The hardware must change for availability reasons, so the replacement should preserve as much of that frequency class and processing architecture as possible.
- **Additional technical reason:** The poster connects the radar to micro-scale subtle-motion changes, joint/body movement patterns, overall body posture, movement quality, estimated fatigue and compensation risk. XE125/A121 is a single-channel 1TX/1RX radar: it can measure distance and coherent phase but cannot directly estimate angle. AWR2944PEVM's 4TX/4RX angular hardware is a much closer match to the broader movement/posture claims.
- **Boundary:** Plan B does not fully match the poster because it replaces AWR1843BOOST and initially omits DCA1000; this must be disclosed as an availability-driven implementation change. Poster consistency does not remove Plan B's schedule risk: selected complex phase data for muscle micro-vibration still needs custom firmware. Neither plan is ordered.
- **Alternatives:** Plan A with a spoken substitution explanation (about ฿27,380 cheaper with phase data out of the box, but contradicts the poster's frequency, named hardware and processing path). Multiple XE125 units would increase cost/complexity and diverge even further from the submitted flowchart.

## 2026-10-18 — Separate required validation hardware from two radar purchase options
- **Decision:** Treat MyoWare 2 DEV-27924, Wireless Shield DEV-23387 and three SEN-12969 electrode packs as required validation equipment. Choose one radar track: **Plan A** XE125 60-GHz EVK at the lower budget, or **Plan B** AWR2944PEVM plus GST60A12-P1J supply for the closer 76–81-GHz implementation. USB-A-to-C cables are conditional on existing inventory. See [procurement plan](plans/2026-10-18-hardware-procurement-options.md).
- **Why:** sEMG provides development ground truth regardless of radar choice, while the two radar options have very different cost, software and data interfaces and should not be conflated or accidentally ordered together.
- **Boundary:** Prices are user-provided DigiKey Thailand quotations from 2026-10-18 and are not checkout guarantees. Neither radar option is marked ordered. XE125 already includes XM125/A121; AWR2944PEVM without DCA1000 does not provide automatic full raw ADC capture.
- **Safety:** Use the MyoWare assembly wirelessly from its included battery while attached to a person; disconnect electrodes before USB charging/programming. The prototype and electrodes are not medical diagnostic devices.

## 2026-10-18 — Provisional AWR2944PEVM implementation without DCA1000
- **Decision:** Keep AWR1843BOOST + DCA1000EVM as the frozen submitted design, but prepare AWR2944PEVM as the current implementation candidate if it can arrive within the schedule. Without DCA1000, run the high-rate Range/Doppler processing on AWR2944P and transmit reduced data over Ethernet. Bring up OOB detected objects first; then try Range-Doppler and selected complex Range-FFT bins. Full continuous raw ADC capture is not an initial deliverable. See [plan](plans/2026-10-18-awr2944-no-dca.md).
- **Why:** The original two boards are difficult to source in time, while AWR2944PEVM may arrive sooner and contains R5F, C66x, HWA/EDMA and Ethernet resources for standalone processing.
- **Alternatives:** Wait for AWR1843BOOST+DCA1000 (preserves the raw-data research workflow but risks missing the deadline); build a custom DCA-like FPGA capture board (far beyond the schedule); use a different 60-GHz module (simpler acquisition on some platforms but diverges further from the submitted 77-GHz design).
- **Boundary:** This is a local engineering plan, not confirmation that the board has been ordered or tested. Software cannot by itself reproduce DCA1000's LVDS/Aurora capture hardware.

## 2026-10-12 — Home page: no template tells; rules kept in `frontend/DESIGN.md`
- **Decision:** The live demo sits directly under the hero. "How it works" is a plain numbered list, and "Why radar" is a Camera / Wearables / Radar table. There are no uppercase eyebrows and no rows of identical shadowed cards. The rules and "don'ts" live in `frontend/DESIGN.md`. See [plan](plans/2026-10-12-home-ai-slop-pass.md).
- **Why:** These were the "AI slop" tells from the video (youtube.com/watch?v=M4DNgmI7MIM) still left after the restyle. Showing the real product early is the most specific visual we have.
- **Alternatives:** Keep the cards and only drop the eyebrows (still reads as a template). Remove uppercase from dashboard panel titles too (kept, because they are dense UI labels).

## 2026-10-12 — Home page first, with hash routing (no router library)
- **Decision:** `#/` is an Apple-style landing page (`frontend/src/home/`), `#/app` is the dashboard. `Root.tsx` picks the route. Opened from a Pi bridge or with `?pi=`, it skips the landing page and goes straight to the dashboard. The page's live preview runs its own nested `SensorProvider` with `MockSource`, so it never touches the real connection. See [plan](plans/2026-10-12-home-page.md).
- **Why:** The user needed something to present first; the old first screen was "Connect your kit". Two routes don't justify a router package, and the Pi-served page must still open on live data.
- **Alternatives:** A router library (heavier for two routes); making the connect screen prettier (no story, no demo); a static preview image (not live).

## 2026-10-12 — Logo: "TR" monogram, SF Rounded outlined to SVG, mono
- **Decision:** The header logo is a rounded-square tile with "TR" (SF Rounded Bold), drawn as an inline SVG in `frontend/src/App.tsx`. The letters are traced outlines, not text, so no font is needed. Mono colours that flip with the theme (`currentColor` tile, `var(--bg)` letters); no gradients.
- **Why:** The first logo (CSS-gradient arcs) was disliked, and the user wanted something other than blue. Outlines look identical on every device and offline on the Pi. Mono avoids a second bright colour next to the blue accent and the status colours.
- **Alternatives:** Pulse tile, joint angle, target rings, wave, "shape with a ghost" (true vs compensation) and coloured versions; Mistral (Adobe font, can't be bundled); live text in SF Rounded (only looks right on Apple devices).
- **Open risk:** Apple licenses SF fonts for Apple platforms, so using outlines of them in a public logo is a grey area. For a poster or product logo, redo it with a clearly licensed rounded font (e.g. Nunito).

## 2026-10-12 — Dashboard look: Fluent-style neutrals, Inter, floating rounded rectangles, no gradients
- **Decision:** Neutral greys + one blue accent (`#0f6cbd` light / `#479ef5` dark), muted green/amber/red only for status. Font: Inter + Noto Sans Thai, bundled with `@fontsource` so it works offline on the Pi. Every container is a floating card (layered `--float` shadow, 16px radius); small controls use 10px; no pills. No CSS gradients anywhere. All of it lives in `frontend/src/styles/theme.css`. See [plan](plans/2026-10-12-dashboard-restyle.md).
- **Why:** The first teal/cyan-on-navy palette looked like generic AI styling. The user chose the Microsoft-like direction and wanted a calm, clinical feel. Bundled fonts keep the Pi demo offline-safe.
- **Alternatives:** Apple-like or OpenAI-like neutrals; IBM Plex Sans; Google Fonts CDN (needs internet); frosted-glass surfaces (tried, dropped because there are no gradients to blur); real Liquid Glass refraction (Chromium-only SVG filter).

## 2026-10-11 — Protocol 1.1: the Pi describes itself; Python reference bridge
- **Decision:** Each Pi sends a `hello` with a manifest of every stream (labels, units, score direction, radar axes, device links, accepted commands). The dashboard labels itself from it and checks that each stream arrives. Commands (`session.start/stop`, `marker`) go back with `ack` replies. The reference Pi side is `pi-bridge/` (Python, `websockets`). It also serves the dashboard over HTTP, so users open `http://<pi>.local:8080` and nothing needs typing. `check_bridge.py` verifies any bridge. See [plan](plans/2026-10-11-easier-ui-and-pi-bridge.md).
- **Why:** Hardcoded labels in the web break as soon as the Pi changes. A manifest + checker proves the Pi sends everything the page needs. Serving the page from the Pi removes the hardest setup step.
- **Alternatives:** MQTT broker (from the multi-kit plan): deferred until 2+ kits; `kitId`/`sessionId` are already in the envelope. Keeping labels in the frontend config: drifts from the Pi.

## 2026-10-10 — Dashboard in TypeScript (replaces Streamlit), WebSocket protocol v1
- **Decision:** The dashboard is a Vite + React + TypeScript app in `frontend/` with no UI framework and canvas plots. Sensors reach it through one `SensorSource` interface: a WebSocket from the Pi bridge (binary `TRF1` radar frames + JSON for everything else, each with a seq number and Pi timestamp), Web Serial for an Arduino, or replay. See [plan](plans/2026-10-10-typescript-frontend.md).
- **Why:** The user asked for TypeScript and fully customizable components. Browsers can't receive UDP, so the Pi must speak WebSocket over Wi-Fi. Binary frames keep a 64×64 map at 20 fps around 2.6 Mbit/s. Sensor timestamps keep the plots right despite Wi-Fi jitter.
- **Alternatives:** Streamlit (from the Oct 5 plan: one language, but less control and a weaker live demo). JSON/base64 frames (about 4× heavier). A chart library (lock-in, slower for heatmaps).

## 2026-10-08 — Frame encoder v0.1 design (sandbox)
- **Decision:** A CNN frame encoder that accepts any input size (`[B,C,H,W]` gives `[B,E]`, E=128), with GroupNorm, pooling only while an axis stays ≥ 4, and an `InputContract` saved alongside the weights. It lives in `sandbox/Encoder_0.1/` (user choice) rather than the `truerehab-rf/` layout. See [plan](plans/2026-10-08-frame-encoder.md).
- **Why:** There is no real chirp config yet, so the input view and shape must stay open. Batches will be small. The contract stops a model being fed differently preprocessed data.
- **Alternatives:** A fixed range-Doppler input (could rule out micro-Doppler or range-time views). BatchNorm (unstable with small batches).

## 2026-10-05 — ML stack and 6-week scope (proposed to team)
- **Decision:** Python end to end: numpy/scipy processing, MediaPipe + LSL for labels and sync, scikit-learn baselines then a small PyTorch CNN, leave-one-subject-out evaluation, Streamlit demo. Scope to 15 Nov: Phase 1 + 3 working, Phase 2 exploratory, Phases 4–7 as demo/future work. See [plan](plans/2026-10-05-ml-plan-and-stack.md).
- **Why:** No data yet and ~6 weeks; data collection is the bottleneck. Small data favours simple models and strict subject-wise evaluation.
- **Alternatives:** MATLAB for processing (splits the codebase, harder on Pi 5); all 7 phases by Nov 15 (unrealistic without multi-session data).

## 2026-10-05 — Adopted CLAUDE/ workspace via /initiate-project
- **Decision:** Keep project context, decisions, session reports and plans in `CLAUDE/`; root `CLAUDE.md` points to it.
- **Why:** Every session starts oriented and leaves a trail.
- **Alternatives:** A single root CLAUDE.md — gets long and mixes stable facts with changing state.
