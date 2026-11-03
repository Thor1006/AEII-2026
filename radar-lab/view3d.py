"""3D radar view: the full-room map as a floor + the 3D point cloud, redrawn at 60 fps.

  .venv/bin/python view3d.py --sim
  .venv/bin/python view3d.py --cli-port /dev/cu.usbmodemRA29P0551 --data-port /dev/cu.usbmodemRA29P0554 \\
      --cfg configs/fullmap_awr2x44p.cfg --period-ms 16.667 --frames 65535
  .venv/bin/python view3d.py --data-port ... --layout configs/fullmap_awr2x44p.cfg --measure 10

AWR2944PEVM (2026-11-03): 60 radar fps with both heatmaps, no frames lost. The screen redraws
in step with the display (60 Hz, or 120 Hz on ProMotion) and glides between radar frames.
Mouse: drag to orbit, scroll to zoom.
Keys: H height relief on/off, R auto-rotate, F mirror left/right, T point trails on/off.
"""
import argparse
import collections
import sys
import threading
import time

import numpy as np

from radarlab import cfg, maps, sim
from radarlab.tlv import (AZIMUTH_STATIC_HEATMAP, DETECTED_POINTS, RANGE_DOPPLER_HEATMAP,
                          STATS, FrameReader)
from view import cli_send, heatmap_shape, open_serial, send_cfg

# SDK 3.x stats TLV layout; assumed the same on the AWR2944 demo
STATS_NAMES = ("frame processing", "UART send", "frame margin", "chirp margin",
               "active CPU %", "idle CPU %")


class Feed(threading.Thread):
    """Reads frames on its own thread; the window just takes the newest one."""

    def __init__(self, args):
        super().__init__(daemon=True)
        self.args = args
        self.lock = threading.Lock()
        self.reader = FrameReader()
        self.room = sim.Room(fps=args.sim_fps) if args.sim else None
        self.port = None if args.sim else open_serial(args.data_port, args.data_baud)
        self.latest = None
        self.count = self.total_bytes = 0
        self.first_no = self.last_no = None
        self.t_first = self.t_last = None
        self.times = collections.deque(maxlen=400)

    def run(self):
        next_t = time.perf_counter()
        while True:
            if self.room:
                next_t += 1 / self.args.sim_fps
                time.sleep(max(0.0, next_t - time.perf_counter()))
                data = self.room.frame()
            else:
                data = self.port.read(max(1, self.port.in_waiting))
            frames = self.reader.feed(data)
            now = time.perf_counter()
            with self.lock:
                self.total_bytes += len(data)
                for f in frames:
                    self.count += 1
                    self.times.append(now)
                    if self.first_no is None:
                        self.first_no, self.t_first = f.number, now
                    self.last_no, self.t_last = f.number, now
                if frames:
                    self.latest = frames[-1]

    def take(self):
        with self.lock:
            f, self.latest = self.latest, None
            return f

    def fps(self):
        now = time.perf_counter()
        with self.lock:
            recent = [t for t in self.times if t > now - 2.0]
        if len(recent) < 2:
            return 0.0
        return (len(recent) - 1) / (recent[-1] - recent[0])


def parse_stats(payload):
    n = len(payload) // 4
    return np.frombuffer(payload[: 4 * n], "<u4").astype(float)


def parse_points(payload):
    n = len(payload) // 16
    return np.frombuffer(payload[: 16 * n], "<f4").reshape(n, 4).astype(float)  # x y z v


def stop_radar(cli):
    """Stop the radar through the command port we kept open since starting it.

    On the AWR2944PEVM the command port goes silent if it is closed while the radar runs
    (the data keeps coming), so stopping must happen before we let go of the port.
    """
    reply = cli_send(cli, "sensorStop", wait=3.0)
    print("Radar stopped." if "Done" in reply else f"sensorStop: {reply or 'no reply'}")


