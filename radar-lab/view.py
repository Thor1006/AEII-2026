"""See the whole scene from a TI mmWave demo: static objects and moving ones.

  python3 view.py --sim                        # fake room, no radar needed
  python3 view.py --sim --clutter-removal      # what the point-cloud demo shows
  python3 view.py --sim --save out.png         # one snapshot, no window

  .venv/bin/python view.py --cli-port /dev/cu.usbmodemXXXX1 --probe
  .venv/bin/python view.py --cli-port ... --data-port ... --cfg configs/fullmap_awr2x44p.cfg
  .venv/bin/python view.py --data-port ... --layout configs/fullmap_awr2x44p.cfg --dump 5
"""
import argparse
import struct
import sys
import time

import numpy as np

from radarlab import cfg, maps, sim
from radarlab.tlv import (AZIMUTH_STATIC_HEATMAP, DETECTED_POINTS, MAGIC,
                          RANGE_DOPPLER_HEATMAP, TLV_NAMES, FrameReader)


def open_serial(port, baud):
    try:
        import serial
    except ImportError:
        sys.exit("Live mode needs pyserial. Run with .venv/bin/python (see README).")
    try:
        return serial.Serial(port, baud, timeout=0.05)
    except serial.SerialException as e:
        sys.exit(f"Can't open {port}: {e.strerror or e}\nPlugged in? List ports with:  ls /dev/cu.usbmodem*")


def cli_send(cli, line, wait=1.0, char_delay=0.0):
    """Send one CLI line and return what the radar answered.

    char_delay: pause between characters. While the radar streams at 60 fps it drops command
    characters sent at full speed (seen 2026-11-04: "sensorStop" arrived as "s").
    """
    if char_delay:
        for ch in (line + "\n").encode():
            cli.write(bytes([ch]))
            cli.flush()
            time.sleep(char_delay)
    else:
        cli.write((line + "\n").encode())
    out, end = b"", time.time() + wait
    while time.time() < end:
        out += cli.read(4096)
        if any(w in out for w in (b"Done", b"Error", b"not recognized", b"Exception")):
            break
    return out.decode(errors="replace").strip()


FAILED = ("Error", "not recognized", "Exception")


def stop_radar(cli, tries=3):
    """Stop a running radar: type sensorStop slowly and retry until it says Done.

    Do this before closing the command port: closing it while the radar runs leaves the port
    silent until the board is reset (the data keeps flowing).
    """
    reply = ""
    for _ in range(tries):
        reply = cli_send(cli, "sensorStop", wait=3.0, char_delay=0.01)
        if "Done" in reply and "not recognized" not in reply:
            return True, reply
        time.sleep(0.2)
    return False, reply


def send_cfg(cli, lines):
    for line in lines:
        reply = cli_send(cli, line, wait=3.0 if line == "sensorStart" else 1.0)
        said = [l.strip() for l in reply.splitlines()
                if l.strip() and l.strip() not in (line, "mmwDemo:/>")]
        print(f"> {line}\n  {' | '.join(said) or '(no reply)'}")
        if not reply:
            print("The radar's command port isn't answering. On the AWR2944PEVM it goes silent once the\n"
                  "radar has been started (the data keeps coming). Press the board's reset button, then run again.")
            return False
        if any(w in reply for w in FAILED):
            if "Exception" in reply:
                print("The firmware crashed. Press the board's reset button (or replug its power) before trying again.")
            else:
                print("Stopped: the radar refused that line. Run --probe to see the commands it knows.")
            return False
    return True


class Source:
    """Frames from the simulator or from the data serial port."""

    def __init__(self, args):
        self.reader = FrameReader()
        self.room = sim.Room(args.clutter_removal) if args.sim else None
        self.port = None if args.sim else open_serial(args.data_port, args.data_baud)
        self.next_sim = 0.0
        self.total = 0
        self.head = b""  # first bytes received, for diagnosis

    def poll(self):
        if self.room:
            if time.time() < self.next_sim:
                return []
            self.next_sim = time.time() + 1 / sim.FPS
            return self.reader.feed(self.room.frame())
        data = self.port.read(max(1, self.port.in_waiting))
        self.total += len(data)
        if len(self.head) < 256:
            self.head += data[: 256 - len(self.head)]
        return self.reader.feed(data)

    def wait(self, timeout):
        end = time.time() + timeout
        while time.time() < end:
            frames = self.poll()
            if frames:
                return frames[-1]
            time.sleep(0.01)
        return None

    def explain_silence(self):
        if self.room or not self.total:
            return "No bytes at all. Is the radar started (sensorStart), and is this the data port?"
        magic = "found" if MAGIC in self.head else "NOT found (wrong baud rate?)"
        return (f"Got {self.total} bytes but no whole frame. Magic word {magic}.\n"
                f"First bytes: {self.head[:64].hex(' ')}")


