# radar-lab — see the whole room, not just what moves

A standalone test, separate from `pi-bridge/` and `frontend/`.

**Theory (confirmed on the AWR2944PEVM, 2026-11-03):** the TI point-cloud demo only shows
moving things because the firmware (1) removes static clutter and (2) sends only the
strongest detected peaks. Turn clutter removal **off** and ask for the **heatmaps**
instead, and walls, furniture and a person sitting still all show up.

```
radar (USB) ── CLI port  (115200):   config lines (clutterRemoval off, heatmaps on)
            └─ data port (3125000):  frames ─► view.py ─► left:  top view of everything (range × angle)
                                                          right: range × speed (still things on the 0 line)
```

`real_room3d.png` / `real_room.png` are real snapshots; `room3d.png`, `room.png`, `room_clutter_removal.png` are the simulator.

## 3D at 60 fps (`view3d.py`)

The full-room map is the floor (relief = echo strength). The radar's points stand on stems at
their measured height, coloured cyan when still and orange when moving. The range-vs-speed
panel sits on the right. **Measured on the AWR2944PEVM: 60 radar frames/s with both heatmaps, 0 lost.**
The screen redraws with the display (120 Hz on this Mac) and glides between radar frames.

Start the radar at 60 fps and open the window (one command; closing the window stops the radar):

```bash
.venv/bin/python view3d.py --cli-port /dev/cu.usbmodemRA29P0551 --data-port /dev/cu.usbmodemRA29P0554 --cfg configs/fullmap_awr2x44p.cfg --period-ms 16.667 --frames 65535
```

- Mouse: drag to orbit, scroll to zoom. Keys: **H** relief, **R** auto-rotate, **F** mirror left/right, **T** trails.
- `--measure 10` instead of a window: radar fps, lost frames, serial-link load and the firmware's own timing.
- 65 535 frames is the most the firmware takes: ~18 min at 60 fps. Then run the command again.
- `--period-ms 33.333` = 30 fps if 60 ever gets unstable.
- Without a radar: `.venv/bin/python view3d.py --sim`

**Important: the command port.** If a program closes the command port while the radar is running,
the port goes silent until you press reset (the data keeps flowing). So `view3d.py` keeps it open and
sends `sensorStop` when you close the window. *That stop-on-close step is not yet tested on the board.*
If a run says "the radar's command port isn't answering", press reset and run again.

## 2D viewer (`view.py`, AWR2944PEVM over USB)

Uses the folder's own Python environment `.venv/` (has `pyserial`, `pyqtgraph`, `PyQt6`, `PyOpenGL`;
reuses the Mac's numpy/matplotlib). To make it again:
`python3 -m venv --system-site-packages .venv && .venv/bin/python -m pip install pyserial pyqtgraph PyQt6 PyOpenGL`

Start the radar and open the live window (one command):

```bash
.venv/bin/python view.py --cli-port /dev/cu.usbmodemRA29P0551 --data-port /dev/cu.usbmodemRA29P0554 --cfg configs/fullmap_awr2x44p.cfg
```

- Ports: `ls /dev/cu.usbmodem*` — the one ending in `1` is the CLI, the one ending in `4` is data.
- The config runs 10 000 frames (~50 min at 300 ms), then the radar stops. Run the command again to restart.
- Radar already running? Leave out `--cli-port` and `--cfg`, and add `--layout configs/fullmap_awr2x44p.cfg` for the scales.
- Stop it: `.venv/bin/python view.py --cli-port /dev/cu.usbmodemRA29P0551 --stop`
- `Exception: ./mss/mmw_cli.c …` means the firmware crashed: press the board's reset button, then run again.
- Check what arrives: add `--dump 5` instead of opening a window. `--save out.png` saves one picture.
- Probe the firmware's commands: `--cli-port … --probe` (sends only `version` and `help`).

## What we learned about this board

| | |
|---|---|
| Firmware | mmWave demo, SDK 04.07.02.01, platform AWR2X44P, TDM, **UART output** (no `enetStreamCfg` command) |
| Data port speed | **3 125 000 baud** (921 600 gives garbage) |
| `frameCfg` numFrames | must not be 0: `0` (forever) crashed `sensorStart` (TI E2E reports the same for SDK 4.7) |
| Frame contents | TLV 1 points, 7 point side info, 4 static heatmap, 5 range-Doppler heatmap; 40-byte header |
| Heatmap size | 64 range bins × 0.059 m = 3.8 m; static heatmap has **8** antennas (azimuth row only), RD has 16 Doppler bins × 0.137 m/s |
| Antenna order | evenly spaced looks right; `antGeometryCfg` positions (`--use-geometry`) gave a ring of repeating blobs. Not yet confirmed with a known target |
| Frame rate | 30 fps and **60 fps** both run with both heatmaps + points + stats, 0 frames lost. At 60 fps: ~4.4 KB/frame, processing 0.66 ms, UART send 14.1 ms, spare 1.7–7.8 ms per frame |
| Command port | answers while the radar runs only if it stays open; closed + reopened while running → silent until reset (seen 3×) |
| Point heights | points carry z (one TX sits on a raised row); about 6 points/frame with clutter removal off, mostly still objects |

## Still open

- **Stop-on-close** in `view3d.py` (keeps the command port open, sends `sensorStop`): untested on the board.
- **3D is points only:** this firmware's heatmap is flat (range × left/right). Dense 3D would need raw data (DCA1000) or custom firmware.
- **Left/right and angle check:** stand ~1.5 m away, off to one side, and see where the blob appears. Use `--flip` if mirrored.
- **Near 0 m** there is a strong echo from the radar itself. `calibDcRangeSig -1 1 …` in the config may remove it (untested).
- **Range** is only 3.8 m with this chirp; a different `profileCfg` can trade resolution for distance.
- **LAN:** this firmware streams over USB only. Streaming over Ethernet needs TI's Ethernet out-of-box demo
  flashed on the board (`enetStreamCfg`), and its Ethernet demo is documented to send detected objects, not heatmaps.
  **Don't flash without agreeing it first.**

## Try it without the radar

```bash
python3 view.py --sim
```

```bash
python3 view.py --sim --clutter-removal
```

## Files

- `view3d.py` — 3D viewer at display rate (pyqtgraph/OpenGL; `--measure`, `--save`, `--sim`)
- `view.py` — 2D viewer (matplotlib; `--probe`, `--dump`, `--save`, `--stop`)
- `radarlab/tlv.py` — frame parser for the demo's UART output
- `radarlab/maps.py` — static heatmap → range-azimuth map; range-Doppler reshape
- `radarlab/cfg.py` — antenna layout and range/speed scales from a config file
- `radarlab/sim.py` — fake room that sends the same bytes as the demo
- `configs/fullmap_awr2x44p.cfg` — the working config (clutter removal off + heatmaps on)
- `tests/` — `python3 -m unittest discover tests`
