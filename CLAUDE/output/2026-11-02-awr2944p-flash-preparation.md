# AWR2944PEVM official demo flash preparation

Date: 2026-11-02 (Asia/Bangkok). Status: PREPARED, NOT FLASHED; awaiting the user's UART boot-mode photo and confirmation. The approved plan remains in progress, not done.

## Evidence and scope
- User reports all hardware received, installed SDK, dedicated power and no previous firmware flashing.
- User explicitly approved `2026-11-02-awr2944p-demo-flash.md` and supplied two board photos. Silkscreen: AWR2944PEVM / PROC194 / REV. A; separate 12-V power and XDS_USB connected. The existing jumper state has not been approved as UART flashing mode.
- Windows PnP identifies TI XDS110 (VID 0451, PID BEF3) at COM5 (interface 00) and COM6 (interface 03). Other COM ports are Bluetooth. COM5 opened but returned no text to a read-only `version` command at 115200 baud in initial diagnosis. No measurement profile was sent.
- Host Chrome contains TI's SDK page. Prior GUI attempts did not launch/verify the visualizer; concurrent user input was detected and browser automation was paused. No host driver, extension, TI Cloud Agent or firewall changes made.

## Prepared isolated tools
Task directory: `C:/Users/chap_/.codex/.chatgpt-projects/g-p-69f1b1cfff0c81919aa91c82a1c098a6/tmp/radar-flash-2026-11-02`.

Python: task directory `/.venv/Scripts/python.exe`; packages pyserial 3.5, tqdm 4.67.1, xmodem 0.4.7, colorama 0.4.6. `pip check` passes. The first sandbox network attempt was denied; the approved escalated package installation succeeded. System Python, installed SDK files and Pi bridge packages were not changed.

Official flash utility (unmodified): `C:/ti/mmwave_mcuplus_sdk_04_07_02_01/mcu_plus_sdk_awr2x44p_10_02_00_04/tools/boot/uart_uniflash.py`.

Copied vendor images in task directory, verified against the recorded hashes:
- RAM flash writer `sbl_uart_uniflash.release.tiimage`: 67601 bytes; SHA256 `FBF05D00733A766904B6D7A72F43C41AC2E92F55DA360245C7D1B7DDD94DD889`.
- QSPI SBL `sbl_qspi.release.tiimage`: 67969 bytes; SHA256 `CC27FC61C16301653D51ECF90AE43CFF7A36BEFE15A3CCB6349D6A2305E56288`; flash offset `0x0`.
- TDM demo `awr2x44P_mmw_demoTDM.appimage`: 405932 bytes; SHA256 `F28437EEE015CA19F3965D19A7BE199AA4A6834A211FEC3904E03C6C20C84901`; offset `0xA0000`.

Source images are SDK `mmwave_mcuplus_sdk_04_07_02_01/tools/awr2x44P/` and `ti/demo/awr2x44P/mmw_tdm/`. Copies avoid vendor-tool temporary writes next to the installed source images.

## Validated configurations, not executed
- `10-bootloader-flash.cfg`: RAM writer, then SBL write.
- `20-bootloader-verify.cfg`: SBL readback verification.
- `30-demo-flash.cfg`: official P-variant TDM demo write.
- `40-demo-verify.cfg`: demo readback verification.
- All four pass the vendor `FileCfg.parse()` with status 0; all three copied binaries match SHA256 values. Validation imported the tool without calling main or opening a serial port.
- Run configurations separately with working directory set to the task directory and inspect returned TI status before the next stage. The vendor config loop does not itself guarantee abort on every returned flash status. Do not run all steps unattended or interpret exit code alone as successful verification.

## Physical gate and next actions
1. User must remove BOTH 12-V and USB power before jumper changes. UART mode: J17 SOP2 closed, J18 SOP1 open, J20 SOP0 closed. Request a close-up photo before reconnecting power. Do not confuse SOP jumpers with VPP 1P7/J1 or other power headers.
2. After the photo is confirmed, ask user to restore stable power/USB and reset for UART boot, re-enumerate COM mapping and verify bootloader communication before image transfer. Keep power/USB connected throughout writes and verification.
3. Execute each TI stage with a full log. Stop on errors, unexpected responses or interrupted power; no mass erase, alternate images, security provisioning or custom firmware.
4. After both regions verify, ask user to remove power and restore QSPI functional boot (J17 SOP2 open, J18 SOP1 open, J20 SOP0 closed), then restart.
5. Verify demo/version banner first, then matched AWR2944P TDM profile and data stream. SDK guide uses CFG 115200 and current demo auxiliary data 3125000 baud, but verify the flashed version before applying a profile. GUI success remains separate from firmware and serial success. OOB processed outputs are not DCA-equivalent raw ADC.

References: installed SDK guide sections 3.4, 4.1, 4.2.4; TI AWR2944/AWR2944P EVM guide Rev. C section 2.10.2, https://www.ti.com/lit/pdf/spruj22.

No flash log exists yet because no firmware writes have been attempted. No Git commit/push; source poster/proposal unchanged.
