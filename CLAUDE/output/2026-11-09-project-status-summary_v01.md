# TrueRehab-RF — status summary and missing work (2026-11-09)

Built from the repo, `CONTEXT.md`, `DECISIONS.md` and git history. Status words: **Done** (verified), **Partly** (works, gaps remain), **Not started**.
Owners are a guess from git commits (Thor1006 = Tor: pi-bridge, model, deploy, most of frontend; KINKIN-007 = KinKin: radar viewer, IMU, Phisit demo, frontend). **Please confirm or correct.**

## 1. Hardware

| Topic | Status | Done | Missing |
|---|---|---|---|
| Radar AWR2944PEVM (Plan B) | Partly | Received; flash + boot verified; UART live; real frames accepted by TI parser. Windows viewer 40 Hz; radar-lab 60 fps, 0 missing | Finer 3.88-cm profile not yet tried on the board; Ethernet and phase/micro-vibration unverified; left/right orientation unverified; occasional sequence gaps on long Windows runs |
| MyoWare 2.0 sEMG | Partly | Wi-Fi firmware uploaded; 1000 samples/s, 0 gaps; Pi bridge check passes | Never worn on a person; sEMG thresholds are from fake data; check with first real recording |
| IMU (MPU-6050 board) | Partly | Firmware rewritten; 200 Hz over Wi-Fi, matches USB; reconnects | Wiring fails on the arm (179 I²C errors, lost 36 of 72 s); 6-face calibration not run; range setting to confirm; Wi-Fi pauses ~1 s |
| Webcam pose (MediaPipe) | Partly | Works live on the MacBook | Not yet recorded together with the radar; only opens from the user's own terminal |
| Raspberry Pi 5 (required) | Partly | Pi 5 8GB, cooler, PSU, 64-GB SD, SSD, cables all received | SD card not flashed; nothing run on a real Pi yet |
| Purchases | Done | All listed hardware received | Optional accessories only |

## 2. Software

| Topic | Status | Done | Missing |
|---|---|---|---|
| Windows radar viewer, Room map, Drive demo (`sandbox/radar-live-viewer`) | Done (demo) | Live 3D points, 30-s room map, car-style view | Reflection-only: no person/vehicle recognition (by design) |
| radar-lab (Mac viewer, heatmaps) | Partly | 2D/3D heatmaps, stop-on-close verified | Known-target angle test |
| Recorder (`recorder/`) | Done | Radar/IMU/sEMG/pose recording, Wi-Fi input, clock alignment | First full multi-sensor session not recorded |
| Pi bridge + Pi set v0.2 (`pi-bridge/`, `deploy/pi/`) | Partly | Radar and sEMG providers, one shared recording, installer, self-test; passes with replay and real MyoWare | Not run on a real Pi or on the live radar; `session_end` lacks reps; packages on Pi need your OK first |
| Dashboard (`frontend/`) | Partly | Home/dashboard, EN/TH/zh-HK, 4 radar views, replay links, session history | Live mode waits for the Pi; Reps panel continues after session end; not merged with Phisit demo |
| AI model (`model/`) | Partly (untrained) | Network, data pipeline, fake data, 73 tests, session check | No real session with a person; input contract v1 not frozen (frames per rep, whether phase carries signal, points on/off); label thresholds are placeholders; needs ≥ 3 people to train |
| Phisit demo / `Encoder_0.1` | Done (separate demos) | Run on synthetic input | Not connected to real radar data |

## 3. Presentation

| Item | Status | Notes |
|---|---|---|
| Poster speech | Done | Short + expanded, `.doc` / `.docx` / `.pdf` |
| Stage deck + script (10 slides + 2 hidden Q&A) | Done | Backup version |
| Structured deck, latest `_v04.pptx` (15 slides, white theme) | Done | Matches your 4-part structure |
| Structured script `_v01.docx` | Partly | Written for the earlier deck; **not re-checked against v02–v04**. Deck was edited by you and by me since |
| Missing | | Deck and script don't mention the newer work (Pi set, sEMG, model, 4 radar views); rehearsal and timing (7–8 min target); demo run-through; Q&A prep from the evidence review; GigaFlex is deliberately left out |

## 4. Brochure

**Not started — no brochure file found in the repo** (searched names: brochure, flyer, leaflet). If it exists elsewhere (Canva, Downloads), tell me where. Needed: format/size, audience, language(s), content outline, branding/logo, print deadline.

## 5. Other small items

- **Claims:** proposal fatigue/risk numbers are illustrative; outside adherence/pain/visit figures are not product results (evidence review). Keep out of the brochure unless worded as background.
- **Placeholders:** label thresholds and recommendation numbers need a physiotherapist.
- **Ethics:** healthy-volunteer consent/approval still open; no patient trials.
- **Poster wording/licence:** "oral health" wording and home-copy/font licence open (submitted poster stays unchanged).
- **Team roles:** not written down anywhere.
- **Git:** `CLAUDE/CLAUDE.md`, `presentation/` and 8 report files are uncommitted/unpushed. Remote branches not reviewed: `wifi-pause-fixes`, `claude/codebase-audit-diagram-786f9c`.

## Suggested order (next 1–2 weeks)

1. **First full test session** (radar + MyoWare worn + IMU or webcam), then `check_session.py`. Everything else in model/ depends on this.
2. **Pi:** flash SD, install, self-test, live radar on Pi.
3. **Fix IMU wiring** (or drop the IMU and use sEMG + webcam).
4. **Presentation:** update deck and script with newer work; rehearse with timing.
5. **Brochure:** decide format and start.
6. Freeze input contract v1; commit and push the leftover files.
