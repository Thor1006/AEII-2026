# Context

<!-- Living state. Keep under ~40 lines; reports hold detailed run history. -->
**Last updated:** 2026-11-05 19:21 (first radar recording with a person: speed limit OK at ~1 m; IMU wiring fails on the arm)

## Current focus
**Plan B is selected and received: AWR2944PEVM, no DCA1000.** The submitted AWR1843BOOST/DCA1000 poster stays frozen. Two independent USB radar demos now coexist; their profiles, outputs and measured limits differ. Run only one serial collector at a time. No raw ADC or validated fatigue/body model is claimed.
- Windows browser viewer: `sandbox/radar-live-viewer/`, AWR2X44P TDM / SDK 04.07.02.01, COM5 115200 / COM6 3125000. Selected `tdm-wide-points-40hz.cfg`: 40-Hz target, nominal 3.88-cm radial separation, point/health output. [Measured limits and rollback](output/2026-11-03-radar-rate-resolution.md); extended runs had occasional sequence gaps. Last recorded server PID 36636 is historical, not a current health check.
- Browser Room map http://127.0.0.1:8766/ and separate Drive view http://127.0.0.1:8766/drive/ share that collector. [Room map](output/2026-11-03-fixed-radar-room-map.md): fixed-board, 30-s RAM window, 10-cm display cells, >=3-frame persistence. [Drive](output/2026-11-03-car-style-radar-demo.md): illustrative car and measured reflection groups; no vehicle/person/lane/path recognition.
- Teammate's `radar-lab/`: independent macOS 2D/3D viewer with static range-azimuth and range-Doppler heatmaps. Its different profile reportedly measured 60.0 radar fps, 601/601 frames; this is not a new benchmark of the Windows 40-Hz profile. [Report](output/2026-11-03-2214-radar-lab-fullmap-3d.md), `radar-lab/README.md`. Height comes only from sparse measured points; angular orientation is unverified there. Stop-on-close verified on the board Nov 4 (type `sensorStop` slowly at 60 fps).
- Received: radar/power, MyoWare + Wireless Shield + 30 pads, Pi 5 8GB + cooler + 27-W PSU + 64-GB A2 microSD, Micro-HDMI, SSD and USB-C LAN adapter. UART is verified; Ethernet/custom phase, ground-truth synchronization, clinical inference and Pi deployment remain unverified.
- **`model/` (new, untrained):** radar-only network and its pipeline, all tested without sensors. [Report](output/2026-11-05-1316-neural-network-pipeline.md), `model/README.md`.
  - Network: 239,515 parameters. Input `v0-draft`: angle FFT + phase `[2,64,16]`, range-Doppler `[1,64,16]`, 128 frames per rep.
  - Labels use placeholder thresholds. `check_session.py` runs after each recording. Fake data replays real empty-room radar frames and the real timing.
  - 60 tests. On fake data it beats the baseline for 5 of 6 heads (plumbing only). No real session with a person exists yet.
  - Dashboard: `model/export_dashboard.py` writes a replay that `frontend/` opens with `?replay=/replays/<file>.ndjson`. The radar panel switches between 3 views. Live mode waits for the Pi. [Report](output/2026-11-05-1844-dashboard-replay-radar-check.md).
