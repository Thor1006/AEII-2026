# Radar rate / resolution audit — 2026-11-02

Read-only investigation completed for the user's request to approach theoretical performance limits. No runtime settings, source code or firmware were changed.

The current receiver runs at 10 Hz, but browser polling caps visible refresh near 4 Hz. Read-only health showed the sensor had stopped after 5866 consecutive frames, zero invalid packets and zero sequence gaps. Existing capture statistics and installed TI source imply a rough 46-Hz ceiling for the unchanged waveform/output in that sparse test, before operational headroom. The 64.26-Hz acquisition-only limit is not an achievable end-to-end guarantee. Current nominal range separation is 4.36 cm; full 5-GHz ideal separation is about 3 cm, subject to supported acquisition/settling constraints. Accuracy and angular/velocity resolution must be evaluated separately.

Evidence: task-local `radar-smoke-capture.dat` (151 real frames), SDK `mmw_tdm/include/mmw_output.h` stats layout, `mmw_tdm/mss/mss_main.c` timing semantics, `ti/demo/utils/mmwdemo_rfparser.c` formulas, viewer `index.html` 250-ms polling, and TI's official AWR2944P product specifications at https://www.ti.com/product/AWR2944P.

[Proposed staged implementation and verification](../plans/2026-11-02-radar-rate-resolution.md). Waiting for OK as explicitly required by `CLAUDE/CLAUDE.md`; this plan remains proposed, not done. No commit/push.
