# Report: Raspberry Pi software set v0.1 (build → test → verify → debug)

<!-- Filename: YYYY-MM-DD-HHMM-<slug>.md -->

**Date:** 2026-11-05 21:19 · **Result:** ✅ done (not yet run on a real Pi or with the live radar) · **Plan:** [plans/2026-11-05-pi-software-set.md](../plans/2026-11-05-pi-software-set.md)

## Goal
"Prepare a software set for raspberry pi from what we have right now", in a build / test / verify / debug loop.
The user also asked for the package to be copied to the PortableSSD, with the test install (and its packages) on the
SSD.

## The set
`truerehab-pi-0.1.0-20261105-de84695.tar.gz`: 0.5 MB, 96 files, built from committed code.
- **Where:** `deploy/pi/dist/` (git-ignored) and `/Volumes/PortableSSD/TrueRehab-Pi/`.
- **sha256:** `6c8322a394c3047492708397f240effa5c3d2287682b6eb8af8e7e26a2370141`, verified after the copy.

**What it does on the Pi:**
- At boot, the bridge serves the dashboard at `http://<kit>.local:8080`, with the **live radar** as the network's
  3 maps at 15/s, plus health and temperature.
- Dashboard **Start/Stop** records every radar frame (60 fps) into `~/truerehab-sessions/`, in the recorder's format.
- The **model tools** come with `install.sh --with-model`.

**Not in v0.1:** live model scores (no radar-only rep finder yet; the network is fake-trained), and live
IMU/MyoWare in the dashboard.

## What was built (each pushed after its tests)
| Commit | What |
|---|---|
| `8a5874b` | recorder: two sessions started in the same second get `_2` instead of crashing (found by the new bridge test) |
| `8ff8c11` | pi-bridge: the real radar provider (details below) |
| `5b5809e` | recorder tests: the camera test is skipped without mediapipe/opencv (failed in the Pi self-test) |
| `9044087` | `deploy/pi/`: installer, self-test, bundle builder, Pi config, boot service template, README |
| `611b50f` | pi-bridge: viewers can connect again (an Oct-12 bug); clean shutdown on SIGTERM; live end-to-end test |
| `9ffa6ce` | recorder + model: a recording with no radar frames is reported, not a crash |
| `de84695` | dashboard: radar frames/s compared with all views together ("of 45", not "of 15") |

**The radar provider (`8ff8c11`):**
- finds the XDS110 ports;
- starts the radar with the profile already in use (no flashing);
- builds the 3 maps with the model's own preprocessing;
- reports health in plain words;
- has a `replay` mode for testing;
- records in the recorder's format;
- passes markers from the dashboard to data sources.

## Debug loop: problems found and fixed
1. **`Viewer` not hashable** (`611b50f`). Every dashboard connection to the real Python bridge failed with 1011. It
   had been like that since Oct 12, and nobody noticed because the bridge had never run with `websockets`
   installed. Found by the first `check_bridge.py` run against the installed set.
2. **Stopped instantly by systemd** (`611b50f`). SIGTERM killed the bridge immediately, which would leave the radar
   streaming and its command port silent until reset, with any recording unfinished. It now shuts down like Ctrl+C.
   Verified: SIGTERM mid-recording gives exit 0 and a finished recording (845 frames, 0 missing).
3. **Same-second session folders** crashed (`8a5874b`). Found by a provider test.
4. **Empty recording crashed** `check_session.py` (`9ffa6ce`). Found when checking the instant Start/Stop of
   `check_bridge`.
5. **Self-test problems** (`5b5809e`, `9044087`). The camera test needed mediapipe, and the model test was started
   the wrong way.
6. **Misleading frame rate** (`de84695`): "48.4 of 15".
7. **macOS `._` files** next to the bundle on the exFAT drive (`9044087`). The builder now strips that metadata.
   The tarball itself never contained any.
8. **3.12-only syntax check:** Python's 3.11 check (`ast feature_version`) misses f-strings that reuse their own
   quote. The builder checks for that separately; tested on 6 cases.

## Verified by
- **Unit tests:** bridge 47 (2 new files: provider, live connection), model 61, recorder 14, radar-lab 6.
- **Build:** the dashboard builds; all 65 Python files pass the 3.11 check.
- **Install test on the PortableSSD (exFAT):**
  - `install.sh --no-systemd --system-site-packages` made the venv with copies (detected automatically, no
    symlinks on exFAT) and installed `websockets` 15.0.1 and `pyserial` 3.5, in 38 s. numpy and PyTorch were reused.
  - Updating in place kept the venv and `config.toml`.
- **`selftest.py`:** PASS, 0 failures. The warnings were "radar not plugged in" and, until the bridge ran, "no
  bridge".
- **Installed bridge with the real curls recording replayed:**
  - `check_bridge.py --commands`: PASS 16/16. The 3 maps arrive at 15.0/s each, a status every 1.0 s, no gaps in
    460 messages, ping 1 ms, and Start, marker and Stop all work.
  - The self-test's own checker step: PASS 11/11.
- **Dashboard served by the bridge:**
  - connects by itself: "Signal good", the no-key warning, Start session;
  - the radar map with its 3 view buttons, all 4 streams arriving;
  - 0 messages lost, 1 ms round trip, 134 KB/s, "48.3 of 45" frames/s;
  - no console errors.
- **Recording + shutdown:** Start through a WebSocket client, then SIGTERM mid-recording: exit 0, and the session is
  finished (845 frames, 0 missing). `check_session.py`: 60.00 fps, 0 missing, 48 °C, movement in 35 % of frames.

## Not verified (needs hardware or a Pi)
- **Live radar:** it was unplugged after this evening's measurement. The live path (ports, start, frames) is only
  tested through the replay mode and the port-detection tests.
- **A real Raspberry Pi 5:** Raspberry Pi OS, aarch64 wheels, `apt` and systemd, `dialout`, CPU load and
  temperature. `install.sh` ran in test mode only. Its systemd and `dialout` parts have only been syntax-checked.
- **Shutdown delay:** up to ~10 s while a dashboard is open (the server waits for the connection to close); the
  service allows 20 s.

## On the PortableSSD (`/Volumes/PortableSSD/TrueRehab-Pi/`)
- **Final:** `truerehab-pi-0.1.0-20261105-de84695.tar.gz` and its `.sha256`.
- **Older:** 2 intermediate builds (`8ff8c11-modified`, `611b50f`), left for the user to delete.
- **`test-install/`:** the unpacked set with its `.venv`, `pi-bridge/config.replay.toml` (test only) and
  `recordings/`: 2 test sessions (the empty `check_bridge` one and the SIGTERM one).

## Next
1. **Live radar** (power first, then USB): run the installed bridge with `config.toml` and `check_bridge.py`, then
   Start/Stop in the dashboard.
2. **On the Pi:** flash the SD card (README step 1), copy the set from the SSD, `bash install.sh`, then
   `selftest.py`. Note the CPU load and temperature.
3. **Later:** radar-only rep detection, then live scores; live IMU/MyoWare in the dashboard.

**Uncommitted work:** only these notes, committed next.
