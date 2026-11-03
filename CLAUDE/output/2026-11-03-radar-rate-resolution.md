# Validated faster 3D radar view

User approved the existing rate/resolution plan with "apply all those changes please" after the completed 3D view and explanation of its original 10-Hz rate. Work began 2026-11-02 and continued across local midnight. All changes are local; no firmware flash, SDK edit, main dashboard/Pi installation, source poster edit, commit or push.

## Selected operating point
- **Final selection:** `sandbox/radar-live-viewer/profiles/tdm-wide-points-40hz.cfg`: 40-Hz target (25-ms period), 4 TX / 4 RX, 64 chirps/frame. Same antenna geometry, detection thresholds and 186-us idle / 7-us ADC start. The initially selected 45-Hz candidate was superseded after extended GUI validation showed an intermittent discontinuity.
- Full sweep 76.55 to 80.9698 GHz; 70 MHz/us slope; ramp 63.14 us; 736 real samples at 13.349 Msps. ADC capture lasts 55.135 us and ends about 0.965 us before ramp end. This remains inside the existing upper VCO2 sub-band with about 30/50-MHz RF edge guards.
- Sampled bandwidth 3.8595 GHz gives nominal radial range separation 3.8839 cm, versus 4.3575 cm originally (about 10.9% smaller separation). Nominal Doppler separation changes from 0.12161 to 0.11904 m/s. This is waveform-derived separation, not experimentally calibrated accuracy or improved angular/body-position precision.
- Point positions, SNR/noise, timing statistics and valid temperature reports remain. The unused range-profile TLV is disabled only for this viewer profile, reducing UART overhead. Full-telemetry profiles and the exact original waveform/output remain available as rollback/comparison.

## Verification
Final selected 40-Hz GUI run: recorded health at 118.6 seconds / 4748 consecutive received frames, 40.1-Hz receive throughput, zero gaps/invalid packets, maximum valid temperature 56 C and minimum remaining time 6250 us (25.0% of the 25-ms frame). The browser subsequently showed approximately 40.1 unique measured-frame updates/s; the final screenshot is frame 5164, still zero gaps/invalid packets. This is evidence for the tested window and scene, not an unlimited-duration guarantee. Final post-change 17 tests, original 151-frame regression, JavaScript syntax and HTTP rejection checks passed.

Final preview: `C:\Users\chap_\.codex\.chatgpt-projects\g-p-69f1b1cfff0c81919aa91c82a1c098a6\tmp\radar-flash-2026-11-02\live-radar-3d-40hz-stable.png`. Recorded final health is `live-40hz-final-health.json` in the same runtime folder. Earlier 45-Hz screenshots/logs are historical, not the selected default.

All baseline 20/30/40-Hz profiles passed 12-second real tests with no invalid packets or frame sequence gaps. Wide full-telemetry 20/30/40-Hz profiles also produced clean real sequences. Full-telemetry 40 Hz passed a 60-second test: 2408 received packets, zero gaps/invalid packets, minimum transport-inclusive reserve 2864 us (11.46%), maximum sensor temperature 56 C. A later GUI trial dipped to 9.9% reserve; omitting unused telemetry provided more margin.

Point/health-only candidates:

| Target | Test | Packets received | Gaps / invalid | Minimum reserve | Result |
|---|---|---:|---|---:|---|
| 40 Hz | 12 s | 488 | 0 / 0 | 6115 us (24.46%) | Passed |
| 45 Hz | 12 s | 549 | 0 / 0 | 2989 us (13.45%) | Passed |
| 48 Hz | bounded test | 10 before stop | 0 / 0 | 2077 us (9.97%) | Rejected by 10% reserve guard; confirmed stop |
| 45 Hz | 60 s | 2709 | 0 / 0 | 2371 us (10.67%) | Passed, confirmed stop |

The 60-second 45-Hz run measured 45.2-Hz receive throughput, maximum processing 2766 us, UART transmission 1302 us, maximum valid sensor temperature 49 C. Counts include startup/stop-boundary packets; snapshot samples are fewer than decoded frames because USB may deliver multiple frames in a burst. JSON benchmark files are sampled real states and aggregate counters, not a full ADC recording.

