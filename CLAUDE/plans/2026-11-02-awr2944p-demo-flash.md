# Plan: AWR2944PEVM official demo firmware bring up

**Status:** done
**Date:** 2026-11-02

## Why
The user-approved matching SBL/TDM images were flashed and verified; QSPI boot reports AWR2X44P/TDM/04.07.02.01. The unchanged TI profile produced 151 consecutive real frames in 15 seconds, independently validated by TI's parser. TI's official GUI remained unavailable. The user then explicitly approved a separate local diagnostic graph as the substitute host display; that graph is now visibly live and verified. This completes the firmware/data/live-plot bring-up through the user-approved alternative, not through TI's own GUI. Clinical AI, Ethernet and custom raw/complex outputs remain out of scope.

## Progress
- Preparation, user approval, physical UART-mode gate: complete.
- Bootloader flash at 0x0 and flashverify: SUCCESS.
- AWR2x44P TDM demo flash at 0xA0000 and flashverify: SUCCESS.
- Four vendor logs audited: one SUCCESS each, no ERROR or traceback.
- Normal QSPI boot/version, standard TDM configuration and real output: SUCCESS; 151/151 consecutive frames parsed by TI's own parser with no frame errors/gaps in this bounded capture.
- Sensor stopped after the bounded smoke test; later restarted through the user-approved local graph. The custom host display is verified live; TI's own GUI remains unavailable/unverified.
- [Approved substitute viewer plan](2026-11-02-local-live-radar-viewer.md) completed with Start/Stop/shutdown/restart checks and a real advancing graph. No additional flash writes were made.
- Latest evidence: `CLAUDE/output/2026-11-02-awr2944p-real-data-smoke-test.md`.
- See `CLAUDE/output/2026-11-02-awr2944p-flash-success-awaiting-qspi.md`.

## Approach
1. Confirm the board marking and SOP jumper positions from a photo. Verify dedicated 12-V power and USB connected to XDS110. Do not infer the board's boot mode from COM enumeration.
2. Obtain approval of this plan before any flash write. Ask the user to power down before adjusting jumpers and set UART flashing mode using the board guide: J17 SOP2 closed, J18 SOP1 open, J20 SOP0 closed. Restore power/reset only after the physical setup is confirmed.
3. Prepare an isolated host Python environment with the TI flash tool dependencies pyserial, tqdm and xmodem. Do not install paused Pi bridge dependencies or modify TI's installed files.
4. Use the official AWR2x44P UART flash utility, flash writer and QSPI secondary bootloader from the installed SDK. Create a separate configuration pointing to the matching AWR2x44P TDM demo appimage, not the default CCS debug image, AWR294x non-P images, ECO/LC variants, or HS images without verifying device security requirements.
5. Write only the documented bootloader and application regions, preserving the vendor scripts. Require successful flash verification; stop on unexpected errors instead of trying alternate images or mass erasing flash.
6. Ask the user to power down, restore QSPI functional mode (SOP2 open, SOP1 open, SOP0 closed), then restart. Read the demo banner/version before sending a compatible standard radar profile.
7. Launch the matching TI visualizer and verify real sensor packets and a live plot. Report separately firmware success, UART data success and GUI success; do not describe processed point clouds as raw ADC.

## Files touched
- This plan and a subsequent report/context update in CLAUDE.
- Task-local flash configuration, dependency environment and logs; no source poster, proposal, SDK source or existing project application files are to be changed.
- Device QSPI bootloader and application regions only after approval and physical mode confirmation.

## Risks / needs OK
- Flashing replaces existing contents in the specified regions; interruption or a wrong device image can prevent normal boot until reflashed.
- User must keep power and USB stable while writing and perform physical jumper changes only with power removed.
- Exact board revision, boot state and security variant must be checked before writing. Do not promise that SDK installation alone means factory firmware is runnable.
- No changes to network, firewall, browser security, project Git commits or remote pushes.

## How we will verify
- Identify TI XDS110 COM interfaces and verify the selected CLI port.
- Record exact vendor file paths and hashes, check configuration offsets against TI's guide, and retain the complete flash/verification log.
- After functional-mode restart, obtain a readable demo/version response and real binary sensor data.
- Confirm a live TI visualizer plot, or report the exact remaining host/GUI blocker without claiming end-to-end success.
