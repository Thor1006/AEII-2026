# TrueRehab-RF — Raspberry Pi set (v0.3)

What it does on a Raspberry Pi 5:
- At boot it starts the **bridge**. A phone or laptop on the same Wi-Fi opens `http://<kit>.local:8080` and sees the
  **live radar**: the 4 maps the network uses ("Where things are", "Tiny motion", "Points (height)", "Movement speed"), plus radar
  health and temperature.
- **sEMG (new in v0.2):** with the MyoWare 2.0 on its Wi-Fi link, the dashboard's "Reference signals" panel shows
  the muscle's **envelope** and its **median frequency** (it falls as the muscle tires; sent only during movement).
- **Start/Stop** in the dashboard records every radar frame (60 fps) and every sEMG sample (1 kHz) into one folder
  in `~/truerehab-sessions/`, on one clock, in the recorder's format.
- The **model tools** (session check, dashboard replays) run on the Pi after `install.sh --with-model`.

**New in v0.3:** smoother live data over Wi-Fi (see "Wi-Fi: smooth live data" below).

**Not in v0.3:**
- **Live model scores.** The network needs reps cut from the radar alone, and that part doesn't exist yet. The
  network is also trained on fake data only.
- **Live IMU in the dashboard.** Record it with `recorder/record.py` (stop the bridge first).

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
3. **sEMG (MyoWare):** see "MyoWare (sEMG)" below. Without it, everything else works as before.
4. **Record:** press Start (type a subject **code** like `S01`, never a name), do the exercise, then Stop. The session
   folder appears in `~/truerehab-sessions/`.
5. **Check a recording** (needs `--with-model`). With radar + sEMG only (no camera, no IMU), reps come from the sEMG
   bursts and it says "can train: fatigue ✓":
   ```bash
   .venv/bin/python model/check_session.py ~/truerehab-sessions/<folder>
   ```
6. **Self-test** (everything, including the running bridge and the MyoWare):
   ```bash
   .venv/bin/python selftest.py
   ```

## MyoWare (sEMG)
1. **Upload its sketch once, from a computer** with the Arduino IDE (board "ESP32 Dev Module"):
   `firmware/myoware_record/`. First copy `wifi_secrets.example.h` to `wifi_secrets.h` next to it and put in the
   Wi-Fi name and password (2.4 GHz; at school use a phone hotspot with "Maximize Compatibility"). Nobody may wear
   the sensor while USB is plugged in.
2. **Turn it on in `pi-bridge/config.toml`:** `[providers.emg]` → `enabled = true` (an older `config.toml` lacks the
   section: copy it from `config.pi.toml`), then `sudo systemctl restart truerehab-bridge`.
3. **Wear it on battery.** The dashboard shows "MyoWare sEMG" with its samples/s and Wi-Fi strength. Between
   movements the median frequency shows "Waiting for movement": that's normal.

No board yet? `.venv/bin/python pi-bridge/fake_myoware.py` sends **fake** sEMG the way the board does, on
`tcp://127.0.0.1:3334`: set `port` to that to test everything.

## Wi-Fi: smooth live data (new in v0.3)
The MyoWare sends over 2.4-GHz Wi-Fi. Now and then the network holds its data back for about a second (after a
short radio blackout the ESP32 most likely waits 1–2 s before it resends). Nothing is lost: it arrives late, all at once.
What v0.3 does about it:
- **The live charts run a moment behind:** 0.25 s, or up to 1.5 s after a pause, so a short pause no longer
  freezes them. Recordings don't change.
- **The MyoWare's health line counts the pauses**, e.g. "2 Wi-Fi pause(s) in 5 min, longest 1.1 s". The log
  (`journalctl -u truerehab-bridge -f`) has a line per pause, next to "viewer connected" lines.
- **The dashboard stream is about 5× lighter** (8-bit maps, 10 maps/s, 25 envelope values/s), so less traffic on
  2.4 GHz. An older `pi-bridge/config.toml` keeps its own values: copy `frame_dtype`, `fps` and `env_hz` from
  `config.pi.toml`.

**One reader per board.** The MyoWare serves one program at a time, and a new one kicks out the old. Stop the
Mac's `record.py` or any other bridge while the Pi reads it. If two keep trying, the dashboard says "Another program
is reading the MyoWare…" and the Pi waits longer each time (5, 15, 30, 60 s).

**On the Pi, once: Wi-Fi power save off.** Find the Wi-Fi connection's name (Imager usually calls it `preconfigured`):
```bash
nmcli -t -f NAME,TYPE connection show
```
```bash
sudo nmcli connection modify preconfigured 802-11-wireless.powersave 2
```
```bash
sudo nmcli connection up preconfigured
```
Check that this says `off`:
```bash
iw dev wlan0 get power_save
```

**During sessions:** unplug the USB 3 SSD (USB 3 gives off noise near 2.4 GHz), and don't run `nmcli dev wifi list`
(it makes the Pi scan for networks, which pauses its Wi-Fi).

**Placement:** the router (or the Pi, when it is the access point) 1–2 m in front of the person, at chest height, on
the sensor's side. The body blocks 2.4 GHz: watch the lowest "Wi-Fi … dBm" in the health line during a set of curls
(above −65 dBm is good, below −70 is weak).