An earlier UI trial showed one sequence discontinuity near the end/Stop operation; its exact cause was not established. Stop acknowledgement itself succeeded. Receive buffers were enlarged where the driver supports it, and subsequent discontinuities log their frame pair and operating mode. The extended 45-Hz GUI trial initially reached frame 7062 with zero gaps/invalid packets, then logged `9354 -> 9356 during running` at 00:25:15 local time. It ended at frame 19309 with one discontinuity and no malformed packets. The SDK sends a stats packet even with zero detected points, so zero detections do not explain the missing sequence number. Its root cause was not established; do not claim the 45-Hz candidate is lossless. The final selection is therefore the more conservative 40-Hz point/health-only profile, retaining the same 3.88-cm nominal separation and all 3D/display improvements. The 45/48-Hz profiles remain experimental. Do not generalize sparse-scene tests to every target density or unlimited-duration operation.

17 parser/state/history/stop tests passed; the original 151 captured packets still all parse correctly. Tests cover transport subtraction, reserved temperature field exclusion, invalid temperature reports, profile timing units, cursor/session restart and unconfirmed-stop errors. JavaScript syntax, real-frame queue order/deduplication/restart/stale discard, projection guards/orientation and camera controls passed. Local HTTP health/auth/Host tests passed (unauthorized controls and bad Host return 403). Actual browser Top/Front/Zoom/Reset/drag/keyboard and stopped/live states were checked. Clean Close now returns its response before shutting down; browser verified Viewer closed. No browser console errors on the final live view. Physical touch pinch remains untested.

## Delivery and controls
The browser originally polled at 250 ms (~4 visible updates/s); reducing a timeout alone still yielded ~25/s, and smaller UART output increased USB batching. The final solution uses local HTTP/1.1, TCP_NODELAY, non-overlapping polls with 8-ms post-response delay, a bounded 32-frame server cursor history and a bounded client queue. Animation displays actual measured frames once each, without position interpolation or synthetic measurements; queued frames over 250 ms old are discarded. Receive rate, actual unique displayed-frame rate, nominal range separation and displayed packet receive age are shown separately. RF/USB latency precedes this receive-age metric.

Busy CLI input sometimes truncated a burst `sensorStop`. Stop commands now pace characters at 5 ms, retry up to three times, and require acknowledgement; an unconfirmed stop is an error rather than falsely reporting stopped. Runtime safety also stops on a valid maximum sensor temperature of 85 C or transport-inclusive reserve below 5% for three frames; existing 15-minute session and 15-second client-loss stops remain.

Final server: **PID 42784**, http://127.0.0.1:8766/, profile `tdm-wide-points-40hz.cfg`, left live. Logs under the task runtime:
- `live-viewer-40hz-stable-stdout.log`, `live-viewer-40hz-stable-stderr.log` — current selected run
- `live-viewer-45hz-final-stdout.log`, `live-viewer-45hz-final-stderr.log`
- `bench-baseline-20hz.json`, `bench-baseline-30hz.json`, `bench-baseline-40hz.json`
- `bench-wide-20hz.json`, `bench-wide-30hz.json`, `bench-wide-40hz.json`, `bench-wide-40hz-validation.json`
- `bench-points-40hz.json`, `bench-points-45hz.json`, `bench-points-48hz.json`, `bench-points-45hz-validation.json`

Runtime root: `C:\Users\chap_\.codex\.chatgpt-projects\g-p-69f1b1cfff0c81919aa91c82a1c098a6\tmp\radar-flash-2026-11-02`. Initial wide 30/40-Hz logs contain the subsequently fixed stop-input warning; only later explicitly confirmed runs establish successful cleanup. Preserve these historical logs.

Rollback: close the current viewer, then launch the same server using `profiles/tdm-baseline-10hz.cfg`. No reflash is needed. The SDK documents VCO2's 76-80.5 / 76.5-81-GHz alternatives (4.5-GHz instantaneous span), so generic 5-GHz chip coverage is not proof that one chirp can sample all 5 GHz. Source: installed `mmwave_dfp_02_04_18_01/ti/control/mmwavelink/include/rl_sensor.h` and SDK TDM output/RF parser code; official chip overview https://www.ti.com/product/AWR2944P.
