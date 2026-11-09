# Report: autopilot while the user was away: Pi set built, demo-day plan, event rules

<!-- Filename: YYYY-MM-DD-HHMM-<slug>.md -->

**Date:** 2026-11-09 19:25 · **Result:** ✅ done, as far as possible without the hardware (uncommitted) ·
**Plan:** [plans/2026-11-09-aeii-demo-day.md](../plans/2026-11-09-aeii-demo-day.md) (proposed)

## Goal
The user asked for autopilot ("go auto pilot for the next 2 reset cycle"). Rules kept:
- no firmware, no radar or board runs;
- no commits or pushes;
- nothing changed in the main folder;
- anything that needs the user or the hardware is listed below.

## What was done
1. **Pi set built:** `truerehab-pi-0.3.0-20261109-2440d3b.tar.gz` (0.6 MB, 107 files), with its `.sha256`.
   - It is in this branch's `deploy/pi/dist/` (git-ignored), built from the pushed branch tip `2440d3b`.
   - It has the sEMG-health fix and the 9 Nov restart fix.
   - Built with the main folder's `node_modules` linked for the dashboard build and removed afterwards, the way
     `scripts/check_all.sh` does it.
   - The main folder's `wifi-pause-fixes` was not moved; see DECISIONS.
   - Superseded the same day by `truerehab-pi-0.3.0-20261109-33ae848`, which adds fix F1.
2. **The hall network:** already covered by `deploy/pi/README.md` ("At the venue": the Pi as access point, a travel
   router, an iPhone hotspot). Nothing to add: it needs a decision and an hour's test at home.
3. **Demo-day plan** (proposed):
   - tests at home before 17 Nov, packing list, setup at the booth, during the demo;
   - fallbacks from live to recorded to demo data;
   - one small fix proposed (F1);
   - the event rules and a draft email to the organiser.
4. **Event pages:**
   - the PolyU and CUHK listings, the official site's conditions, the Entrepreneur Day rules (2023; a scan, read with
     macOS text recognition) and its 2024 exhibitor services manual, plus the InnoEX 2026 manual for comparison;
   - nothing on them is dated 15 Nov.
5. **The system map** (version 6): milestone step 1 ticked, now 1 of 7, with the new steps and the real update time.

## Verified by
- **The set's checksum** matches; `VERSION.json` says commit `2440d3b`, not dirty.
- **Python 3.11 syntax:** OK for 73 files (the build's own check).
- **Both fixes are inside the set:** the bridge's "waiting for sEMG samples" (Python and the built dashboard) and
  `device_runs` in the recorder.
- **The set's own tests, run from the unpacked copy** (the tests `selftest.py` runs):
  - pi-bridge 67 OK, 14 skipped (they need `websockets`, which only the SSD's venv has);
  - recorder 23 OK, 1 skipped (with the recorder's venv; plain `python3` lacks `pyserial`);
  - radar-lab 6 OK; model `test_radar` 9 OK, 2 skipped.
- **Map:** checked earlier today at 375 px, 716 px and 1280 px, light and dark. The page no longer scrolls
  sideways; this version only changed the steps' text.

## Found
- **The radar stops after 65,535 frames (about 18 min at 60 fps).**
  - The bridge restarts it after 3 s of silence; the restart re-sends the settings.
  - That restart has never run: the bridge has never driven the live radar.
  - During those seconds the dashboard says "No frames for 3 s. Check the cables…", which would mislead people at
    the booth.
  - Fix F1 is proposed in the plan, not made.
- **The event rules (Entrepreneur Day, 2023 edition):**
  - demonstrations and working exhibits need the organiser's written approval in advance;
  - working exhibits are never left running unattended;
  - power comes only through the venue's contractor, at 210–230 V.
  So the team should ask now about the live demo, its own Wi-Fi network and a socket.
- **The venue's free Wi-Fi** is for light use and drops idle devices. Another HKTDC fair's manual suggests exhibitors
  rent their own router, so the kit's own network looks normal there; approval is unconfirmed.
- **Build-up and dismantling dates, and the jury's day,** come in the organiser's "General Instructions" to
  registered teams.

## Issues / not done
- **Not done; it needs the SSD:** copying the set there and the replay check with its venv.
- **Not done; it needs the Pi and radar:** everything from step 3 of the milestone on.
- **No answer yet:** whether anything is due on 15 Nov (the 5 Oct plan said so). The public pages show nothing.
- **Not read:** the official site's Apply page.
- **Not sent:** the email to the organiser. It goes from the team's registered address.

## Next
1. Send the email (plan G), and decide Pi access point or travel router (order it now if so).
2. Plug in the SSD: copy the set, run the replay check, then the Pi steps of the milestone.
3. Say yes or no to fix F1 (the bridge's message and a quick restart at the frame limit). A frame count of 0 is
   no way out: it crashed `sensorStart` on this board (report 2026-11-03).

**Uncommitted work:** none: committed on branch `claude/codebase-audit-diagram-786f9c` (not pushed).
