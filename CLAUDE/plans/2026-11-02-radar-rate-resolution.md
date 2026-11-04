# Plan: Measure and improve live radar frame rate and range resolution

**Status:** done
**Date:** 2026-11-02

**Approval:** After asking why the completed 3D view still received 10 Hz and being told rate/resolution tuning remained pending, the user instructed "apply all those changes please" on 2026-11-02. This authorizes this staged runtime profile/display optimization, including its bounded experiments and rollback, without firmware flashing.

## Result
Completed through staged real baseline/wide-band tests and local browser verification. Final selection is 40-Hz point/health-only output with nominal 3.8839-cm radial range separation and 0.1190-m/s Doppler separation; unused range-profile telemetry is disabled in this viewer profile only. The 45-Hz candidate passed a bounded 60-second test but later showed one live sequence discontinuity (9354 to 9356), so it was not retained as the default. 48 Hz was rejected below 10% reserve. Actual measured-frame queue delivery removes the former ~4/s browser cap without interpolation. Final server PID 42784 uses `tdm-wide-points-40hz.cfg` at the same URL; no reflash, commit or push. See [full evidence, limits, stop/buffer fixes and rollback](../output/2026-11-03-radar-rate-resolution.md).

## Why
The user requests frame rate and precision just below the theoretical limit. There is no single joint maximum: frame period, sampled bandwidth, coherent acquisition time, processing, UART output and browser updates impose different limits. Interpret precision initially as range resolution, while preserving velocity resolution where possible; do not claim improved absolute accuracy without calibration evidence.

## Read-only findings
- Current official profile: 100-ms frame period = 10 measurement frames/s; the page polls every 250 ms, so visible updates are at most about 4/s. Prior statements describing the graph itself as 10-Hz should be read as receiver rate, not display rate.
- 64 chirps with (186 + 57.14) microseconds each take 15.56096 ms. A 64.26-Hz chirp-only ceiling excludes processing and transport.
- Existing 151-frame capture, excluding the first two timing reports: processing 1723–1777 us; previous-frame UART transmission 3966–4375 us; processing margin 82621–82674 us. The SDK explicitly excludes UART time from the reported processing margin. Combining maxima gives a rough 21.713-ms budget, about 46 Hz before extra headroom, and is NOT a validated maximum under dense/moving scenes.
- Sampled bandwidth = 70 MHz/us * 656 / 13.349 MHz = approximately 3.440 GHz; nominal range separation c/(2B) = 4.36 cm. This differs from FFT bin spacing and absolute accuracy. Current sweep already ends near 81 GHz.
- TI specifies 76–81 GHz coverage and 5-GHz available bandwidth: ideal full-band separation is about 3 cm, not a promise that this demo/profile can achieve it without settling/guard constraints. Source: https://www.ti.com/product/AWR2944P
- Current read-only health check: sensor stopped, 5866 frames received, zero invalid packets/gaps. No settings or firmware changed in this audit.

## Approach
1. Preserve the exact working TI profile and viewer as rollback; use named experimental profiles. Keep existing firmware, power/boot settings and 4-TX/4-RX antenna configuration.
2. Decode SDK timing statistics with correct previous-frame semantics and expose actual receiver FPS, display FPS, packet gaps, data age and available temperature telemetry. Do not treat CPU-load zeros as proof of unlimited processing headroom.
3. Improve local display polling/serial latency with bounded non-overlapping requests and no fake/interpolated measurement frames. Keep authentication, loopback binding, stop controls and watchdogs.
4. Increase frame rate alone in bounded stages, initially 20, 30 and 40 Hz, preserving the existing chirps and velocity/range resolution. Select the fastest tested rate with at least 10% timing headroom including UART, no observed losses/assertions and acceptable temperatures; lower it for denser output. Do not assume 60 Hz is feasible.
5. Separately investigate a wider sampled-bandwidth profile within TI RF, IF, ADC, timing and memory constraints, with margin below band edges. Only test validated parameters; retain the original if unsupported. Re-evaluate frame-rate/velocity tradeoffs for this profile and present achieved values. Increasing ADC rate, FFT padding or decimal places alone does not improve physical resolution. Leave angle resolution claims unchanged. Bias/phase calibration requires a suitable known target and is not silently performed.
6. Return the selected validated configuration to the local viewer, show the live graph, and document measured limits/tradeoffs. Roll back if the new configuration fails. Keep the original dashboard, Pi packages and submitted poster untouched; no commit or push.

## Files touched
- `sandbox/radar-live-viewer/server.py`, `index.html`, focused tests and README — telemetry, display responsiveness and explicit profile metadata.
- `sandbox/radar-live-viewer/profiles/` — baseline copy and independently validated experimental configurations.
- Task-local runtime — bounded capture/benchmark outputs and logs.
- `CLAUDE/output/`, `CONTEXT.md`, `DECISIONS.md`, this plan — results and selected operating point.

## Risks / needs OK
- Repository instruction requires a proposed plan and OK before non-trivial/risky work. User approval has now been received. This remains an experiment, not a guarantee of simultaneous maximum FPS and range/velocity/angle accuracy.
- Higher duty cycle increases heat; point density changes processing and UART demand. Monitor available telemetry, bounded sessions and measured timing margins. Stop on stale output, growing losses, CLI errors or timing faults, and restore baseline when possible. If the device becomes unresponsive, report that physical reset is needed.
- No firmware flash, hardware modification, external transfer, driver change or new Pi installation is included.

## How we'll verify
- Parser tests for real statistics/layout and malformed TLVs, existing captured-frame regression, existing local HTTP security tests.
- Real captures at each candidate configuration, recording configured/received FPS, frame sequence, timestamps, packet sizes, processing/UART maxima, margins and available temperatures. Include movement/dense scenes where physically available; document scene limits instead of claiming all-scene guarantees.
- Browser observation of actual fresh frames and measured display updates, Stop releasing ports, and baseline restart/rollback. Report measured operating point separately from formula-only ceilings.