def measure(args, feed, secs, cli=None):
    """No window: run for `secs` and report rate, losses and the firmware's own timing."""
    t0, stats = time.time(), []
    while time.time() - t0 < secs:
        f = feed.take()
        if f is not None and STATS in f.tlvs:
            stats.append(parse_stats(f.tlvs[STATS]))
        time.sleep(0.002)
    with feed.lock:
        n, first, last = feed.count, feed.first_no, feed.last_no
        span = (feed.t_last - feed.t_first) if n > 1 else 0
        total, dropped = feed.total_bytes, feed.reader.dropped
    if n < 2:
        sys.exit(f"Only {n} frames in {secs} s. Is the radar running?")
    fps = (n - 1) / span
    missing = (last - first + 1) - n
    per_frame = total / n
    load = per_frame * fps * 10 / args.data_baud * 100  # 10 bits per byte on the wire
    print(f"radar frames: {n} in {span:.1f} s = {fps:.1f} fps  (frame numbers {first}..{last}, missing {missing})")
    link = "" if args.sim else f"   serial link busy: {load:.0f} %"
    print(f"bytes/frame: {per_frame:.0f}{link}   bytes skipped: {dropped}")
    if stats:
        m = np.mean(stats, axis=0)
        names = STATS_NAMES if len(m) == len(STATS_NAMES) else [f"field {i}" for i in range(len(m))]
        print("firmware stats (mean; times in µs):  " + ",  ".join(f"{k} {v:.0f}" for k, v in zip(names, m)))
    if cli is not None:  # does the command port still answer while running, port kept open?
        reply = cli_send(cli, "queryDemoStatus", wait=2.0)
        print("command port while running:", repr(reply[-120:]) if reply else "SILENT")


