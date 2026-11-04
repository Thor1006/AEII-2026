# Official AWR2944P TDM demo flash successful

Date: 2026-11-02 (Asia/Bangkok). Flash and readback verification are complete; normal QSPI boot, demo response, sensor data and GUI are still unverified. The approved bring-up plan remains in progress.

## Authorization and physical checks
- User explicitly approved the TI demo flash plan, supplied photos identifying AWR2944PEVM PROC194 REV. A and a second SOP-area photo, then confirmed power/reset readiness with "พร้อมแล้ว".
- Reviewed photo showed SOP2/SOP0 jumper positions for UART mode and SOP1 open. Dedicated 12-V power and XDS_USB were confirmed. Windows identifies TI XDS110 VID 0451 / PID BEF3 at COM5 and COM6.
- Passive COM5 read at 115200 baud returned `CCC` (three XMODEM CRC requests), confirming an actual ROM UART boot response before any transfer.

## Firmware and host tools
SDK 04.07.02.01; official, unmodified flash utility:
`C:/ti/mmwave_mcuplus_sdk_04_07_02_01/mcu_plus_sdk_awr2x44p_10_02_00_04/tools/boot/uart_uniflash.py`.

Working directory and isolated Python environment:
`C:/Users/chap_/.codex/.chatgpt-projects/g-p-69f1b1cfff0c81919aa91c82a1c098a6/tmp/radar-flash-2026-11-02`.
Interpreter `.venv/Scripts/python.exe`; task-local copies of the three vendor images and manifest. Exact SHA256 values are in the preparation report and `firmware-manifest.json`; the TDM app hash was rechecked immediately before writing.

## Verified results
Each vendor command used COM5, its own configuration, a complete captured log and explicit inspection of the previous stage before the next. All processes exited 0, and each log contains exactly one `[STATUS] SUCCESS !!!` with no `[ERROR]`, `[STATUS] ERROR` or traceback. Success is based on the actual device status, not exit code alone.

| Stage | Target | Operation | Result | Log in working directory |
| --- | --- | --- | --- | --- |
| 10 | `sbl_qspi.release.tiimage`, 0x0 | Send RAM flash writer, write QSPI SBL | SUCCESS | `flash-10-bootloader.log` |
| 20 | Same SBL, 0x0 | flashverify | SUCCESS | `flash-20-bootloader-verify.log` |
| 30 | `awr2x44P_mmw_demoTDM.appimage`, 0xA0000 | flash | SUCCESS | `flash-30-demo.log` |
| 40 | Same TDM app, 0xA0000 | flashverify | SUCCESS | `flash-40-demo-verify.log` |

The RAM writer is 67601 bytes; QSPI SBL is 67969 bytes; TDM app is 405932 bytes. Reported transfer durations: RAM writer 8.08 s, SBL write 9.57 s, SBL verify 8.81 s, app write 38.27 s, app verify 83.36 s. All four serial sessions closed normally. No mass erase, alternative firmware, HS/security image or provisioning was attempted.

## Current physical state and next actions
The board was last used in UART flashing mode. User has been informed that verification passed and power/USB may now be removed.
1. Remove BOTH 12-V and USB before changing jumpers. QSPI functional mode is J17 SOP2 open, J18 SOP1 open, J20 SOP0 closed. Ask for a confirming photo before reconnecting power; do not move unrelated jumpers.
2. Restore stable power and XDS_USB, press SW1 NRST, re-enumerate COM mapping and read a demo/version response at 115200 baud.
3. Only after version confirmation, use a matching official AWR2944P TDM profile, read actual auxiliary binary packets (SDK expects 3125000 baud) and verify a live visualizer plot.
4. Do not claim the original end-to-end demo request is complete before normal boot, sensor output and GUI evidence. Do not reflash automatically if a host GUI or boot-mode issue remains.

No Git commit/push, source poster/proposal edits, system Python/SDK modifications, Pi bridge dependency installs or network/firewall changes. Existing unrelated worktree changes preserved.
