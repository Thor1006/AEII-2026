"""Record one session: radar + sEMG (+ IMU) on one clock, into recorder/data/sessions/<...>/.

  .venv/bin/python record.py --subject S01 --exercise elbow_flexion \\
      --radar-data /dev/cu.usbmodemRA29P0554 --radar-cli /dev/cu.usbmodemRA29P0551 \\
      --emg /dev/cu.TrueRehab-MyoWare

  .venv/bin/python record.py --subject TEST --exercise demo --radar-sim --duration 10   # no hardware

Start every session with 3 quick shoulder shrugs (press s), so the sensors can be lined up afterwards.
Keys while recording: space rep start · s sync shrugs · t feels tired · c compensating · x note · q stop
"""
import argparse
import select
import sys
import termios
import time
import tty
from pathlib import Path

from rec import radar_lab
from rec.session import MARKER_KEYS, SessionWriter
from rec.sources import RadarSource, SerialLineSource

HERE = Path(__file__).resolve().parent


class Keys:
    """Single key presses without Enter, when run in a real terminal."""

    def __init__(self, enabled):
        self.fd = sys.stdin.fileno() if enabled and sys.stdin.isatty() else None
        self.saved = None

    def __enter__(self):
        if self.fd is not None:
            self.saved = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self

    def __exit__(self, *exc):
        if self.saved is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)

    def read(self, timeout):
        if self.fd is None:
            time.sleep(timeout)
            return None
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        return sys.stdin.read(1) if ready else None


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--subject", required=True, help="a code like S01, never a name")
    p.add_argument("--exercise", required=True, help="e.g. elbow_flexion")
    p.add_argument("--notes", default="")
    p.add_argument("--out", default=str(HERE / "data" / "sessions"))
    p.add_argument("--duration", type=float, help="stop after this many seconds (default: press q)")
    g = p.add_argument_group("radar")
    g.add_argument("--radar-sim", action="store_true", help="simulated radar instead of the board")
    g.add_argument("--radar-data", help="data port, e.g. /dev/cu.usbmodemRA29P0554")
    g.add_argument("--radar-cli", help="command port; given = the recorder starts and stops the radar")
    g.add_argument("--radar-cfg", default=str(radar_lab.DEFAULT_CFG))
    g.add_argument("--radar-baud", type=int, default=3125000)
    g.add_argument("--period-ms", type=float, default=16.667, help="16.667 = 60 fps (measured stable)")
    g.add_argument("--frames", type=int, default=65535, help="the most the firmware accepts (~18 min at 60 fps)")
    g = p.add_argument_group("ground truth")
    g.add_argument("--emg", help="MyoWare port, e.g. /dev/cu.TrueRehab-MyoWare (Bluetooth)")
    g.add_argument("--emg-baud", type=int, default=921600, help="only matters for USB; the record sketch uses 921600")
    g.add_argument("--imu", help="IMU board port (MPU6050), if not sent through the MyoWare ESP32")
    g.add_argument("--imu-baud", type=int, default=921600)
    g.add_argument("--camera", type=int, help="video pose from this camera (find it with pose_check.py --list)")
    g.add_argument("--save-video", action="store_true", help="also keep the raw video (off by default: privacy)")
    args = p.parse_args()

    if not (args.radar_sim or args.radar_data or args.emg or args.imu or args.camera is not None):
        p.error("nothing to record: give --radar-data or --radar-sim, and/or --emg / --imu / --camera")

    session = SessionWriter(args.out, args.subject, args.exercise, args.notes)
    sources, cli = [], None
    try:
        if args.radar_sim or args.radar_data:
            radar = RadarSource(session, args.radar_data, args.radar_baud, sim_fps=60 if args.radar_sim else None)
            layout = radar_lab.cfg.load(args.radar_cfg)
            info = {"kind": "sim" if args.radar_sim else "AWR2944PEVM mmWave demo (UART)",
                    "port": args.radar_data, "baud": args.radar_baud,
                    "range_res_m": layout.range_res, "vel_res_ms": layout.vel_res,
                    "doppler_bins": layout.doppler_bins, "virtual_antennas": layout.n_virt,
                    "started_by_recorder": bool(args.radar_cli)}
            radar.start()  # read the data port before the radar starts, so its buffer can't overflow
            sources.append(radar)
            if args.radar_cli and not args.radar_sim:
                lines = radar_lab.cfg.read_lines(args.radar_cfg, args.period_ms, args.frames)
                info["cfg_file"] = str(args.radar_cfg)
                info["cfg_lines"] = lines
                cli = radar_lab.open_serial(args.radar_cli, 115200)
                print("Starting the radar...")
                if not radar_lab.send_cfg(cli, lines):
                    raise SystemExit("Radar didn't start (see above). Nothing was lost; delete the empty session folder.")
            session.add_source("radar", info)
        for name, port, baud in (("emg", args.emg, args.emg_baud), ("imu", args.imu, args.imu_baud)):
            if port:
                src = SerialLineSource(session, name, port, baud)
                session.add_source(name, {"port": port, "baud": baud, "format": "t_ns,line (as received)"})
                src.start()
                sources.append(src)
        if args.camera is not None:
            from rec.pose import MODEL, PoseSource  # needs mediapipe; only loaded when asked for
            pose = PoseSource(session, args.camera, save_video=args.save_video)
            session.add_source("pose", {"camera": args.camera, "model": MODEL.name, "raw_video": args.save_video,
                                        "format": "rec/pose.py HEADER: 33 MediaPipe landmarks, image + world (m)"})
            pose.start()
            sources.append(pose)

        print(f"\nRecording to {session.dir}")
        print("Start with 3 quick shoulder shrugs and press s. Keys: space rep · t tired · c compensating · x note · q stop\n")
        t_end = time.time() + args.duration if args.duration else None
        last_marker = ""
        with Keys(enabled=True) as keys:
            while t_end is None or time.time() < t_end:
                key = keys.read(0.25)
                if key == "q":
                    break
                if key in MARKER_KEYS:
                    last_marker = f" | marked: {session.marker(key)}"
                elapsed = session.t() / 1e9
                line = f"{int(elapsed // 60):02d}:{elapsed % 60:04.1f} | " + " | ".join(s.status() for s in sources)
                sys.stdout.write("\r" + line + f" | markers {session.n_markers}{last_marker}   ")
                sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        print()
        if cli is not None:  # stop the radar BEFORE letting go of its command port (see radar-lab README)
            ok, reply = radar_lab.stop_radar(cli)
            print("Radar stopped." if ok else f"Radar did NOT stop ({reply or 'no reply'}): press its reset button before the next session.")
            cli.close()
        for s in sources:
            s.stop()
        summary = {s.key: s.summary() for s in sources}
        summary["markers"] = session.n_markers
        session.close(summary)
        print(f"Saved {session.dir}")
        for name, s in summary.items():
            print(f"  {name}: {s}")


if __name__ == "__main__":
    main()
