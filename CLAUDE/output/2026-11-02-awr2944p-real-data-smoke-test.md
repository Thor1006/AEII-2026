# Real AWR2944P TDM UART smoke test passed

Date: 2026-11-02 (Asia/Bangkok). Hardware boot, configuration and real output verified. Sensor is stopped after the bounded test; no continuously running GUI is claimed.

## Boot evidence
After the user reported the functional-mode jumper change complete, the first combined newline/version query returned only prompts. A separate `version` command terminated with carriage return produced the complete response:
- Platform AWR2X44P; ProcChain TDM; mmWave SDK 04.07.02.01.
- RF FW 02.05.04.00.23.05.16; RF patch 02.06.03.01.25.05.22; mmWaveLink 02.04.06.17.
- Real CLI prompt `mmwDemo:/>`, no reflash required.

## Acquisition procedure
- Isolated host Python and vendor flash/capture directory: `C:/Users/chap_/.codex/.chatgpt-projects/g-p-69f1b1cfff0c81919aa91c82a1c098a6/tmp/radar-flash-2026-11-02`.
- CLI COM5, 115200 baud; auxiliary data COM6, 3125000 baud. DTR/RTS disabled. USB device TI VID 0451/PID BEF3, serial RA29P055.
- Unchanged official SDK profile `ti/demo/awr2x44P/mmw_tdm/profiles/awr2944P/profile_3d_3Azim_1ElevTx_awr2944P.cfg` copied to `official-awr2944p-tdm.cfg` in the task folder. This sends runtime configuration only; no additional persistent calibration or flash operation was requested.
- Task-local helper `radar_smoke_test.py` checks the returned platform/version/chain, sends one command at a time, waits for prompts and errors, reads the auxiliary port concurrently, captures for 15 seconds, parses complete packets and stops/cleans up in finally.
- Every official profile command returned Done, including sensorStart (init calibration status 0xffe). SensorStop returned Done at test completion; cleanup stop returned already stopped.

## Measured results
- Duration: 15.0 seconds; binary bytes received: 196192.
- Complete frames: 151, numbered 1 through 151; zero observed frame gaps; zero invalid frames; zero capture exceptions; no discarded prefix bytes.
- Header platform: 0x2944; SDK version: 0x04070201; subframe 0.
- Detected points per frame: minimum 3, maximum 8. Sample near points and more distant reflections occur at physically plausible coordinates, but no target identity or rehab metric is inferred.
- TLVs seen: 1 detected points (float x/y/z/velocity), 7 side info, 2 range profile, 6 statistics, 9 temperature/statistics payload. No raw ADC, complex radar cube or Range-Doppler heatmap was requested/proven.
- Nominal configured period is 100 ms. Frame count over the 15-second capture includes a startup/boundary frame; do not claim an exact long-run 10.0667-Hz hardware rate from this short test.

## Independent vendor-parser verification
Ran the unmodified SDK `ti/demo/parser_scripts/mmw_demo_example_script.py` against the captured `.dat`, with output files kept in the task folder. Exit code 0. End of log: `totalBytesParsed: 196192`, `numFramesParsed: 151`; no `Frame Fail` or `ERROR` messages. This independently validates the task helper's packet-count result using TI's supplied parser.

## Artifacts in the task folder
- `radar-smoke-capture.dat`: real processed UART binary capture.
- `radar-smoke-summary.json`: complete packet metadata, measured metrics and sampled coordinates.
- `radar-smoke-cli.json`, `radar-smoke-test.log`: command/response evidence.
- `ti-official-parser-validation.log`, `mmw_demo_output.csv`: independent vendor parser output.
- `radar_smoke_test.py`, `official-awr2944p-tdm.cfg`: reproducible bounded test; uses the isolated `.venv/Scripts/python.exe`.

## GUI boundary
The official link exposed on TI's SDK page and in the installed guide is `https://dev.ti.com/gallery/view/mmwave/mmWave_Demo_Visualizer/ver/4.7.0/`. Opening that exact URL in the in-app browser redirected to `https://www.ti.com/errorpage.html`, displaying "This part of the TI website is not currently available." No broader outage diagnosis is implied; this only describes the observed navigation. No GUI plot was verified. User-owned Chrome and Edge tabs were not modified, no browser extension/driver/agent was installed, and no security/firewall setting was changed.

## Next step
Resolve the official visualizer page/host requirements or obtain agreement for a separate local live viewer. Do not repeat firmware flashing for a website/host issue. Repeat UART test if needed; firmware/profile are now evidenced. Project dashboard/AI/ground-truth integration, Ethernet, Pi and clinical/fatigue claims remain separate, unverified tasks. No commit or push.
