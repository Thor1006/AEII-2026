# Context

<!-- Living state. Keep under ~40 lines; reports hold detailed run history. -->
**Last updated:** 2026-11-09 (public clinical and fatigue dataset review)

## Current focus
**Plan B is selected and received: AWR2944PEVM, no DCA1000.** The submitted AWR1843BOOST/DCA1000 poster stays frozen. Two independent USB radar demos now coexist; their profiles, outputs and measured limits differ. Run only one serial collector at a time. No raw ADC or validated fatigue/body model is claimed.
- Windows browser viewer: `sandbox/radar-live-viewer/`, AWR2X44P TDM / SDK 04.07.02.01, COM5 115200 / COM6 3125000. Selected `tdm-wide-points-40hz.cfg`: 40-Hz target, nominal 3.88-cm radial separation, point/health output. [Measured limits and rollback](output/2026-11-03-radar-rate-resolution.md); extended runs had occasional sequence gaps. Last recorded server PID 36636 is historical, not a current health check.
- Browser Room map http://127.0.0.1:8766/ and separate Drive view http://127.0.0.1:8766/drive/ share that collector. [Room map](output/2026-11-03-fixed-radar-room-map.md): fixed-board, 30-s RAM window, 10-cm display cells, >=3-frame persistence. [Drive](output/2026-11-03-car-style-radar-demo.md): illustrative car and measured reflection groups; no vehicle/person/lane/path recognition.
- Teammate's `radar-lab/`: independent macOS 2D/3D viewer with static range-azimuth and range-Doppler heatmaps. Its different profile reportedly measured 60.0 radar fps, 601/601 frames; this is not a new benchmark of the Windows 40-Hz profile. [Report](output/2026-11-03-2214-radar-lab-fullmap-3d.md), `radar-lab/README.md`. Height comes only from sparse measured points; angular orientation is unverified there. Stop-on-close verified on the board Nov 4 (type `sensorStop` slowly at 60 fps).
- Received: radar/power, MyoWare + Wireless Shield + 30 pads, Pi 5 8GB + cooler + 27-W PSU + 64-GB A2 microSD, Micro-HDMI, SSD and USB-C LAN adapter. UART is verified; Ethernet/custom phase, ground-truth synchronization, clinical inference and Pi deployment remain unverified.
- **`model/` (new, untrained):** radar-only network and its pipeline, all tested without sensors. [Report](output/2026-11-05-1316-neural-network-pipeline.md), `model/README.md`.
  - Network: 239,803 parameters. Input `v1` (2026-11-08): H `[4,64,32]` = angle FFT, phase, and the radar's own points as height + presence (0.25 s pooled); range-Doppler `[1,64,16]`; 128 frames per rep. [Report](output/2026-11-08-1704-points-and-finer-heatmap.md).
  - Points agree with the heatmap (+11 dB on real recordings) but a still target's height jitters ±0.16–0.25 m; on fake data the point layers HURT the model (shrug F1 0.49 vs 0.60 without). Decision pending.
  - Labels use placeholder thresholds. `check_session.py` runs after each recording. Fake data replays real empty-room radar frames and the real timing.
  - 73 tests. On fake data it beats the baseline for 5 of 6 heads (plumbing only). No real session with a person exists yet.
  - Without pose or IMU, reps come from the sEMG envelope (fallback): then only fatigue can be labelled.
  - Dashboard: `model/export_dashboard.py` writes a replay that `frontend/` opens with `?replay=/replays/<file>.ndjson`. The radar panel switches between 4 views (incl. "Points (height)"). Live mode waits for the Pi. [Report](output/2026-11-05-1844-dashboard-replay-radar-check.md).