### Laptop on a cable (keeps the dashboard off Wi-Fi)
Plug a network cable from the laptop (USB-C LAN adapter) into the Pi's Ethernet port. On the Pi, once (not tested on
our Pi yet):
```bash
sudo nmcli connection add type ethernet ifname eth0 con-name trh-laptop ipv4.method shared connection.autoconnect no
```
Each time:
```bash
sudo nmcli connection up trh-laptop
```
Then open `http://10.42.0.1:8080` on the laptop: the address, not `trh-kit-01.local`, so the data stays on the
cable. (Don't use this profile while the Pi's Ethernet port is plugged into a router.)

### At the venue: bring the kit's own network
Venue Wi-Fi with a login page (like the HKCEC's) doesn't work for the boards. The boards know one Wi-Fi name and
password (their `wifi_secrets.h`): any network for them must use that name and password, or both boards need a
re-flash. Pick one:
1. **The Pi as the access point (free).** It takes the Pi off its current Wi-Fi, so set it up with the laptop cable
   above (or a keyboard and screen). With the boards' Wi-Fi name, once:
   ```bash
   sudo nmcli connection add type wifi ifname wlan0 con-name trh-ap ssid "BOARDS-WIFI-NAME" 802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 6 ipv4.method shared wifi-sec.key-mgmt wpa-psk connection.autoconnect no
   ```
   Start it (`--ask` asks for the boards' Wi-Fi password, so it isn't saved in the shell history):
   ```bash
   sudo nmcli --ask connection up trh-ap
   ```
   Back to the normal Wi-Fi:
   ```bash
   sudo nmcli connection up preconfigured
   ```
   Viewers join this network and open `http://10.42.0.1:8080` (or use the laptop cable). Use channel 1 or 11 instead
   of 6 if 6 is crowded (`nmcli dev wifi list` shows the networks around: run it before a session, not during). Never
   run a phone hotspot with the same name at the same time. If the bridge can't find `truerehab-myoware.local`, put
   the board's address in `port`. **Not tested on our Pi yet:** try it at home for an hour with both boards first.
2. **A small travel router** (e.g. GL.iNet Opal, about 1,500 THB): its 2.4-GHz network gets the boards' name and
   password, a fixed channel (1, 6 or 11) at 20 MHz, 802.11b off; the Pi on its LAN port; viewers on its 5-GHz
   network or a cable. The most robust choice.
3. **An iPhone hotspot** ("Maximize Compatibility" on) as the last resort, with the iPhone itself as the dashboard
   (one hop instead of two).

### Wi-Fi check (about 25 min, MyoWare on the bench, nothing flashed)
1. Exactly one program reads the board.
2. Four 5-minute recordings with Start/Stop (subject code `TEST`):
   - **A:** no dashboard watching (press Start, close the tab, reopen it to press Stop);
   - **B:** the Mac watching over Wi-Fi;
   - **C:** the Mac on the laptop cable;
   - **D:** the iPhone watching, reloading the page 5 times, 10 s apart.
3. Compare them. `recorder/link_report.py` needs only Python; run it on the Pi, or on the Mac after copying the
   folders (`scp -r pi@trh-kit-01.local:~/truerehab-sessions ~/Downloads/`):
   ```bash
   python3 recorder/link_report.py ~/truerehab-sessions/<A> ~/truerehab-sessions/<B> ~/truerehab-sessions/<C> ~/truerehab-sessions/<D>
   ```
   It says how often the data paused and why (held by the network, ended by the ESP32's resend timer, not sent by
   the board, another program on the board), then prints a table that compares the four.

## 5. Update to a newer set
Unpack the new `.tar.gz` over the old folder (`tar xzf ...` in the same place), then run `bash install.sh` again.
Your `pi-bridge/config.toml` and your recordings are kept (an old `record_dir` under `[providers.radar]` still works;
new settings belong under `[bridge]`).

## Troubleshooting
- **Logs:** `journalctl -u truerehab-bridge -f`.
- **Status and restart:** `sudo systemctl status truerehab-bridge`, `sudo systemctl restart truerehab-bridge`.
- **"Not plugged in":** power the radar first, then USB. `ls /dev/ttyACM*` should list 2 ports.
- **"didn't accept its settings" or "no frames":** press the radar's reset button (or replug its power) and wait
  10 s. The bridge retries every few seconds.
- **"data port busy":** only one program may read the radar. Stop the bridge first
  (`sudo systemctl stop truerehab-bridge`) before using `recorder/record.py` or radar-lab.
- **Hot radar:** the dashboard warns at 85 °C. Stop and let it cool.
- **MyoWare "Not reachable":** is it switched on (battery), running `firmware/myoware_record`, and on the same Wi-Fi
  as the Pi? School and guest Wi-Fi often block devices from talking to each other: use a phone hotspot.
- **MyoWare "Flat signal" or "clipping":** check the electrodes (fresh pads, on the muscle belly) and that the
  sensor is pressed onto the shield.

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
| `pi-bridge/` | The bridge: dashboard server, radar and sEMG providers, kit key, `check_bridge.py`, `fake_myoware.py`, tests |
| `firmware/myoware_record/` | The MyoWare's sketch (upload from a computer, not from the Pi) |
| `frontend/dist/` | The built dashboard |
| `model/` | The network's preprocessing, session check, replays, calibration numbers, tests |
| `radar-lab/` | The radar frame reader and its profile (`configs/fullmap_awr2x44p.cfg`) |
| `recorder/` | The session format and `record.py` (all sensors, one clock) |
| `install.sh`, `selftest.py`, `config.pi.toml`, `requirements-*.txt`, `truerehab-bridge.service.in` | Setting it up |
| `VERSION.json` | Version, git commit, and a sha256 for every file |
