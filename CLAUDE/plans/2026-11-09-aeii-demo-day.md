# Plan: AEII demo day: tests at home, packing, setup and fallbacks

<!-- Filename: YYYY-MM-DD-<slug>.md -->

**Status:** proposed (a draft for the team, written on autopilot on 9 Nov while the user was away). Done so far: fix F1
(approved by the user: "sure"; committed as `33ae848`, not yet run on the board) and the Pi set with it
**Date:** 2026-11-09

## Why
- The team's main plan for AEII (HKCEC Hall 1D, 19–20 Nov) is the poster talk with a live demo, slides as backup
  (DECISIONS 2026-11-04, on GitHub's `main`).
- The live demo has never run in one piece:
  - the Pi set has never run on the Pi;
  - the bridge has never driven the live radar, only recordings;
  - the Pi access point is untested;
  - the MyoWare has never been worn.
- The hall's Wi-Fi has a login page that the boards can't pass.
- This plan lists the tests to do at home, what to pack, the setup order, and what to switch to when something fails,
  so that a failure costs a minute, not the demo.

## Approach

### A. At home, by 17 Nov (each one is a test)
0. **First, by email:** send the organiser the email in G. The event rules need written approval for a live
   demonstration, and power comes only from the venue's contractor, so a missing socket has to be ordered in time.
1. **Pi set:** copy `deploy/pi/dist/truerehab-pi-0.3.0-20261109-33ae848.tar.gz` (in this branch's folder,
   `.claude/worktrees/codebase-audit-diagram-786f9c/`) to the SSD, then follow `deploy/pi/README.md`: flash the SD
   card, `bash install.sh`, `selftest.py`. Then turn the MyoWare on in `pi-bridge/config.toml`
   (`[providers.emg] enabled = true`); it is off in the shipped settings.
   - This set has the sEMG-health fix, the 9 Nov restart fix and fix F1.
   - It passed its own tests on the Mac. The full replay test needs the SSD's venv: run it once the SSD is plugged in.
2. **Live radar through the bridge for 25 min, hands off.**
   - At about 18 min the radar has sent its 65,535 frames and stops. With fix F1 the bridge sends its settings again
     after a quarter of a second of quiet. The health line then says "restarted 1× at its 18-min frame limit".
   - This has never run on the board: watch that the frames come back within a second or two.
   - Before F1, the bridge waited 3 s and said "Check the cables…".
3. **The hall network, for an hour with both boards.** Either the Pi as the access point (`trh-ap` in
   `deploy/pi/README.md`, free) or a travel router.
   - If you want the router, order it now so it arrives before you test.
   - The network must use the boards' Wi-Fi name and password; otherwise both boards need re-flashing.
4. **The Wi-Fi check** (A/B/C/D, 25 min) and `recorder/link_report.py`, on that network.
5. **The MyoWare worn for the first time:**
   - battery, switch ON, USB out, fresh pads on the biceps;
   - a few curls: the envelope should rise with effort.
6. **Two backup recordings** with Start/Stop, 2–3 min of curls each.
   - They stay in the Pi's `~/truerehab-sessions`; write down their folder names.
   - They are fallback 1 in E. Only the radar part replays; the sEMG stays live, or off.
7. **Dress rehearsal (30 min):** pack from list B, set up from scratch with list C, run the demo for 30 min, then try
   each fallback in E once.

### B. Packing list
- **Radar:** AWR2944PEVM, its power supply, its USB cable.
- **Pi 5:** cooler fitted, the 27-W USB-C power supply, the SD card with the set (a second card with the same set is
  cheap insurance).
- **MyoWare 2.0:** Wireless Shield, its battery charged, its charging cable, a fresh 10-pack of pads.
- **Laptop:** its charger, the USB-C LAN adapter and a network cable (the cable keeps the dashboard off Wi-Fi).
- **Network:** the travel router, if you choose one.
- **Power:** Hong Kong sockets are the UK 3-pin type (G), 220 V.
  - Bring an adapter for every plug and a power strip.
  - Check that each power supply says 100–240 V.
- **If you fly:** the MyoWare's battery goes in hand luggage (spare lithium batteries aren't allowed in checked
  bags); keep the radar board and the Pi in hand luggage too.