- `sandbox/Encoder_0.1/` and the existing AI/dashboard demos still use synthetic input. `frontend/` (home/dashboard, EN/TH/zh-HK, session history) and `Phisit/` (teammate's FastAPI/React demo) are unchanged.
- Ground truth, all into `recorder/` ([plan](plans/2026-11-04-recorder.md)):
  - **MyoWare 2.0 sEMG:** runs `firmware/myoware_record` with the Wi-Fi link since 2026-11-07 ([report](output/2026-11-07-1601-myoware-upload.md)): `tcp://truerehab-myoware.local:3334`, 1000.1 samples/s, 0 gaps, RSSI ~-45 dBm, and the Pi bridge's check passes with the real board. Not yet worn. Power switch must be ON (it cuts the ESP32 even on USB). On this Mac its CH340 USB port (`/dev/cu.usbserial-*`) can't do 921600 baud: upload with `UploadSpeed=115200`, read the data over Wi-Fi.
  - **IMU board** (`sandbox/imu-mpu6050-oled/`, chip 0x74 clone, [fix report](output/2026-11-04-2232-imu-firmware-fix.md)): now runs fw 2.1 RECORD + Wi-Fi at `tcp://truerehab-imu.local:3333`. Verified on the board: 200 Hz, byte-identical to USB, reconnects, timing 4.1 ms constant vs USB ([report](output/2026-11-05-0012-imu-wifi-link.md)). Wi-Fi password in the git-ignored `wifi_secrets.h`. 6-face accel calibration not yet run.
  - **Video pose** (MediaPipe): verified live on the MacBook webcam, camera 0. The camera only opens from the user's terminal, not from Claude's shell. Not yet recorded with the radar.
- **Pi set v0.2** (`deploy/pi/`, [report](output/2026-11-07-1535-semg-support.md)): live radar + MyoWare sEMG (envelope, median frequency) in the dashboard; Start/Stop records both into one folder on one clock. Verified from the PortableSSD install with replayed radar + `fake_myoware.py`, and with the real MyoWare over Wi-Fi (`check_bridge` passes; not worn yet). Not yet run on a real Pi or the live radar. Live model scores need radar-only rep detection.

## Recent changes
- 2026-11-09 - Reviewed clinical/public datasets for both AI reference work and presentation evidence. [Sources and use limits](output/2026-11-09-clinical-data-sources_v01.md); [machine-readable catalog](output/2026-11-09-clinical-data-sources_v01.json). CC BY samples (one real stroke MAT file, Minho fatigue labels/protocol) in ignored `model/data/external_reference_v01/`. None is paired radar input; current labels/model/slide content unchanged. No commit/push.
- 2026-11-08 - Radar points + heatmaps (contract v1), finer profile `fullmap_fine_awr2x44p.cfg` (3.88 cm, not yet on the board), 4th dashboard view "Points (height)". Radar stays on USB (Ethernet demo = bare points). [Report](output/2026-11-08-1704-points-and-finer-heatmap.md).
- 2026-11-07 - MyoWare: the Wi-Fi record sketch uploaded (Wi-Fi file copied from the IMU's, unopened); real board at 1000/s with 0 gaps over Wi-Fi; Pi bridge check passes. [Report](output/2026-11-07-1601-myoware-upload.md).
- 2026-11-07 - sEMG support end to end (the IMU is unreliable): MyoWare Wi-Fi firmware, bridge `emg` provider and one shared recording, sEMG-envelope reps, dashboard EN/TH/zh-HK, Pi set v0.2 on the PortableSSD.
  - Verified without the board: `check_bridge` 18/18, a radar + sEMG recording is USABLE with "fatigue ✓"; fixed a replay-loop frame-number bug on the way.
  - [Report](output/2026-11-07-1535-semg-support.md).
- 2026-11-05 - Raspberry Pi set v0.1 (`deploy/pi/`): live radar in the dashboard, Start/Stop recording in the recorder's format, installer, self-test.
  - Bundle `truerehab-pi-0.1.0-20261105-de84695.tar.gz` on the PortableSSD; installed and verified there with a replayed real recording (`check_bridge` 16/16).
  - Fixed on the way: bridge viewers couldn't connect (since Oct 12), SIGTERM shutdown, same-second sessions, empty recordings, the frames/s display.
  - [Report](output/2026-11-05-2119-pi-software-set.md).
- 2026-11-05 - Project-wide check: every runnable suite passes with 0 warnings; all 4 firmware builds compile.
  - Bug fixes pushed as 4 small commits: the training warning, radar-lab's open config file, recorder test leaks, and 7 bugs in `ml_Try-1.py`.
  - [Report](output/2026-11-05-2040-project-audit.md).
- 2026-11-05 - The model is shown in the dashboard (replay link, radar view buttons, translations); typecheck, i18n and report checks pass; verified in the browser.
  - Radar smoke test with the current settings: 60 fps, 0 missing; IMU 200/s over Wi-Fi.
  - The user chose to keep the radar settings (measure only). The person runs are still to do.
  - [Report](output/2026-11-05-1844-dashboard-replay-radar-check.md).
- 2026-11-07 - Latest presentation is `presentation/TrueRehab_RF_Structured_Visual_v04.pptx`: white slides with very faint blue/mint corner arcs, replacing the distracting navy backgrounds. All 15 slides retain their wording, notes, pictures, fonts and layout; user cover stays intact. [Report](output/2026-11-07-white-corner-theme_v01.md). Previous versions retained; no commit/push.
- 2026-11-07 - Latest deck: `presentation/TrueRehab_RF_Structured_Visual_v03.pptx`. Removed the prompt-generated illustration slide and restored the 15-slide sequence with blue/white/mint colors. User cover, images, wording, notes, fonts and layout preserved. [Report](output/2026-11-07-restore-deck-theme_v01.md). Prior versions and script retained; GigaFlex excluded; no commit/push.
- 2026-11-07 - Edited the user's newer 16-slide Downloads attachment: `presentation/TrueRehab_RF_Structured_Visual_v02.pptx` has a full-page text-free blue/white/mint background-problem illustration on slide 3. Other 15 slides preserved exactly. Asset/prompt in `presentation/assets/`. [Report](output/2026-11-07-background-illustration_v01.md). User wants GigaFlex left out of presentation changes for now. No commit/push.
- 2026-11-05 - User requested numbered deliverables after every creation/revision. Latest structured deck and script duplicated unchanged as `presentation/TrueRehab_RF_Structured_Visual_v01.pptx` and `TrueRehab_RF_Structured_Presentation_Script_v01.docx`; use `_v02` next. Standing convention saved in `CLAUDE/CLAUDE.md`. [Report](output/2026-11-05-numbered-deliverable-copies.md). No commit/push.
- 2026-11-05 - New user-structured deck and script: `presentation/TrueRehab_RF_Structured_Visual.pptx` (15 slides) and `TrueRehab_RF_Structured_Presentation_Script.docx` (884 words, 7-8 min plus demo). Intro, background/problems, developer flowcharts and showcase; school identity and licensed assessment photo verified. [Report](output/2026-11-05-structured-presentation-and-script.md). Earlier versions retained; no commit/push.
- 2026-11-05 - Backup stage version created: `presentation/TrueRehab_RF_Stage_Visual.pptx` (10 main + 2 hidden Q&A slides) and matching `TrueRehab_RF_Stage_Presentation_Script.docx` (661 spoken words, 5-6 min, delivery cues). Simple visual narrative, hardware substitution and evidence limits disclosed. [Report](output/2026-11-05-stage-presentation-and-script.md). Original poster speech retained; no commit/push.
- 2026-11-05 - Converted the original expanded poster speech to `presentation/TrueRehab_RF_Poster_Speaking_Script_Expanded.docx` at user request. All wording and the original three-page layout preserved and verified; `.doc` retained. This is a format-only change, no commit/push.
- 2026-11-05 - At user request, the latest evidence review is also available as [editable Word DOCX](output/2026-11-05-evidence-review-and-presentation-options.docx). All source wording retained; six-page layout and reference links verified. Markdown source retained; no commit/push.
- 2026-11-05 - Pulled `8e5b6db` and preserved local poster scripts/notes. [Evidence audit and presentation/project options](output/2026-11-05-evidence-review-and-presentation-options.md): proposal fatigue/risk numbers are illustrative; outside adherence/pain/visit figures are not product outcomes. Recommendations only, no UI/artifact/hardware implementation or push.
- 2026-11-05 - IMU Wi-Fi link (fw 2.1) verified on the board. The recorder reads `tcp://` (IPv4 lookup, reconnects with marker rows), and `align_device_time` now fits the lower edge: Wi-Fi vs USB timing changed from 37 ms wander to a constant 4.1 ms. [Report](output/2026-11-05-0012-imu-wifi-link.md).
- 2026-11-04 - IMU firmware rewritten and verified on the board (OLED on its own core: 200.00 Hz, no gaps; clone chip accepted; reconnects; calibrations). Merged teammate's record mode after fast-forwarding to `660e66d`; recorder now drops macOS port-open replays. [Report](output/2026-11-04-2232-imu-firmware-fix.md).
- 2026-11-04 - Poster speaking script saved as `presentation/TrueRehab_RF_Poster_Speaking_Script_Expanded.doc`: expanded at user request to 626 spoken English words, three pages, eight sections and pointing cues. Original short file remains because it was open and locked. Poster speech/demo is primary; slides remain backup. [Report](output/2026-11-04-poster-speaking-script.md). No commit/push.
- 2026-11-03 - User requested pull then push. Pulled MyoWare wireless sketch and `radar-lab/` commits through `cc97005`; reconciled context/decision conflicts while preserving both implementations and evidence. See [sync report](output/2026-11-03-repository-sync.md).
- 2026-11-03 - Browser Drive and fixed-board map approved and completed; parser, geometry, HTTP boundaries and live/shared controls verified in their reports. Existing Room map HTML preserved by the Drive task. No new firmware/Pi/main-dashboard changes for those tasks.
- 2026-11-02/03 - Official SBL/TDM flash and normal boot previously verified. Real 151-frame capture independently accepted by TI's parser. Windows tuning chose 40 Hz after extended 45-Hz gaps; 45/48-Hz profiles remain experimental, original 10-Hz full output is rollback.

## Open questions
- Freeze the input contract (v1: angle FFT + phase + point height/presence `[4,64,32]`, range-Doppler `[1,64,16]`)?
  - Open: frames per rep. T = 128 crops 58 % of the fake 2.0–2.9-s reps.
  - Open: whether the phase channel carries muscle signal.
  - The recording protocol is in `model/README.md`. The browser's fast point output is a different input.
- Label thresholds and recommendation numbers are placeholders: they need a physiotherapist.
- Can phase/micro-vibration output be exposed within schedule? Ethernet is not verified; changing firmware still requires approval.
- Validate radar-lab left/right and antenna ordering with the actual board (stop-on-close verified Nov 4). Investigate Windows long-run sequence gaps without hiding them.
- IMU on the body: solid wiring/strain relief and mounting position. Record default is ±4 g/±500 °/s at the 16384/131 count scale (values can pass int16); confirm or switch to `RECORD_WIDE_RANGE 0`. Wi-Fi pauses ~1 s now and then (Mac or router?); harmless for recordings, would delay a live display.
- sEMG numbers come from fake data: the live activity gate (9x rest), the rep rule (15x resting noise, 30 % swing) and the textbook stats. Check them after the first real MyoWare recording.
- Shoulder visibility/mounting, merging the two dashboards, team roles and healthy-volunteer ethics remain open. No patient trials yet.
- Repo instructions describe macOS/zsh, but Windows work also exists. Home copy/font license and the poster's "oral health" wording remain open; submitted sources stay unchanged.

## Next steps
0. **Radar points decision:** keep the point layers on for the model, or off until real sessions show a benefit (fake data: off is better).
0. **Finer profile on the board** (radar plugged in, power first): 60 fps, 0 missing, temperature, two metal objects ~5 cm apart; then switch `paths.RADAR_CFG`, the recorder and the bridge to it.
0. **MyoWare:** wear it on battery (switch ON, USB out, fresh pads on the biceps) and record curls with the radar over Wi-Fi; then `check_session.py`, `python -m trnet.calibrate`, and check the sEMG thresholds on the real signal.
0. **Pi set v0.2:** live-radar check (power first, then USB; installed bridge + `check_bridge`), then on the real Pi: flash the SD card, copy from the SSD, `bash install.sh`, then `selftest.py` (see `deploy/pi/README.md`).
1. **Fix the IMU wiring for the arm** (solder or a locking connector, cable taped down). On the arm it had 179 I²C errors and lost 36 of 72 s. Then redo the curls run with it.
   - Left/right test with a still metal object (tray or laptop lid) at radar height, ~1 m in front, then to the left, then to the right.
1. **First full test session:**
   - Hardware: radar (power first, then USB); MyoWare over Wi-Fi (battery only on a person); IMU over Wi-Fi from a power bank with wire strain relief, once its wiring is fixed; webcam pose started from the user's terminal.
   - Protocol from `model/README.md`: 5 s still, `s` + 3 shrugs, sets with space per rep.
   - Then run `model/check_session.py` and `python -m trnet.calibrate`. Run the IMU's 6-face accel calibration once.
   - After that: choose T, freeze contract v1, and train with `train.py --sessions` once there are ≥ 3 people.
1. Before switching demos, stop the current collector and release serial ports. Browser Start/Stop affects both pages; original Close viewer shuts their shared service. Never run radar-lab alongside it on the same board.
2. Browser safety stops: 15 min/session, 15 s without polling, valid temperature >=85 C, or reserve <5% for three frames. Start resumes a new session; do not reflash merely to reopen.
3. Validate radar-lab known-target angular orientation, then agree recording scope, preserve frame/config/timestamp/loss metadata, and freeze a real versioned `InputContract` before training or bridge integration.
4. Upstream follow-ups: Reps panel continues after session end; Python bridge `session_end` lacks `reps`. (`sandbox/ml_Try-1.py` fixed on 2026-11-05: it trains and runs to the end.)
5. Ask before Pi package setup; later run its tests and bridge checks. Reuse verified acquisition/parser components only after matching their actual output contract.