def points_xy(payload):
    n = len(payload) // 16
    pts = np.array(struct.unpack(f"<{4 * n}f", payload[: 16 * n])).reshape(n, 4)
    return pts[:, 0], pts[:, 1]


def heatmap_shape(frame, args, layout):
    """(range bins, virtual antennas, note) for this frame's static heatmap."""
    static = frame.tlvs.get(AZIMUTH_STATIC_HEATMAP, b"")
    rd = frame.tlvs.get(RANGE_DOPPLER_HEATMAP, b"")
    if layout and rd:
        n_range = len(rd) // (2 * layout.doppler_bins)
        n_virt = len(static) // (4 * n_range) if static else layout.n_virt
        # the AWR2944P demo sends only the azimuth row (8 of 12), which is fine too
        if static and n_virt not in (layout.n_virt, len(layout.az_index)):
            return n_range, n_virt, f"static heatmap has {n_virt} antennas, cfg says {layout.n_virt}"
        return n_range, n_virt, ""
    n_virt = layout.n_virt if layout else args.virt_ant
    return (len(static) // (4 * n_virt) if static else args.range_bins), n_virt, ""


class View:
    def __init__(self, args, layout, title):
        import matplotlib.pyplot as plt
        self.plt, self.args, self.layout = plt, args, layout
        self.fig, (self.ax_map, self.ax_rd) = plt.subplots(1, 2, figsize=(13, 6))
        self.fig.suptitle(title)
        self.mesh = self.rd_img = self.dots = None
        self.ang = maps.angles_deg(args.angle_bins)

    def draw(self, frame):
        a, L = self.args, self.layout
        static = frame.tlvs.get(AZIMUTH_STATIC_HEATMAP)
        rd = frame.tlvs.get(RANGE_DOPPLER_HEATMAP)
        n_range, n_virt, note = heatmap_shape(frame, a, L)
        if static:
            index = cols = None
            if L is not None and not note and a.use_geometry:
                cols = L.az_cols
                index = L.az_index if n_virt == L.n_virt else list(range(n_virt))
            ra = maps.range_azimuth(static, n_virt, a.az_ant, a.angle_bins, a.flip, index, cols)
            self._draw_map(maps.to_db(ra))
        if rd:
            self._draw_rd(maps.range_doppler(rd, n_range))
        if DETECTED_POINTS in frame.tlvs and self.mesh is not None:
            x, y = points_xy(frame.tlvs[DETECTED_POINTS])
            if self.dots is None:
                (self.dots,) = self.ax_map.plot(x, y, "o", mfc="none", mec="w", ms=9,
                                                label="point cloud (what the demo sends)")
                self.ax_map.legend(loc="upper right", fontsize=8)
            else:
                self.dots.set_data(x, y)
        missing = [TLV_NAMES[t] for t in (AZIMUTH_STATIC_HEATMAP, RANGE_DOPPLER_HEATMAP)
                   if t not in frame.tlvs]
        if missing:
            note = (note + "; " if note else "") + "missing: " + ", ".join(missing)
        self.ax_map.set_title(f"Top view, everything (frame {frame.number})"
                              + (f"\n{note}" if note else ""), fontsize=10)

    def _draw_map(self, ra):
        r = np.arange(ra.shape[0]) * self.args.range_res
        th = np.radians(self.ang)
        R, T = np.meshgrid(r, th, indexing="ij")
        X, Y = R * np.sin(T), R * np.cos(T)
        lo = max(np.percentile(ra, 50), ra.max() - 40)  # show the top 40 dB
        if self.mesh is None:
            self.mesh = self.ax_map.pcolormesh(X, Y, ra, shading="gouraud", cmap="inferno",
                                               vmin=lo, vmax=ra.max())
            self.ax_map.set_aspect("equal")
            self.ax_map.set_xlabel("x (m) — left / right")
            self.ax_map.set_ylabel("y (m) — away from radar")
            self.ax_map.set_ylim(0, r[-1])
            self.ax_map.set_facecolor("black")
            self.fig.colorbar(self.mesh, ax=self.ax_map, label="dB")
        else:
            self.mesh.set_array(ra.ravel())
            self.mesh.set_clim(lo, ra.max())

    def _draw_rd(self, rd):
        r_max = rd.shape[0] * self.args.range_res
        half = rd.shape[1] // 2
        edges = [-half - 0.5, rd.shape[1] - half - 0.5]  # bin centres land on whole numbers
        if self.args.vel_res:
            ext, xl = [e * self.args.vel_res for e in edges], "speed (m/s)"
        else:
            ext, xl = edges, "Doppler bin (0 = not moving)"
        if self.rd_img is None:
            self.rd_img = self.ax_rd.imshow(rd, origin="lower", aspect="auto", cmap="viridis",
                                            extent=[*ext, 0, r_max])
            self.ax_rd.set_xlabel(xl)
            self.ax_rd.set_ylabel("range (m)")
            self.ax_rd.set_title("Range vs speed: still things sit on the middle line", fontsize=10)
        else:
            self.rd_img.set_data(rd)
            self.rd_img.set_clim(rd.min(), rd.max())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sim", action="store_true", help="use the fake room instead of a radar")
    p.add_argument("--clutter-removal", action="store_true", help="sim only: hide still objects, like the demo default")
    p.add_argument("--cli-port", help="radar CLI serial port (config, 115200)")
    p.add_argument("--data-port", help="radar data serial port (frames)")
    p.add_argument("--cli-baud", type=int, default=115200)
    p.add_argument("--data-baud", type=int, default=3125000, help="AWR2944PEVM demo: 3125000 (found by scanning)")
    p.add_argument("--cfg", help="send this config file before viewing (also used as --layout)")
    p.add_argument("--layout", help="read antenna layout and scales from this config, without sending it")
    p.add_argument("--probe", action="store_true", help="ask the radar which CLI commands it knows, then exit")
    p.add_argument("--stop", action="store_true", help="send sensorStop, then exit")
    p.add_argument("--dump", type=int, metavar="N", help="print the TLVs of N frames, then exit")
    p.add_argument("--save", metavar="PNG", help="save one snapshot instead of opening a window")
    p.add_argument("--virt-ant", type=int, default=sim.VIRT_ANT, help="virtual antennas in the static heatmap (no layout)")
    p.add_argument("--az-ant", type=int, default=None, help="use only the first N antennas (no layout)")
    p.add_argument("--angle-bins", type=int, default=64)
    p.add_argument("--range-bins", type=int, default=sim.RANGE_BINS, help="only used if the static heatmap is missing")
    p.add_argument("--range-res", type=float, help="metres per range bin (default: from the cfg, or the sim)")
    p.add_argument("--vel-res", type=float, help="m/s per Doppler bin; 0 = show bins (default: from the cfg, or the sim)")
    p.add_argument("--flip", action="store_true", help="mirror left/right if the map looks reversed")
    # On the AWR2944PEVM (2026-11-03) evenly spaced looked like a real room; antGeometryCfg
    # positions turned a ~1 m object into a ring of repeating blobs. Confirm with a known target.
    p.add_argument("--use-geometry", action="store_true",
                   help="place antennas by the cfg's antGeometryCfg (default: evenly spaced, as sent)")
    args = p.parse_args()

    layout = cfg.load(args.layout or args.cfg) if (args.layout or args.cfg) and not args.sim else None
    if args.range_res is None:
        args.range_res = layout.range_res if layout else sim.RANGE_RES_M
    if args.vel_res is None:
        args.vel_res = layout.vel_res if layout else sim.VEL_RES_MS

    if args.cli_port and (args.probe or args.cfg or args.stop):
        cli = open_serial(args.cli_port, args.cli_baud)
        if args.probe:
            for cmd in ("version", "help"):
                print(f"> {cmd}\n{cli_send(cli, cmd, wait=2.0)}\n")
            return
        if args.stop:
            print(cli_send(cli, "sensorStop", wait=2.0))
            return
        if not send_cfg(cli, cfg.read_lines(args.cfg)):
            return
    if not args.sim and not args.data_port:
        p.error("give --sim, or --data-port (plus --cli-port to probe or configure)")
    if not args.sim and not args.cli_port:
        print("Note: no --cli-port given, so no config was sent; the radar must already be running.")

    src = Source(args)
    if args.dump:
        for _ in range(args.dump):
            f = src.wait(5.0)
            if f is None:
                sys.exit("No frames in 5 s. " + src.explain_silence())
            parts = ", ".join(f"{t} {TLV_NAMES.get(t, '?')} ({len(b)} B)" for t, b in f.tlvs.items())
            n_range, n_virt, note = heatmap_shape(f, args, layout)
            print(f"frame {f.number}: {parts}\n  -> {n_range} range bins x {n_virt} antennas"
                  f" = {n_range * args.range_res:.2f} m{'  !! ' + note if note else ''}")
        print(f"skipped bytes between frames: {src.reader.dropped}")
        return

    if args.sim:
        title = "Simulated room" + (" — clutter removal ON" if args.clutter_removal else "")
    else:
        title = f"Radar on {args.data_port}"
    if args.save:
        import matplotlib
        matplotlib.use("Agg")
    view = View(args, layout, title)
    if args.save:
        f = src.wait(5.0)
        if f is None:
            sys.exit("No frames in 5 s. " + src.explain_silence())
        for _ in range(4):  # a few frames in, so the picture has settled
            f = src.wait(2.0) or f
        view.draw(f)
        view.fig.savefig(args.save, dpi=110, bbox_inches="tight")
        print(f"Saved {args.save}")
        return

    from matplotlib.animation import FuncAnimation

    def tick(_):
        frames = src.poll()
        if frames:
            view.draw(frames[-1])

    anim = FuncAnimation(view.fig, tick, interval=30, cache_frame_data=False)  # noqa: F841 (keep alive)
    view.plt.show()


if __name__ == "__main__":
    main()
