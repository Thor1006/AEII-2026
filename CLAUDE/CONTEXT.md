# Context

<!-- Living state. Keep under ~40 lines; reports hold detailed run history. -->
**Last updated:** 2026-11-03 (repository sync)

## Current focus
**Plan B is selected and received: AWR2944PEVM, no DCA1000.** The submitted AWR1843BOOST/DCA1000 poster stays frozen. Two independent USB radar demos now coexist; their profiles, outputs and measured limits differ. Run only one serial collector at a time. No raw ADC or validated fatigue/body model is claimed.
- Windows browser viewer: `sandbox/radar-live-viewer/`, AWR2X44P TDM / SDK 04.07.02.01, COM5 115200 / COM6 3125000. Selected `tdm-wide-points-40hz.cfg`: 40-Hz target, nominal 3.88-cm radial separation, point/health output. [Measured limits and rollback](output/2026-11-03-radar-rate-resolution.md); extended runs had occasional sequence gaps. Last recorded server PID 36636 is historical, not a current health check.
- Browser Room map http://127.0.0.1:8766/ and separate Drive view http://127.0.0.1:8766/drive/ share that collector. [Room map](output/2026-11-03-fixed-radar-room-map.md): fixed-board, 30-s RAM window, 10-cm display cells, >=3-frame persistence. [Drive](output/2026-11-03-car-style-radar-demo.md): illustrative car and measured reflection groups; no vehicle/person/lane/path recognition.
- Teammate's `radar-lab/`: independent macOS 2D/3D viewer with static range-azimuth and range-Doppler heatmaps. Its different profile reportedly measured 60.0 radar fps, 601/601 frames; this is not a new benchmark of the Windows 40-Hz profile. [Report](output/2026-11-03-2214-radar-lab-fullmap-3d.md), `radar-lab/README.md`. Height comes only from sparse measured points; angular orientation and stop-on-close remain unverified on hardware there.
- Received: radar/power, MyoWare + Wireless Shield + 30 pads, Pi 5 8GB + cooler + 27-W PSU + 64-GB A2 microSD, Micro-HDMI, SSD and USB-C LAN adapter. UART is verified; Ethernet/custom phase, ground-truth synchronization, clinical inference and Pi deployment remain unverified.
- CNN encoder `sandbox/Encoder_0.1/` and existing AI/dashboard demonstrations still use synthetic input. `frontend/` has home/dashboard, kit key, EN/TH/zh-HK, help, session summaries and five-session history (upstream records these as committed). `Phisit/` is the teammate's separate FastAPI/React demo.
- **Paused by user:** do not install `pi-bridge/` packages (`websockets`, `numpy`) until actual Pi setup; ask then. The bridge has not run.

## Recent changes
- 2026-11-03 - User requested pull then push. Pulled MyoWare wireless sketch and `radar-lab/` commits through `cc97005`; reconciled context/decision conflicts while preserving both implementations and evidence. See [sync report](output/2026-11-03-repository-sync.md).
- 2026-11-03 - Browser Drive and fixed-board map approved and completed; parser, geometry, HTTP boundaries and live/shared controls verified in their reports. Existing Room map HTML preserved by the Drive task. No new firmware/Pi/main-dashboard changes for those tasks.
- 2026-11-02/03 - Official SBL/TDM flash and normal boot previously verified. Real 151-frame capture independently accepted by TI's parser. Windows tuning chose 40 Hz after extended 45-Hz gaps; 45/48-Hz profiles remain experimental, original 10-Hz full output is rollback.

## Open questions
- What representation/profile and labeled recording/synchronization protocol should feed the encoder and dashboard? Upstream heatmap candidate is 64 range bins x 64 angles plus 64 x 16 Doppler; browser fast output is points. These inputs are not interchangeable.
- Can phase/micro-vibration output be exposed within schedule? Ethernet is not verified; changing firmware still requires approval.
- Validate radar-lab left/right, antenna ordering and stop-on-close with the actual board. Investigate Windows long-run sequence gaps without hiding them.
- Shoulder visibility/mounting, merging the two dashboards, team roles and healthy-volunteer ethics remain open. No patient trials yet.
- Repo instructions describe macOS/zsh, but Windows work also exists. Home copy/font license and the poster's "oral health" wording remain open; submitted sources stay unchanged.

## Next steps
1. Before switching demos, stop the current collector and release serial ports. Browser Start/Stop affects both pages; original Close viewer shuts their shared service. Never run radar-lab alongside it on the same board.
2. Browser safety stops: 15 min/session, 15 s without polling, valid temperature >=85 C, or reserve <5% for three frames. Start resumes a new session; do not reflash merely to reopen.
3. Validate radar-lab stop-on-close and known-target angular orientation, then agree recording scope, preserve frame/config/timestamp/loss metadata, and freeze a real versioned `InputContract` before training or bridge integration.
4. Upstream follow-ups: Reps panel continues after session end; Python bridge `session_end` lacks `reps`; `sandbox/ml_Try-1.py` does not run. These are outside this sync.
5. Ask before Pi package setup; later run its tests and bridge checks. Reuse verified acquisition/parser components only after matching their actual output contract.
