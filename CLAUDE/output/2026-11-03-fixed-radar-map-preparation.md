# Fixed-radar mapping preparation

The user requested surrounding mapping, then explicitly clarified a stationary radar accumulating the front-of-room view. Read-only review confirms the current x/y/z/velocity data and existing frame cursor can support a bounded accumulated reflection map without changing the RF profile or firmware. Current static clutter removal is off, so stationary detections are not intentionally removed by that option; this does not guarantee visible walls or a complete room.

[Concrete proposed scope and verification](../plans/2026-11-03-fixed-radar-room-map.md): 30-second retention, bounded 10-cm display cells with distinct-frame persistence, map/live layers, Clear and Pause/Resume, measured-distance colors, fixed-board labels and no surface/free-space fabrication. Scope clarification has been received; implementation still awaits the written-plan OK required by the repo. No source code, runtime settings, map accumulation or firmware has been changed in this preparation turn.

Read-only health at the start: running, last frame 25763 / 25762 packets, ~40.4-Hz receive rate, eight points, one sequence gap, zero invalid packets, ~644 seconds. This later observation supersedes any implication that the prior short zero-gap checks guaranteed indefinite losslessness. Preserve the gap counter. The map must never interpret missing data as confirmed empty space.

Reference reviewed: TI AWR2944/AWR2944P EVM guide, antenna section, https://www.ti.com/lit/ug/spruj22c/spruj22c.pdf. No new physical FoV, 360-degree or SLAM capability is claimed. Existing local viewer remains as found; no commit or push.
