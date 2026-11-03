# Separate car-style radar demo preparation

User requested a separate automotive/Tesla-style radar demo. Read-only review confirms a new HTML page can share the existing local frame-history API and COM collector. The proposed route is `/drive/` with a separate `sandbox/radar-car-demo/` source folder; the existing Room map HTML stays intact. A single service restart is necessary to load the route and will reset the RAM map on the existing acquisition-session reset behavior.

[Reviewable design, implementation scope and checks](../plans/2026-11-03-car-style-radar-demo.md): light automotive scene, illustrative ego-car at the sensor origin, distance grid, unclassified measured reflection markers, warm/cool distance emphasis, real metrics and shared Start/Stop. No fabricated object classes, lanes, road/path predictions, vehicle sizes or synthetic traffic. No new radar ports/session, firmware, hardware settings or main project dashboard changes.

Current health: running, last frame 20841 / 20840 received, seven current returns, ~40.1-Hz receive rate, one sequence gap and zero invalid packets. This read-only preparation made no implementation/runtime/firmware changes. Plan is proposed and awaits the explicit repo-required OK. No commit/push.