- **Printed:** this page and the poster talk.

### C. Setup at the booth (about 15 min)
1. Power strip in. **Radar: power first, then USB** into the Pi.
2. Pi power on. Start the network: the router, or the Pi as access point (on the Pi, over the laptop cable:
   `sudo nmcli --ask connection up trh-ap`).
3. MyoWare: battery, switch ON. It joins the network by itself.
4. **Laptop:**
   - on the cable (`trh-laptop` profile): open `http://10.42.0.1:8080`;
   - or on the Pi's access point: also `http://10.42.0.1:8080`;
   - or on a router: the address the bridge prints, e.g. `http://trh-kit-01.local:8080`.
5. Both health lines OK. Then on the Pi (over `ssh` from the laptop, or a keyboard and screen):
   `.venv/bin/python selftest.py --quick`. With the bridge running, it also runs the bridge checker. (The Mac's own
   Python can't run `check_bridge.py`: it has no `websockets`.)
6. One 1-minute test session with Start/Stop.
- **Placement:** the router (or the Pi as access point) 1–2 m in front of the person, at chest height, on the sensor's
  side.

### D. During the demo
- **One reader per board:** no `record.py`, radar-lab or Windows viewer on the radar or the MyoWare while the Pi reads
  them.
- **The MyoWare:** a team member wears it, only on battery (never with USB plugged in), with fresh pads.
- **About every 18 min** the radar restarts itself: a pause of a second or two, then "restarted N× at its 18-min
  frame limit" in the health line. This is expected.
- **What's real:** the radar and sEMG are live measurements. The model isn't trained, so there are no live scores (they
  also need radar-only rep detection). Say so if asked.

### E. If something fails (from most live to least)
| Fails | Switch to | How | Tell visitors |
|---|---|---|---|
| MyoWare or its Wi-Fi | Radar only | On the Pi, `pi-bridge/config.toml`: `[providers.emg] enabled = false`, then `sudo systemctl restart truerehab-bridge` | — |
| Live radar | 1. a recording from A6 | `[providers.radar] replay = "<full path of the session folder>"`, restart the bridge | "a recording from <date>" |
| The Pi | 2. the radar on the laptop | radar-lab `view3d.py` at 60 fps (`radar-lab/README.md`); it has run on this Mac with the real radar. Closing the window stops the radar. | — |
| Everything | 3. demo data | `npm run dev` and `npm run mock` in `frontend/` (`frontend/README.md`); the page shows a "Demo data" banner | "simulated data" |
| — | Poster and slides | The talk works without a demo | — |

### F. A small fix (approved 9 Nov: "sure"; committed as `33ae848`, not yet run on the board)
1. **The bridge at the radar's frame limit** (`pi-bridge/truerehab_bridge/providers/radar.py`, 5 new tests in
   `pi-bridge/tests/test_radar_provider.py`):
   - after its last frames and a quarter of a second of quiet, the bridge sends the settings again on the command
     port that is still open (closing it is what silences this board's port until a reset);
   - the health line says "restarting…" during the restart, then "restarted N× at its 18-min frame limit";
   - frame numbers count on across every restart, including the bridge's restart after an error, plus the frames
     the pause would have held. Before, a recording got two runs both starting at frame 1, and the model's reader
     (it sorts by number) would have mixed them;
   - if another program started the radar, the bridge says that it sent all its frames, not "Check the cables";
   - it is in the Pi set `truerehab-pi-0.3.0-20261109-33ae848`.
- **Not possible: no 18-minute stop at all.** A frame count of 0 ("forever") crashed `sensorStart` on this board
  (`radar-lab/README.md`, report 2026-11-03), so the restart stays, and F1 makes it quick and clear.

### G. Event rules found online, and questions for the organiser
Read on 9 Nov from public pages. Nothing on them is dated 15 Nov.
- **The event:** the 6th Asia Exhibition of Innovations and Inventions Hong Kong.
  - Organised by the Hong Kong Exporters' Association, inside HKTDC's Entrepreneur Day.
  - Hall 1D, HKCEC, 09:00–18:00 ([PolyU](https://www.polyu.edu.hk/kteo/about-kteo/news-and-events/events/2026/11/aeii-2026/)).
  - Pitch Day 19 Nov, award ceremony 20 Nov ([CUHK](https://kto.cuhk.edu.hk/en/news-events/events/others/call-for-applications-6th-asia-exhibition-of-innovations-and-inventions-hong-kong-internal-application-deadline-29-may-2026)).
- **Dates still to find:**
  - The [official conditions](https://inventions-hongkong.com/conditions-of-participation/) say the build-up and
    dismantling dates and the day the jury examines each invention come in the organiser's "General
    Instructions", sent after the entry form.
  - Check the team's email for them.
- **Entrepreneur Day rules** ([2023 edition](https://www.hktdc.com/event/eday/wp-content/uploads/sites/39/2023/09/EDay_RR_eng.pdf);
  this year's may differ):
  - **Power:** 210–230 V, single phase. Electricity, "whether from the mains, batteries or generators", comes only
    through the venue's official contractor (clauses 31–32). So make sure the booth has a socket, or order one.
  - **Working or moving exhibits:** only the team operates them, never left running unattended, and they need the
    organiser's prior written approval (clause 33).
  - **Demonstrations:** they need the organiser's advance written approval (clause 35).
  - **Dismantling:** not before the official closing time on the last day; everything cleared by 24:00
    (clauses 26 and 46).
- **The venue's Wi-Fi:**
  - It is for "light and casual usage": it may be slow or drop, and it disconnects idle devices. Exhibitors are told
    to order a broadband line instead
    ([Entrepreneur Day 2024 manual](https://www.hktdc.com/event/eday/wp-content/uploads/sites/39/2024/09/5.-Services-for-Exhibitors.pdf), 5.10).
  - The [InnoEX 2026 manual](https://innoex.hktdc.com/pdf/2026/exhibitor_manual/en/05.pdf) (another HKTDC fair at
    HKCEC) tells exhibitors to rent their own Wi-Fi router for payment devices, so a kit's own network looks normal
    there.
  - Nothing found says whether it needs approval.

**Draft email to the organiser** (exhibition@inventions-hongkong.com; send it from the address the team registered
with, and fill in the brackets):

> Subject: AEII 2026, [booth or entry number] TrueRehab-RF: live demo, power and Wi-Fi
>
> Dear AEII team,
>
> Our entry, TrueRehab-RF ([school], booth [number]), is a contactless rehabilitation monitor. We would like to show
> it working at our booth on 19–20 November:
> - **The demo:** a small 77-GHz radar sensor board (a Texas Instruments evaluation module) and a Raspberry Pi watch
>   a team member doing slow arm exercises while wearing a skin muscle sensor. A team member operates it at all
>   times; nothing moves except the person.
> - **Its own small Wi-Fi network:** the sensors use one (2.4 GHz, no internet), from the Raspberry Pi or a small
>   travel router.
> - **Power:** under 150 W in total (the Raspberry Pi, the radar board and a laptop), from one 220-V socket.
>
> Could you please confirm that the live demonstration and our own small Wi-Fi network are allowed, and whether
> our booth includes a power socket (if not, how and by when we should order one)? Could you also tell us the
> move-in time and the day the jury visits the booths?
>
> Thank you,
> [name, school, phone]

## Files touched
- This plan only. The Pi set was built into the git-ignored `deploy/pi/dist/`.
- F1 touched `pi-bridge/truerehab_bridge/providers/radar.py` and `pi-bridge/tests/test_radar_provider.py`.

## Risks / needs OK
- Nothing here flashes firmware or changes the radar's profile.
- The travel router (about 1,500 THB) is your call.
- The email in G goes out from the team, not from Claude.
- The rules quoted in G are the 2023 Entrepreneur Day edition; the organiser's reply and General Instructions are
  what count.

## How we'll verify
- A2–A6 are the tests; the dress rehearsal (A7) is the pass or fail before packing.
