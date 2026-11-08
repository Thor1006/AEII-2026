# Plan: radar (AWR2944PEVM) data over LAN

**Status:** proposed: a choice is needed first (see "Options")
**Date:** 2026-11-08

## Why
The user (2026-11-08): "right now I want the AWM [AWR] sensor to send data via LAN". The sEMG worn test is postponed.

## What we found (2026-11-08)
- **Now:** the radar runs TI's `awr2x44P_mmw_demoTDM.appimage` (SDK 04.07.02.01, flashed Nov 2 from the Windows PC,
  `C:/ti/mmwave_mcuplus_sdk_04_07_02_01`). It sends over **USB UART** (3.125 Mbaud, 60 fps):
  - the static azimuth heatmap (complex), the range-Doppler heatmap, points, stats, temperature and frame numbers;
  - our whole chain is built on those heatmaps (`model/` input contract v0-draft, the Pi bridge's radar provider,
    radar-lab and the recordings).
- **LAN needs other firmware.** The transport is fixed when TI builds the app; no command switches UART to Ethernet.
  - **Known to work on an AWR2944PEVM** (a community driver, checked on a real board):
    `ti/demo/awr2x44P/mmw_ddm/awr2x44P_mmw_demoDDMEnet.appimage` (SDK 4.7.2.1). It's the **DDM** demo, a different
    radar mode from our TDM demo.
  - **What it sends over LAN:** per frame only `uint32 count, uint16 0, count × (x, y, z, speed) float32`. No magic
    word, no frame number, no timestamp, no SNR, no heatmaps. 10 Hz in the community example.
  - **Network:** the radar is fixed at `192.168.1.200` and connects as a TCP client to the PC, port 7 (fixed). The PC
    is a TCP server; its address is set with the `enetStreamCfg 1 a b c d` CLI command.
  - **Cables:** USB (J8) stays connected for the commands; the data goes over **J9 Ethernet** to a network adapter
    used only for the radar (our USB-C LAN adapter, or the Pi's Ethernet port).
  - **Sessions:** the radar never reconnects: reset the board before each LAN session.
- TI also lists a **TDM Enet** demo that streams **1D-FFT (complex range-FFT) data** over Ethernet (seen for the
  non-P AWR2944: `awr2944_mmw_demoTDMEnet.appimage`, `profile_Enet.cfg`; TI's capture tool is Linux-only). Whether an
  AWR2x44P version is in our SDK 04.07.02.01 is **unknown**: the SDK folder on the Windows PC has to be checked.
- **Address clash:** the home Wi-Fi is also `192.168.1.x` (this Mac .83, the MyoWare .89). With the radar fixed at
  .200, the radar adapter needs an unused address in that range (e.g. `.250`), no router, and a route to .200 through
  the adapter. That's a system network setting: the user makes it (macOS: System Settings → Network). At school the
  phone hotspot uses another range, so no clash there.

## Options
- **A. Keep USB (no change).** Everything works today, including on the Pi (radar on its USB). LAN isn't needed for
  the Pi set.
- **B. DDM_ENET (points over LAN).** Proven on this board model, but the model gets less: no heatmaps, no phase, no
  frame numbers. The model's input, the bridge's radar provider and the recordings would have to change to point
  clouds. Rollback = re-flash the TDM demo the same way.
- **C. First check for a TDM Enet (1D-FFT over LAN) image for AWR2x44P.** If it exists, this is the one that gives the
  AI *more* data (complex range-FFT, the phase the proposal wants for muscle micro-motion). It's more work: a new
  receiver, a new contract. **Recommended next step:** the user copies the SDK's `ti/demo/awr2x44P/` folder (and
  `docs/`) from the Windows PC to the PortableSSD, and I read what's there before anything is flashed.

## Steps once an option is chosen (B or C)
1. **Firmware:** the user's explicit OK to flash.
   - **Board jumpers:** power off, set UART flash mode (J20 on, J18 off, J17 on; S1 at XDS).
   - **Flash:** with the SDK's `uart_uniflash.py`, write `sbl_qspi` at 0x0 and the Enet app at 0xA0000, and verify,
     as on Nov 2.
   - **Back to run mode:** J17 off, then reset.
2. **Network:** the user sets the radar adapter to a static `192.168.1.250/24` with no router; then
   `ping 192.168.1.200` after the radar starts.
3. **Receiver:** a small Python TCP server (port 7) that checks the frame format and logs points/s and gaps; then
   check it live.
4. **Integration** (separate plan): a bridge provider, the recording format, and the model input.

## Risks / limits
- A flash replaces the working TDM demo. Rollback needs the Windows PC (or the SDK files copied to the Mac).
- DDM_ENET sends no frame numbers or timestamps, so data loss can't be detected from the stream itself.
- Port 7 is a privileged port on Linux (the Pi needs a capability or a sysctl); macOS allows it.
- Never flash the AWR1843BOOST/DCA1000 (not in use); the radar config is changed only with the user's OK.
