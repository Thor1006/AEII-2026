# Plan: Raspberry Pi software set (v0.1) from what exists today

**Status:** done (2026-11-05, [report](../output/2026-11-05-2119-pi-software-set.md)): v0.1 built, tested on the PortableSSD install, verified with a replayed real recording; live radar and a real Pi still to verify. Was approved (2026-11-05). The user answered "can you put it in package but also make a copy into PortableSSD drive?" (taken as: build the full v0.1 set, and copy the package to the SSD) and, for installs, "Install it in PortableSSD please". So `websockets` and `pyserial` go into a test venv on `/Volumes/PortableSSD/TrueRehab-Pi/` (exFAT: no symlinks, so `venv --copies`; the package is built without macOS `._` files). The existing `AEII-2026` and `Code` folders on the SSD are not touched.
**Date:** 2026-11-05

## Why
The user asked: "can you prepare a software set for raspberry pi from what we have right now? do it in a usual build
test verify debug loop".

What exists today:
- **`pi-bridge/`:** dashboard server, protocol 1.2, kit key, checker, systemd unit. Its radar provider is an empty
  template.
- **`frontend/`:** the dashboard.
- **`radar-lab/`:** reads the AWR2944PEVM over USB.
- **`recorder/`:** the session format.
- **`model/`:** preprocessing, network, session check, replays.

Nothing has run on a Pi yet. The Pi 5 is received; its OS is not set up.

## What the set does (v0.1)
- **On boot,** the Pi starts the bridge. A phone or laptop on the same Wi-Fi opens `http://<kit>.local:8080` and
  sees the **live radar**: the network's 3 views ("Where things are", "Tiny motion", "Movement speed"), with health
  and temperature.
- **Recording:** Start/Stop in the dashboard records the radar into a session folder in the **recorder's format**,
  so `model/check_session.py` and `export_dashboard.py` work on it unchanged.
- **Model tools on the Pi:** the session check and replay export. Their PyTorch install is optional, because the
  wheel is ~150 MB.
- **Not in v0.1:**
  - **Live model scores:** the network needs reps cut from the radar alone. Today reps come from the IMU or camera,
    and a radar-only rep finder doesn't exist yet. Also, the network is trained on fake data only.
  - **Live IMU/MyoWare** in the dashboard: they're still recorded by `recorder/record.py`.

## Build (files)
1. **`pi-bridge/truerehab_bridge/providers/radar.py`:** the real radar provider (replaces the template).
   - **Ports:** auto-detects the board's 2 USB ports (TI XDS110), or uses the ones set in config.
   - **Start/stop:** sends the existing `fullmap_awr2x44p.cfg` at start, exactly like the recorder (no flashing,
     no new settings), and `sensorStop` at exit. It clears a stray byte on the command port first, which is the
     failure seen today.
   - **Reading:** a thread reads frames with radar-lab's `FrameReader`.
   - **Frames:** made with the model's own `trnet.radar` functions, at 15 fps to viewers.
   - **Health:** says in plain words "not plugged in", "didn't accept its settings", or 60 fps and the
     temperature.
   - **`replay = <session folder>`:** plays a recorded session in real time, for testing without the radar.
   - **Recording:** `on_session_start/end` writes `radar.bin`, `radar_index.csv`, `meta.json` and `markers.csv`
     with the recorder's `SessionWriter`.
2. **`deploy/pi/`** (new):
   - `config.pi.toml`: a real kit, with synthetic data off and the radar on.
   - `requirements-pi.txt`: `websockets`, `numpy`, `pyserial`, with optional `torch` for the model tools.
   - `install.sh`, which runs on the Pi and can be run again safely:
     - checks the Pi 5 / 64-bit system and Python ≥ 3.11;
     - makes a venv and installs the packages;
     - adds the user to `dialout` for USB serial ports;
     - installs and enables the systemd service with the right paths, then prints the dashboard address.
     - `--dry-run` shows the steps; `--no-systemd` is for testing on a Mac.
   - `selftest.py`: checks the Python version, imports, unit tests, the radar's ports and `check_bridge` against
     the running service.
   - `build_bundle.py` (runs on the Mac): makes `deploy/pi/dist/truerehab-pi-<date>-<commit>.tar.gz`.
     - It rebuilds the dashboard and checks every Python file against Python 3.11 syntax (the Pi's version).
     - It copies only what the Pi needs, with no data, caches or replays.
     - It writes `VERSION.json` with the git commit and file hashes.
   - `README.md`, step by step: Raspberry Pi Imager settings, copying the bundle, `install.sh`, opening the
     dashboard, recording, checking, safety.
3. **Tests:** `pi-bridge/tests/test_radar_provider.py`. It replays a real recording through the provider and
   checks frame shapes and timing, the recording written in recorder format, port detection logic and health
   messages.

## Test → verify → debug loop (on this Mac; there's no Pi here yet)
1. **Build** the bundle; Python 3.11 syntax check; the dashboard builds.
2. **Test:** unit tests (bridge with the new provider, model, recorder), then install the bundle into a temp
   folder with `install.sh --no-systemd` and run `selftest.py` there.
3. **Verify, no hardware:** run the installed bridge with `replay` on today's real curls recording;
   `check_bridge.py` must pass (hello, manifest, every stream arriving at its rate, Start/Stop commands).
4. **Verify, real radar** (it's plugged into this Mac): run the bridge with the radar; `check_bridge.py` passes; the
   dashboard shows the live radar in the browser; Start → Stop records a session; `check_session.py` reads it
   (radar OK, 0 missing).
5. **Debug:** fix whatever fails and repeat until all green. Report with timings and what still needs a real Pi.

## When I need you
- **Step 4:** nothing, unless the radar needs its reset button. Its power must stay on.
- **On the real Pi later:** flashing the SD card with Raspberry Pi Imager, then copying the bundle and running
  `install.sh`. The README walks through it.

## Risks / needs OK
- **Installs on this Mac** (your pause from Nov 4 says to ask): `websockets` and `pyserial` into a test venv from
  PyPI, about 0.4 MB. numpy and PyTorch are already installed. Nothing goes into the system Python.
- **Radar:** only the settings already in use (P0), sent the same way the recorder sends them. No flashing.
- **Commits:** small chunks, pushed as each one passes its tests, as you asked for the clean-up.
- **Not verifiable here:** the real Pi (aarch64, Raspberry Pi OS), its CPU load and the systemd service itself.
  `install.sh` is only dry-run tested.
