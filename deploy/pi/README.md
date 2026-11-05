# TrueRehab-RF — Raspberry Pi set (v0.1)

What it does on a Raspberry Pi 5:
- At boot it starts the **bridge**. A phone or laptop on the same Wi-Fi opens `http://<kit>.local:8080` and sees the
  **live radar**: the 3 maps the network uses ("Where things are", "Tiny motion", "Movement speed"), plus radar
  health and temperature.
- **Start/Stop** in the dashboard records every radar frame (60 fps) into `~/truerehab-sessions/`, in the
  recorder's format.
- The **model tools** (session check, dashboard replays) run on the Pi after `install.sh --with-model`.

**Not in v0.1:**
- **Live model scores.** The network needs reps cut from the radar alone, and that part doesn't exist yet. The
  network is also trained on fake data only.
- **Live IMU/MyoWare in the dashboard.** Record those with `recorder/record.py` (stop the bridge first).

## 1. Prepare the SD card (on your Mac)
Use **Raspberry Pi Imager**: device **Raspberry Pi 5**, OS **Raspberry Pi OS (64-bit)** (Lite is enough), your
64-GB microSD. In its settings (the gear / "Edit settings"):
- **Hostname:** `trh-kit-01`
- **Username and password:** e.g. `pi`, with a password you choose
- **Wi-Fi:** your network, country `TH`
- **Services:** enable SSH, so you can log in from the Mac

Put the card in the Pi. Plug in the official 27-W USB-C power supply and wait about 2 minutes.

## 2. Copy the set to the Pi
- **From the Mac:**
  ```bash
  scp truerehab-pi-*.tar.gz pi@trh-kit-01.local:~
  ```
- **From the PortableSSD** (exFAT; Raspberry Pi OS reads it): plug the drive into the Pi and copy the `.tar.gz`
  from `TrueRehab-Pi/` to the home folder.

Check that the copy is complete: the result must match the `.sha256` file.
```bash
sha256sum truerehab-pi-*.tar.gz
```

## 3. Install (on the Pi)
```bash
ssh pi@trh-kit-01.local
tar xzf truerehab-pi-*.tar.gz
cd truerehab-pi
bash install.sh                 # add --with-model for the model tools (PyTorch, ~200 MB)
```
It does these steps (safe to run again):
1. checks the Pi;
2. makes `.venv`;
3. installs `websockets`, `numpy` and `pyserial`;
4. makes `pi-bridge/config.toml` from `config.pi.toml`;
5. adds you to `dialout` for USB serial ports;
6. installs the boot service `truerehab-bridge` and starts it.

`bash install.sh --dry-run` shows the steps without doing them.

## 4. Use it
1. **Radar:** plug its power in first, then its USB cable into the Pi. The bridge finds the 2 USB ports and starts
   the radar with the profile already in use. Nothing is ever flashed.
2. **Dashboard:** open `http://trh-kit-01.local:8080` on a phone or laptop on the same Wi-Fi.
3. **Record:** press Start (type a subject **code** like `S01`, never a name), do the exercise, then Stop. The session
   folder appears in `~/truerehab-sessions/`.
4. **Check a recording** (needs `--with-model`):
   ```bash
   .venv/bin/python model/check_session.py ~/truerehab-sessions/<folder>
   ```
5. **Self-test** (everything, including the running bridge):
   ```bash
   .venv/bin/python selftest.py
   ```

## 5. Update to a newer set
Unpack the new `.tar.gz` over the old folder (`tar xzf ...` in the same place), then run `bash install.sh` again.
Your `pi-bridge/config.toml` and your recordings are kept.

## Troubleshooting
- **Logs:** `journalctl -u truerehab-bridge -f`.
- **Status and restart:** `sudo systemctl status truerehab-bridge`, `sudo systemctl restart truerehab-bridge`.
- **"Not plugged in":** power the radar first, then USB. `ls /dev/ttyACM*` should list 2 ports.
- **"didn't accept its settings" or "no frames":** press the radar's reset button (or replug its power) and wait
  10 s. The bridge retries every few seconds.
- **"data port busy":** only one program may read the radar. Stop the bridge first
  (`sudo systemctl stop truerehab-bridge`) before using `recorder/record.py` or radar-lab.
- **Hot radar:** the dashboard warns at 85 °C. Stop and let it cool.

## Safety and privacy
- **MyoWare:** on a person, use it on battery only, never with USB plugged in (SparkFun's warning).
- **Subject codes only**, no names. Recording people needs their consent; ethics approval is still open.
- **Kit key:** without one, anyone on the Wi-Fi can watch and press Start/Stop. To make one:
  ```bash
  .venv/bin/python -m truerehab_bridge --new-key --write /boot/firmware/trh-key.txt
  ```
  Then set `key_file` in `pi-bridge/config.toml`.

## What's inside
| Folder | What |
|---|---|
| `pi-bridge/` | The bridge: dashboard server, radar provider, kit key, `check_bridge.py`, tests |
| `frontend/dist/` | The built dashboard |
| `model/` | The network's preprocessing, session check, replays, calibration numbers, tests |
| `radar-lab/` | The radar frame reader and its profile (`configs/fullmap_awr2x44p.cfg`) |
| `recorder/` | The session format and `record.py` (all sensors, one clock) |
| `install.sh`, `selftest.py`, `config.pi.toml`, `requirements-*.txt`, `truerehab-bridge.service.in` | Setting it up |
| `VERSION.json` | Version, git commit, and a sha256 for every file |
