# TrueRehab-RF — Pi bridge

Runs on the Raspberry Pi 5 in each kit. It collects data from the radar, Arduino and AI model ("providers"), sends it live to the web dashboard over WebSocket, and serves the dashboard itself. People just open `http://<pi>.local:8080`, and the page connects without typing anything.

```
providers (radar · Arduino · model) ──► bridge ──WebSocket :8765──► dashboards on the same Wi-Fi
                                          └──── HTTP :8080 serves the dashboard page
```

> **Status:** the radar provider is only a template (`providers/radar.py`); no capture code exists yet. The **synthetic** provider sends made-up demo data so everything else can be tested now. The dashboard labels it "Demo data".

## Setup on the Pi (5 steps)

1. **Copy the project** to the Pi (e.g. `git clone`, or copy the folder to `/home/pi/AEII-2026`).
2. **Build the dashboard** on any computer with Node.js, then copy `frontend/dist/` to the Pi into the same place:
   ```bash
   cd frontend && npm install && npm run build
   ```
3. **Install the bridge** (on the Pi, in `pi-bridge/`):
   ```bash
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   ```
4. **Configure:** `cp config.example.toml config.toml`, then set `name`, `kit_id`, and which providers are on.
5. **Start it:**
   ```bash
   .venv/bin/python -m truerehab_bridge --config config.toml
   ```
   It prints the address to open, e.g. `http://trh-kit-01.local:8080`. To start it on every boot, see `truerehab-bridge.service`.

Then check it from any computer on the same network:

```bash
.venv/bin/python check_bridge.py trh-kit-01.local --commands
```

## Check before a demo: `check_bridge.py`

Connects like a dashboard and checks that the Pi sends everything the page needs:

- `hello` comes first, with a valid manifest (radar views, scores, signals, commands)
- every announced stream actually arrives, at roughly the announced rate
- radar frames have the right byte layout and shape, with no NaN values
- messages arrive in sequence with no gaps; the Pi clock matches (otherwise install `chrony`)
- the status heartbeat lists devices; ping gets a pong
- with `--commands`: session start → status shows it → marker → unknown command refused → stop

Exit code 0 = pass, 1 = something failed, 2 = can't connect. It also works against the frontend's Node mock (`npm run mock`).

## Pairing a kit: the kit key (protocol 1.2)

A kit key proves **who** is connecting. Nobody on the Wi-Fi can watch the data or press start/stop without it, and your laptop can tell a real kit from a fake one. The key itself is never sent over the Wi-Fi.

1. Make a key, saving it as a file (works without a screen or remote login, e.g. on the SD card while it's in your Mac, in the boot partition):
   `python -m truerehab_bridge --new-key --write /boot/firmware/trh-key.txt`
2. In `config.toml`, under `[bridge]`: `key_file = "/boot/firmware/trh-key.txt"`.
3. Start the bridge. It prints `Kit key: ON`. Print the sticker link with `python -m truerehab_bridge -c config.toml --show-link` and make a QR code from it.
4. Scanning the QR opens the dashboard with the key saved in the browser (the part after `#` never goes to a server, and the page removes it from the address bar). Or type the key into the connect screen.

If someone loses the sticker, anyone who can take out the SD card can read the file. That is on purpose: physical access means ownership. To change a key, delete the file and make a new one.

Check it: `python check_bridge.py trh-kit-01.local --key <the key> --auth-selftest` proves a wrong key, an unsigned command, an edited command and a replayed command are all refused.

**What it doesn't do:** the data is still plain text on the Wi-Fi (`ws://`), so someone who relays traffic can read it. Use a Wi-Fi you trust. After 5 wrong keys from one address, the Pi refuses that address for a minute.

## What the Pi must send (protocol 1.2, same as 1.1 plus the key)

The full byte-level spec is in `frontend/README.md`. In short:

| Message | When | Why the dashboard needs it |
|---|---|---|
| `hello` (+ manifest) | First, to each viewer | Names, units, score directions, radar axes, the list of streams to expect, which commands work |
| `frame` (binary TRF1) | Every radar frame | Radar map |
| `scores` | A few times per second | Gauges, trend |
| `event` | Reps, compensation, recommendation, session start/end, markers | Rep counter, "What to do now", event log |
| `aux` | Each Arduino sample | Reference-signal charts |
| `status` | Every second | Device strip ("Arduino ✕ Not plugged in"), session state, demo-data banner, health |
| `ack` / `pong` | Replies to commands / pings | Start/Stop buttons, connection delay |

All of this is handled by the bridge. A provider only creates `Frame`, `Scores`, `Aux` and `Event` objects and lists them in `manifest()`.

## Adding the real radar

Edit `truerehab_bridge/providers/radar.py`; the docstring lists the steps. Rules:

- Everything you emit must also be listed in `manifest()`. Otherwise the dashboard labels it generically and `check_bridge.py` warns.
- Everything listed in `manifest()` must actually arrive. Otherwise the dashboard shows "Never arrived" and the checker fails.
- Put blocking work (UDP capture, FFT) in a thread. Hand messages back with `loop.call_soon_threadsafe(emit, msg)`.
- Report problems in `health()` in plain words. Users see them.
- Never flash firmware or change the radar configuration without asking the team.

## Files

| Path | What |
|---|---|
| `truerehab_bridge/server.py` | Envelope, broadcast, hello/status, commands, per-viewer buffers |
| `truerehab_bridge/protocol.py` | Message types and encoders (Python twin of `frontend/src/sensor/protocol.ts`) |
| `truerehab_bridge/providers/` | `synthetic.py` (demo), `serial_aux.py` (Arduino on the Pi), `radar.py` (template) |
| `truerehab_bridge/web.py` | Serves `frontend/dist` and `/truerehab-bridge.json` |
| `check_bridge.py` | Conformance checker |
| `truerehab_bridge/auth.py` | Kit key: handshake, signed commands, rate limit |
| `tests/` | Unit tests: `.venv/bin/python -m unittest discover -s tests` |

## Limits

- Without a kit key, anyone on the same Wi-Fi can view the kit and start or stop sessions. Set a key (see "Pairing a kit"). Real accounts and owner binding come later (multi-kit plan).
- The key proves who connects, but the data isn't encrypted.
- The bridge doesn't record to disk yet. Use the dashboard's Record button.
- Plain `http`/`ws` only. Open the dashboard over http, not https.