- `sandbox/Encoder_0.1/` and the existing AI/dashboard demos still use synthetic input. `frontend/` (home/dashboard, EN/TH/zh-HK, session history) and `Phisit/` (teammate's FastAPI/React demo) are unchanged.
- Ground truth, all into `recorder/` ([plan](plans/2026-11-04-recorder.md)):
  - **MyoWare 2.0 sEMG:** tested with `firmware/myoware_demo/`. `firmware/myoware_record/` compiles but has never run. On Nov 4 the Mac listed it "Not Connected" over Bluetooth, and its port gave 0 bytes.
  - **IMU board** (`sandbox/imu-mpu6050-oled/`, chip 0x74 clone, [fix report](output/2026-11-04-2232-imu-firmware-fix.md)): now runs fw 2.1 RECORD + Wi-Fi at `tcp://truerehab-imu.local:3333`. Verified on the board: 200 Hz, byte-identical to USB, reconnects, timing 4.1 ms constant vs USB ([report](output/2026-11-05-0012-imu-wifi-link.md)). Wi-Fi password in the git-ignored `wifi_secrets.h`. 6-face accel calibration not yet run.
  - **Video pose** (MediaPipe): verified live on the MacBook webcam, camera 0. The camera only opens from the user's terminal, not from Claude's shell. Not yet recorded with the radar.
- **Paused by user:** do not install `pi-bridge/` packages (`websockets`, `numpy`) until actual Pi setup; ask then. The bridge has not run.

## Recent changes
- 2026-11-05 - Project-wide check: every runnable suite passes with 0 warnings; all 4 firmware builds compile.
  - Bug fixes pushed as 4 small commits: the training warning, radar-lab's open config file, recorder test leaks, and 7 bugs in `ml_Try-1.py`.
  - [Report](output/2026-11-05-2040-project-audit.md).
- 2026-11-05 - First radar recording with a person (current settings, IMU on the forearm, spoken cues).
  - At ~1 m, 95 % of the arm's moving echo stayed under 0.7 m/s, with ≤ 0.2 % at the ±1.09 m/s edges and no wrap-around: fast enough.
  - The IMU lost half its data on the moving arm (I²C errors). Left/right still undetermined.
  - [Report](output/2026-11-05-1921-radar-curls-measurement.md).
- 2026-11-05 - The model is shown in the dashboard (replay link, radar view buttons, translations); typecheck, i18n and report checks pass; verified in the browser.
  - Radar smoke test with the current settings: 60 fps, 0 missing; IMU 200/s over Wi-Fi.
  - The user chose to keep the radar settings (measure only). The person runs are still to do.
  - [Report](output/2026-11-05-1844-dashboard-replay-radar-check.md).
- 2026-11-05 - Built `model/`: network, pipeline, session check, calibration, fake data and leave-one-subject-out training; 57 tests pass.
  - Found: the heatmap's 8 values are antennas, not angles. 2 of the 6 IMU recordings are firmware simulations. The two empty-room radar recordings differ by up to 38 dB.
  - [Report](output/2026-11-05-1316-neural-network-pipeline.md).
- 2026-11-03 - User requested pull then push. Pulled MyoWare wireless sketch and `radar-lab/` commits through `cc97005`; reconciled context/decision conflicts while preserving both implementations and evidence. See [sync report](output/2026-11-03-repository-sync.md).

## Open questions
- Freeze the input contract (v0-draft: radar-lab profile, angle FFT + phase `[2,64,16]`, range-Doppler `[1,64,16]`)?
  - Open: frames per rep. T = 128 crops 58 % of the fake 2.0–2.9-s reps.
  - Open: whether the phase channel carries muscle signal.
  - The recording protocol is in `model/README.md`. The browser's fast point output is a different input.
- Label thresholds and recommendation numbers are placeholders: they need a physiotherapist.
- Can phase/micro-vibration output be exposed within schedule? Ethernet is not verified; changing firmware still requires approval.
- Validate radar-lab left/right and antenna ordering with the actual board (stop-on-close verified Nov 4). Investigate Windows long-run sequence gaps without hiding them.
- IMU on the body: solid wiring/strain relief and mounting position. Record default is ±4 g/±500 °/s at the 16384/131 count scale (values can pass int16); confirm or switch to `RECORD_WIDE_RANGE 0`. Wi-Fi pauses ~1 s now and then (Mac or router?); harmless for recordings, would delay a live display.
- Why won't the MyoWare connect to this Mac over Bluetooth (another device holding it, or a stale pairing)?
- Shoulder visibility/mounting, merging the two dashboards, team roles and healthy-volunteer ethics remain open. No patient trials yet.
- Repo instructions describe macOS/zsh, but Windows work also exists. Home copy/font license and the poster's "oral health" wording remain open; submitted sources stay unchanged.

## Next steps
0. **Fix the IMU wiring for the arm** (solder or a locking connector, cable taped down). On the arm it had 179 I²C errors and lost 36 of 72 s. Then redo the curls run with it.
   - Left/right test with a still metal object (tray or laptop lid) at radar height, ~1 m in front, then to the left, then to the right.
1. **First full test session:**
   - Hardware: radar (power first, then USB); MyoWare (re-pair Bluetooth, upload `myoware_record`, battery only on a person); IMU over Wi-Fi from a power bank with wire strain relief; webcam pose started from the user's terminal.
   - Protocol from `model/README.md`: 5 s still, `s` + 3 shrugs, sets with space per rep.
   - Then run `model/check_session.py` and `python -m trnet.calibrate`. Run the IMU's 6-face accel calibration once.
   - After that: choose T, freeze contract v1, and train with `train.py --sessions` once there are ≥ 3 people.
1. Before switching demos, stop the current collector and release serial ports. Browser Start/Stop affects both pages; original Close viewer shuts their shared service. Never run radar-lab alongside it on the same board.
2. Browser safety stops: 15 min/session, 15 s without polling, valid temperature >=85 C, or reserve <5% for three frames. Start resumes a new session; do not reflash merely to reopen.
3. Validate radar-lab known-target angular orientation, then agree recording scope, preserve frame/config/timestamp/loss metadata, and freeze a real versioned `InputContract` before training or bridge integration.
4. Upstream follow-ups: Reps panel continues after session end; Python bridge `session_end` lacks `reps`. (`sandbox/ml_Try-1.py` fixed on 2026-11-05: it trains and runs to the end.)
5. Ask before Pi package setup; later run its tests and bridge checks. Reuse verified acquisition/parser components only after matching their actual output contract.