def run_window(args, layout, feed, cli=None):
    import pyqtgraph as pg
    import pyqtgraph.opengl as gl
    from PyQt6 import QtCore, QtGui, QtWidgets

    def cmap(name):
        try:
            return pg.colormap.get(name)
        except Exception:
            return pg.colormap.get(name, source="matplotlib")

    app = pg.mkQApp("radar-lab 3D")
    win = QtWidgets.QWidget()
    win.setWindowTitle("radar-lab 3D — " + ("simulated room" if args.sim else args.data_port))
    win.resize(1500, 850)
    row = QtWidgets.QHBoxLayout(win)

    view = gl.GLViewWidget()
    view.setBackgroundColor((12, 12, 16))
    row.addWidget(view, 3)
    side = QtWidgets.QVBoxLayout()
    row.addLayout(side, 1)

    rd_plot = pg.PlotWidget(title="Range vs speed (still things on 0)")
    rd_plot.setLabel("bottom", "speed", "m/s")
    rd_plot.setLabel("left", "range", "m")
    rd_img = pg.ImageItem()
    rd_img.setColorMap(cmap("viridis"))
    rd_plot.addItem(rd_img)
    side.addWidget(rd_plot, 3)
    info = QtWidgets.QLabel()
    info.setStyleSheet("font-family: Menlo, monospace; font-size: 12px;")
    info.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
    side.addWidget(info, 2)

    floor_z = -args.radar_height
    grid = gl.GLGridItem()
    grid.setSize(8, 8)
    grid.setSpacing(0.5, 0.5)
    grid.translate(0, 2, floor_z - 0.01)
    view.addItem(grid)
    radar = gl.GLBoxItem(size=QtGui.QVector3D(0.16, 0.05, 0.1), color=(80, 200, 255, 255))
    radar.translate(-0.08, -0.05, -0.05)
    view.addItem(radar)
    floor = gl.GLMeshItem(smooth=True, drawEdges=False, computeNormals=False, glOptions="opaque")
    floor.setVisible(False)  # until the first heatmap arrives
    view.addItem(floor)
    # "additive": glow, no depth test, so points inside the floor relief stay visible
    stems = gl.GLLinePlotItem(mode="lines", width=1.5, antialias=True)
    stems.setGLOptions("additive")
    view.addItem(stems)
    dots = gl.GLScatterPlotItem(pos=np.zeros((1, 3)), size=18, pxMode=True)
    dots.setGLOptions("additive")
    view.addItem(dots)

    st = dict(height=True, rotate=False, flip=args.flip, trails=True,
              disp=None, lo=None, hi=None, rd=None, faces=None, xy=None, mesh=None,
              trail=collections.deque(), frame_no=None, n_pts=0, stats=None,
              ticks=collections.deque(maxlen=120), last=time.perf_counter())
    inferno = cmap("inferno")

    def build_grid(n_range, n_ang):
        r = np.arange(n_range) * args.range_res
        th = np.radians(maps.angles_deg(n_ang))
        R, T = np.meshgrid(r, th, indexing="ij")
        st["xy"] = np.stack([R * np.sin(T), R * np.cos(T)], -1).reshape(-1, 2)
        idx = np.arange(n_range * n_ang).reshape(n_range, n_ang)
        a, b = idx[:-1, :-1].ravel(), idx[1:, :-1].ravel()
        c, d = idx[1:, 1:].ravel(), idx[:-1, 1:].ravel()
        st["faces"] = np.concatenate([np.stack([a, b, c], 1), np.stack([a, c, d], 1)])
        st["mesh"] = None  # rebuilt with the new grid on the next tick
        r_max = r[-1]
        view.opts["center"] = pg.Vector(0, r_max * 0.45, floor_z * 0.6)
        view.setCameraPosition(distance=r_max * 1.9, elevation=32, azimuth=-90)

    def take_frame():
        f = feed.take()
        if f is None:
            return
        st["frame_no"] = f.number
        static = f.tlvs.get(AZIMUTH_STATIC_HEATMAP)
        rd = f.tlvs.get(RANGE_DOPPLER_HEATMAP)
        n_range, n_virt, _ = heatmap_shape(f, args, layout)
        if static:
            index = cols = None
            if layout is not None and args.use_geometry:
                cols = layout.az_cols
                index = layout.az_index if n_virt == layout.n_virt else list(range(n_virt))
            db = maps.to_db(maps.range_azimuth(static, n_virt, None, args.angle_bins,
                                               False, index, cols))
            if st["xy"] is None or st["xy"].shape[0] != db.size:
                build_grid(*db.shape)
                st["disp"] = db.copy()
            st["target"] = db
        if rd:
            st["rd_target"] = maps.range_doppler(rd, n_range)
            if st["rd"] is None or st["rd"].shape != st["rd_target"].shape:
                st["rd"] = st["rd_target"].copy()
                st["rd_rect"] = None
        if DETECTED_POINTS in f.tlvs:
            pts = parse_points(f.tlvs[DETECTED_POINTS])
            st["n_pts"] = len(pts)
            st["trail"].append((time.perf_counter(), pts))
        if STATS in f.tlvs:
            st["stats"] = parse_stats(f.tlvs[STATS])

    def tick():
        now = time.perf_counter()
        dt = now - st["last"]
        st["last"] = now
        st["ticks"].append(now)
        take_frame()
        glide = 1 - np.exp(-dt / args.smooth_s)  # move this far toward the newest radar frame

        if st.get("target") is not None:
            st["disp"] += glide * (st["target"] - st["disp"])
            d = st["disp"]
            hi_t = d.max()
            lo_t = max(np.percentile(d, 50), hi_t - 40)
            st["hi"] = hi_t if st["hi"] is None else st["hi"] + glide * (hi_t - st["hi"])
            st["lo"] = lo_t if st["lo"] is None else st["lo"] + glide * (lo_t - st["lo"])
            norm = np.clip((d - st["lo"]) / max(st["hi"] - st["lo"], 1e-6), 0, 1).ravel()
            xy = st["xy"] * ([-1, 1] if st["flip"] else [1, 1])
            z = floor_z + (norm ** 1.5 * args.relief if st["height"] else 0)
            verts = np.column_stack([xy, np.broadcast_to(z, norm.shape)]).astype(np.float32)
            colors = inferno.map(norm, mode="float").astype(np.float32)
            if st["mesh"] is None:  # build once, then only move vertices and recolour
                st["mesh"] = gl.MeshData(vertexes=verts, faces=st["faces"], vertexColors=colors)
                floor.setMeshData(meshdata=st["mesh"])
                floor.setVisible(True)
            else:
                st["mesh"].setVertexes(verts)
                st["mesh"].setVertexColors(colors)
                floor.meshDataChanged()

        if st.get("rd_target") is not None:
            st["rd"] += glide * (st["rd_target"] - st["rd"])
            rd_img.setImage(st["rd"].T, autoLevels=False,
                            levels=(float(st["rd"].min()), float(st["rd"].max())))
            if st.get("rd_rect") is None:  # axes in m/s and m (only works once an image is set)
                half = st["rd"].shape[1] // 2
                st["rd_rect"] = QtCore.QRectF((-half - 0.5) * args.vel_res, 0,
                                              st["rd"].shape[1] * args.vel_res,
                                              st["rd"].shape[0] * args.range_res)
                rd_img.setRect(st["rd_rect"])

        while st["trail"] and now - st["trail"][0][0] > (args.trail_s if st["trails"] else 0.12):
            st["trail"].popleft()
        if st["trail"]:
            pos, col = [], []
            life = args.trail_s if st["trails"] else 0.12
            for t, pts in st["trail"]:
                if not len(pts):
                    continue
                alpha = max(0.08, 1 - (now - t) / life)
                p = pts[:, :3].copy()
                p[:, 2] = np.clip(p[:, 2], floor_z, args.z_max)  # elevation estimates can be wild
                if st["flip"]:
                    p[:, 0] *= -1
                moving = np.clip(np.abs(pts[:, 3]) / max(args.vel_res * 4, 1e-6), 0, 1)[:, None]
                still_c, move_c = np.array([0.3, 0.9, 1.0]), np.array([1.0, 0.4, 0.1])
                c = still_c * (1 - moving) + move_c * moving
                pos.append(p)
                col.append(np.column_stack([c, np.full(len(p), alpha)]))
            if pos:
                pos, col = np.concatenate(pos), np.concatenate(col)
                dots.setData(pos=pos, color=col)
                base = pos.copy()
                base[:, 2] = floor_z
                seg = np.empty((2 * len(pos), 3))  # a stem from the floor up to each point
                seg[0::2], seg[1::2] = base, pos
                seg_col = np.repeat(col * [1, 1, 1, 0.45], 2, axis=0)
                stems.setData(pos=seg, color=seg_col)
                stems.setVisible(True)
        else:
            dots.setData(pos=np.zeros((0, 3)))
            stems.setVisible(False)

        if st["rotate"]:
            view.orbit(12 * dt, 0)
        view.update()  # ask for the next frame; frameSwapped brings us back here

        if len(st["ticks"]) > 1 and int(now * 4) != int((now - dt) * 4):  # text 4x a second
            t = st["ticks"]
            disp_fps = (len(t) - 1) / (t[-1] - t[0])
            lines = [f"radar   {feed.fps():5.1f} fps   (new data)",
                     f"screen  {disp_fps:5.1f} fps   (redraw)",
                     f"frame   {st['frame_no']}",
                     f"points  {st['n_pts']} this frame",
                     "",
                     "H relief  R rotate  F flip  T trails",
                     f"relief {'on' if st['height'] else 'off'} · trails {'on' if st['trails'] else 'off'}"
                     f" · {'mirrored' if st['flip'] else 'not mirrored'}"]
            if st["stats"] is not None and len(st["stats"]) == len(STATS_NAMES):
                s = st["stats"]
                lines += ["", "firmware timing (µs):",
                          f"  processing {s[0]:.0f}   UART {s[1]:.0f}",
                          f"  frame margin {s[2]:.0f}"]
            info.setText("\n".join(lines))

    def toggle(key):
        st[key] = not st[key]

    for key, name in (("H", "height"), ("R", "rotate"), ("F", "flip"), ("T", "trails")):
        sc = QtGui.QShortcut(QtGui.QKeySequence(key), win)
        sc.activated.connect(lambda name=name: toggle(name))

    # Redraw in step with the screen: each finished frame triggers the next (vsync caps it
    # at the display's refresh rate, 60 Hz on most Macs). A timer drifts against vsync.
    view.frameSwapped.connect(tick)
    QtCore.QTimer.singleShot(0, view.update)

    if args.save:
        def save():
            win.grab().save(args.save)
            print(f"Saved {args.save}  (radar {feed.fps():.1f} fps)")
            app.quit()
        QtCore.QTimer.singleShot(int(args.save_after * 1000), save)

    if cli is not None and not args.leave_running:
        app.aboutToQuit.connect(lambda: stop_radar(cli))
    win.show()
    app.exec()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sim", action="store_true", help="use the fake room instead of a radar")
    p.add_argument("--sim-fps", type=float, default=30, help="sim only: radar frames per second")
    p.add_argument("--cli-port", help="radar CLI serial port (config, 115200)")
    p.add_argument("--data-port", help="radar data serial port (frames)")
    p.add_argument("--cli-baud", type=int, default=115200)
    p.add_argument("--data-baud", type=int, default=3125000, help="AWR2944PEVM demo: 3125000")
    p.add_argument("--cfg", help="send this config before viewing (also used as --layout)")
    p.add_argument("--layout", help="read antenna layout and scales from this config, without sending it")
    p.add_argument("--period-ms", type=float, help="override the config's frame period (33.333 = 30 fps)")
    p.add_argument("--frames", type=int, help="override the config's frame count (0 = forever crashes this board)")
    p.add_argument("--leave-running", action="store_true",
                   help="don't stop the radar on exit (its command port then stays silent until reset)")
    p.add_argument("--measure", type=float, metavar="SECS", help="no window: report radar fps, losses and timing")
    p.add_argument("--save", metavar="PNG", help="save a screenshot of the window, then quit")
    p.add_argument("--save-after", type=float, default=3.0, help="seconds before --save takes the picture")
    p.add_argument("--smooth-s", type=float, default=0.05, help="how quickly the picture glides to new data")
    p.add_argument("--trail-s", type=float, default=0.6, help="how long points stay visible")
    p.add_argument("--relief", type=float, default=0.35, help="height of the strongest echo on the floor map (m)")
    p.add_argument("--radar-height", type=float, default=1.0, help="radar height above the floor (m), for drawing")
    p.add_argument("--z-max", type=float, default=1.5, help="draw points at most this high above the radar (m)")
    p.add_argument("--angle-bins", type=int, default=64)
    p.add_argument("--virt-ant", type=int, default=sim.VIRT_ANT)
    p.add_argument("--range-bins", type=int, default=sim.RANGE_BINS)
    p.add_argument("--use-geometry", action="store_true", help="place antennas by antGeometryCfg (see view.py)")
    p.add_argument("--flip", action="store_true", help="start mirrored left/right")
    args = p.parse_args()

    layout = cfg.load(args.layout or args.cfg) if (args.layout or args.cfg) and not args.sim else None
    args.range_res = layout.range_res if layout else sim.RANGE_RES_M
    args.vel_res = layout.vel_res if layout else sim.VEL_RES_MS

    if not args.sim and not args.data_port:
        p.error("give --sim, or --data-port (plus --cli-port and --cfg to start the radar)")
    feed = Feed(args)
    feed.start()  # read the data port from the start, so its buffer can't overflow while we configure
    cli = None
    if args.cli_port and args.cfg:
        cli = open_serial(args.cli_port, args.cli_baud)
        if not send_cfg(cli, cfg.read_lines(args.cfg, args.period_ms, args.frames)):
            sys.exit(1)
    if args.measure:
        measure(args, feed, args.measure, cli)
        if cli is not None and not args.leave_running:
            stop_radar(cli)
    else:
        run_window(args, layout, feed, cli)


if __name__ == "__main__":
    main()
