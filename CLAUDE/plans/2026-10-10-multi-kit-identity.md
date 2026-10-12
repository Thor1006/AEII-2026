# Plan: Multi-kit identity (telling sensor sets and Pis apart)

**Status:** proposed
**Date:** 2026-10-10


## Context
TrueRehab-RF should support several users, each with their own sensor set. Setup chosen:
**1 kit = 1 Raspberry Pi 5 + AWR1843BOOST (+ DCA1000) + Arduino (sEMG/force)**. Each Pi processes its data locally and sends results to one central dashboard. Users **log in per session**, so kits are shared and the system must always know *which kit*, *which device in that kit*, and *which user/session* each piece of data belongs to.

Honest note: we haven't made a real capture yet. Build the cheap parts now (IDs in the data format, an Arduino ID handshake, a kit file). Leave the central server until there are 2+ real kits.

## Design: 4 identity layers

| Layer | ID | Where it lives | How it's checked |
|---|---|---|---|
| Kit | `kit_id` e.g. `KIT-01` | `/etc/truerehab/kit.json` on the Pi, hostname `trh-kit-01` (reach it as `trh-kit-01.local`), QR sticker on the case | The Pi's own hardware serial (`/sys/firmware/devicetree/base/serial-number`) must match the serial in `kit.json` |
| Device | `device_id` e.g. `KIT-01/radar`, `KIT-01/semg` | Listed in `kit.json` with each USB serial number | udev rules + a startup handshake |
| User | `user_id` (pseudonymous, e.g. `U-0007`) | Central server only. No names on the Pi (PDPA) | Login on the dashboard |
| Session | `session_id` (UUID) | Made by the server when a user scans the kit's QR code | Sent to the Pi with the "start" command |

### 1. Telling devices apart inside a kit (on the Pi)
- **Radar (AWR1843BOOST):** the on-board XDS110 has a unique USB serial and shows up as 2 ports (CLI and data). A udev rule matches serial + interface number and creates fixed names: `/dev/trh-radar-cli` and `/dev/trh-radar-data`. Then the code never touches `ttyACM0/1`, which can change order.
- **DCA1000:** it connects over Ethernet with a fixed IP (192.168.33.180). The Pi's Ethernet port goes only to the DCA1000, so there's no clash; the Pi's uplink uses Wi-Fi. *Risk:* capturing from the DCA1000 on Linux/Pi needs TI's DCA1000 CLI instead of mmWave Studio. Check this before relying on it.
- **Arduino:** cheap clones (CH340 chip) have **no unique serial**, so udev alone can't be trusted. Fix: an **ID handshake**. The PC sends `ID?` and the Arduino replies `{"dev":"semg","kit":"KIT-01","fw":"0.1"}`, using values stored in EEPROM. The Pi scans its serial ports and assigns them by the reply.
- **Startup self-check** (`kit_check.py`): compare the devices found with the list in `kit.json`. If anything is missing, or belongs to another kit, refuse to record and show a clear error, e.g. "sEMG Arduino from KIT-02 plugged into KIT-01".

### 2. Linking a user to a kit (login per session)
1. The user logs in on the dashboard (phone or laptop) and scans the kit's QR code (`kit_id`).
2. The server creates `session_id` and sends `start {session_id, user_id}` to that kit.
3. The Pi tags **every** packet and file with `{kit_id, device_id, session_id, seq, t_mono_ns, t_wall}`.
4. "End session" (or a timeout) closes it. The Pi never keeps the user binding between sessions.

### 3. Transport and storage
- **MQTT** (a Mosquitto broker on the server). Topics: `trh/<kit_id>/status`, `trh/<kit_id>/<device>/data`, `trh/<kit_id>/cmd`. Each kit gets its own username/password, so it can only publish under its own `kit_id`. The dashboard subscribes over MQTT-over-WebSocket (this fits the `WebSocketSource` in the 2026-10-10 frontend plan).
- **Storage:** `data/<user_id>/<session_id>/{meta.json, radar.bin, aux.csv}`. `meta.json` holds the kit, device serials, firmware versions, chirp config and radar mount height. Per-user folders are also what Phase 6 personalization needs.
- **Time sync:** run `chrony` on every Pi so timestamps from different kits line up.

## Files to create (when approved)
- `kit/kit.example.json`: kit manifest schema (kit_id, pi_serial, devices[] with type/usb_serial/expected handshake)
- `kit/99-truerehab.rules.template`: udev rule template for the radar ports
- `kit/arduino_id/arduino_id.ino`: `ID?` handshake + EEPROM identity, to be merged into the sEMG sketch
- `kit/kit_check.py`: discover → match against the manifest → report (has a `--mock` mode, since there's no hardware here)
- `kit/packet.py`: the shared packet header / `meta.json` writer used by capture code

Not now: the central server, auth and MQTT broker setup. Do these once there are 2 real kits.

## Verification
- `kit_check.py --mock` with fake devices covers: everything OK, missing radar, Arduino from the wrong kit, two Arduinos with the same ID. Each case should give the expected message.
- On real hardware later: unplug and replug in a different order, then run `ls -l /dev/trh-*` and `kit_check.py`. The names must stay stable.
- Flash the Arduino handshake **only after asking** (project rule). The radar/DCA1000 firmware and config are not touched.

## Open questions
- How many kits for AEII? If it's 1–2, a shared Wi-Fi network + mDNS might be enough with no MQTT server.
- Genuine Arduino or clones? This decides whether udev-by-serial is enough on its own.
