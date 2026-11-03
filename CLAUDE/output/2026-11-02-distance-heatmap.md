# Distance-colored live radar view — 2026-11-02

Completed the user's explicitly requested small presentation change in the existing local viewer. Only `index.html` rendering and its accompanying documentation changed; the separate rate/resolution tuning proposal remains proposed and unapproved. No radar waveform/configuration, server acquisition logic, firmware, main dashboard or submitted document was changed.

Each measured reflection uses the already-decoded 3D range for a red/orange → green → cyan/blue palette, clamped to 0 through the selected Display range. A matching labeled legend updates on range selection. Soft halos improve visibility while outlined dots mark measured locations; blank areas contain no measurements. The screen explicitly distinguishes distance from temperature/signal strength. Stopped data retains its colors at reduced opacity with LAST FRAME / NOT LIVE status.

Verification: local HTTP returned 200 with the new markup; browser JavaScript compiled; palette endpoints/intermediate stops were inspected. The actual browser showed the updated heatmap and warm/cool legend. Reload invoked the existing page-close stop behavior, so Start was used to resume the unchanged official profile. Fresh real frames advanced from 180 to 263 at 10.0-Hz receiver rate and 0.0-s displayed age. Browser polling remains 250 ms; this is a visual change, not higher measurement rate/accuracy. No new tests were added for this reversible presentation change.

Local preview: `C:\Users\chap_\.codex\.chatgpt-projects\g-p-69f1b1cfff0c81919aa91c82a1c098a6\tmp\radar-flash-2026-11-02\live-distance-heatmap.png`. Existing viewer remains open at http://127.0.0.1:8766/ with the same bounded-session/client-loss watchdogs. No commit or push.
