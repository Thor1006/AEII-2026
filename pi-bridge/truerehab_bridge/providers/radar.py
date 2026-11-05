"""
Radar provider: the AWR2944PEVM on USB (TI mmWave demo with radar-lab's profile), shown the way the network sees it.

  live    finds the board's two USB ports (TI XDS110), starts the radar with the profile already in use
          (radar-lab/configs/fullmap_awr2x44p.cfg, the same lines the recorder sends; never flashes anything) and
          reads its frames in a thread. Stops the radar (sensorStop) when the bridge stops.
  replay  plays a recorder session's radar.bin in real time (replay = "<session folder>"), for testing without
          the radar.

Every radar frame (60 fps) goes through the model's own preprocessing (model/trnet/radar.py): angle FFT of the
static heatmap with the antennas at their real columns, the phase change since the previous frame, and the
range-Doppler map. One frame in four (15 fps) is sent to viewers as three maps: "Where things are",
"Tiny motion" and "Movement speed", cropped to the first 2.4 m.

Recording: Start/Stop in the dashboard writes every raw frame into a recorder session folder (radar.bin,
radar_index.csv, meta.json, markers.csv) under record_dir, so model/check_session.py and export_dashboard.py
read it unchanged.

Never flash firmware or change the radar configuration without asking the team.
"""
from __future__ import annotations

import asyncio
import csv
import sys
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from ..protocol import Axis, DeviceHealth, Frame, FrameStream, ManifestPart, Session
from .base import Emit, Provider

REPO = Path(__file__).resolve().parents[3]          # the project (or unpacked Pi set) root
for _sub in ("model", "radar-lab", "recorder"):
    if str(REPO / _sub) not in sys.path:
        sys.path.insert(0, str(REPO / _sub))

DEFAULT_CFG = REPO / "radar-lab" / "configs" / "fullmap_awr2x44p.cfg"
XDS110 = (0x0451, 0xBEF3)                            # TI's on-board debugger: one command port, one data port
FRAME_PERIOD_MS = 16.667                             # 60 fps, measured stable (recorder default)
STATS_HZ = 1.0

VIEWS = (
    ("range_azimuth", "Where things are", "",
     "What the network sees, part 1: everything reflecting the radar, by distance and direction. 0 = 40 dB below the strongest echo, 1 = the strongest."),
    ("phase_change", "Tiny motion", "×π rad",
     "What the network sees, part 2: how far each spot moved since the last frame, down to a fraction of a millimetre. 0 = still or too faint to tell."),
    ("range_doppler", "Movement speed", "",
     "What the network sees, part 3: how fast things move toward or away from the radar. The middle column is still."),
)


def find_xds110_ports(ports) -> tuple[str | None, str | None]:
    """(command port, data port) of the radar board from pyserial's port list, or (None, None).

    The XDS110 shows two ports per board: interface 0 = commands ("Application/User UART"), interface 3 = data
    ("Auxiliary Data Port"). Linux names them /dev/ttyACM0/1 with locations ending :1.0 and :1.3; macOS names them
    /dev/cu.usbmodem<serial>1 and ...4. Sorting by interface (or name) puts the command port first.
    """
    mine = [p for p in ports if (getattr(p, "vid", None), getattr(p, "pid", None)) == XDS110]
    if len(mine) < 2:
        return None, None
    by_board: dict[str, list] = {}
    for p in mine:
        by_board.setdefault(str(getattr(p, "serial_number", "") or ""), []).append(p)
    board = max(by_board.values(), key=len)

    def order(p) -> tuple[int, str]:
        desc = (getattr(p, "description", "") or "").lower()
        if "auxiliary" in desc or "data port" in desc:
            return (9, p.device)
        if "user uart" in desc or "application" in desc:
            return (0, p.device)
        loc = str(getattr(p, "location", "") or "")
        if ":1." in loc:
            try:
                return (int(loc.rsplit(".", 1)[1]), p.device)
            except ValueError:
                pass
        return (5, p.device)

    board.sort(key=order)
    return board[0].device, board[-1].device


class RadarProvider(Provider):
    name = "radar"

    def __init__(self, data_port: str = "auto", cli_port: str = "auto", data_baud: int = 3_125_000,
                 cfg_file: str = "", start_radar: bool = True, fps: float = 15, max_range_m: float = 2.4,
                 replay: str = "", replay_speed: float = 1.0, replay_loop: bool = True,
                 record_dir: str = "~/truerehab-sessions", **options: Any) -> None:
        super().__init__(**options)
        from trnet.contract import InputContract                     # numpy only (no PyTorch)
        from radarlab import cfg as radar_cfg
        self.data_port, self.cli_port, self.data_baud = data_port, cli_port, int(data_baud)
        self.cfg_path = Path(cfg_file).expanduser() if cfg_file else DEFAULT_CFG
        self.cfg_lines = radar_cfg.read_lines(self.cfg_path, period_ms=FRAME_PERIOD_MS, num_frames=65535)
        self.contract = InputContract.from_radar_cfg(self.cfg_lines)
        self.start_radar = bool(start_radar)
        self.fps_out = float(fps)
        self.rows = max(4, min(self.contract.range_bins, int(round(float(max_range_m) / self.contract.range_res_m))))
        self.replay = Path(replay).expanduser() if replay else None
        self.replay_speed = max(0.1, float(replay_speed))
        self.replay_loop = bool(replay_loop)
        self.record_dir = Path(record_dir).expanduser()
        c = self.contract
        span = round(self.rows * c.range_res_m, 2)
        self.y = Axis("Range", 0, span, "m")
        self.x_angle = Axis("Angle bin", -c.angle_bins // 2, c.angle_bins // 2 - 1)
        half = c.doppler_bins // 2
        self.x_speed = Axis("Radial speed", round(-half * c.vel_res_ms, 2), round((half - 1) * c.vel_res_ms, 2), "m/s")
        # state shared with the reader thread
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._state: DeviceHealth = DeviceHealth("missing", self._label(), "Starting…")
        self._prev_z = self._prev_mag = None
        self._prev_no = None
        self._ref_samples: list[tuple[float, float]] = []
        self._refs: tuple[float, float] | None = None
        self._frames = self._missing = 0
        self._rate_t0, self._rate_n, self._fps_in = time.monotonic(), 0, 0.0
        self._temp: float | None = None
        self._rec: dict[str, Any] | None = None
        self._cli = None

    # ------------------------------------------------------------------ manifest / health
    def _label(self) -> str:
        return f"Radar replay ({self.replay.name})" if self.replay else "Radar (AWR2944PEVM)"

    def manifest(self) -> ManifestPart:
        frames = []
        for view, label, unit, desc in VIEWS:
            x = self.x_speed if view == "range_doppler" else self.x_angle
            frames.append(FrameStream(view, (self.rows, self.contract.angle_bins if view != "range_doppler" else self.contract.doppler_bins),
                                      self.fps_out, label=label, unit=unit or None, x=x, y=self.y, description=desc))
        return ManifestPart(frames=frames, events=["marker"])

    def health(self) -> dict[str, DeviceHealth]:
        with self._lock:
            h = self._state
            if h.state == "ok":
                parts = [f"{self._fps_in:.0f} fps"]
                if self._temp is not None:
                    parts.append(f"{self._temp:.0f} °C" + (" — HOT, stop soon" if self._temp >= 85 else ""))
                if self._missing:
                    parts.append(f"{self._missing} frames missing")
                if self._rec:
                    parts.append(f"recording {self._rec['frames']} frames")
                if self.replay:
                    parts.append("replay, not live")
                h = DeviceHealth("ok", h.label, ", ".join(parts))
            return {"radar": h}

    def _set(self, state: str, message: str) -> None:
        with self._lock:
            self._state = DeviceHealth(state, self._label(), message)

    # ------------------------------------------------------------------ run
    async def run(self, emit: Emit) -> None:
        loop = asyncio.get_running_loop()
        self._stop.clear()
        error: list[BaseException] = []

        def target() -> None:
            try:
                self._read(loop, emit)
            except BaseException as exc:  # noqa: BLE001  reported to the supervisor, which restarts us
                error.append(exc)

        thread = threading.Thread(target=target, name="radar-reader", daemon=True)
        thread.start()
        try:
            while thread.is_alive():
                await asyncio.sleep(0.25)
        finally:
            self._stop.set()
            await asyncio.to_thread(thread.join, 5)
            await asyncio.to_thread(self._shutdown_radar)
        if error:
            raise RuntimeError(str(error[0])) from error[0]

    def _read(self, loop: asyncio.AbstractEventLoop, emit: Emit) -> None:
        source = self._replay_frames() if self.replay else self._live_frames()
        for raw, frame in source:
            if self._stop.is_set():
                break
            self._handle(raw, frame, loop, emit)

    # ------------------------------------------------------------------ sources
    def _live_frames(self):
        import serial
        from radarlab.tlv import FrameReader
        cli_port, data_port = self.cli_port, self.data_port
        if "auto" in (cli_port, data_port):
            from serial.tools import list_ports
            auto_cli, auto_data = find_xds110_ports(list_ports.comports())
            cli_port = auto_cli if cli_port == "auto" else cli_port
            data_port = auto_data if data_port == "auto" else data_port
        if not data_port or (self.start_radar and not cli_port):
            self._set("missing", "Not plugged in: no TI XDS110 USB ports found. Power the radar first, then USB.")
            raise RuntimeError("radar not plugged in")
        try:
            data = serial.Serial(data_port, self.data_baud, timeout=0.05)   # open first so its buffer can't overflow
        except serial.SerialException as exc:
            self._set("error", f"Can't open the radar's data port {data_port}: is another program (the recorder, "
                               "radar-lab) using it? Only one may read the radar at a time.")
            raise RuntimeError(f"can't open {data_port}") from exc
        try:
            if self.start_radar:
                self._start(cli_port)
            self._set("ok", "starting")
            reader = FrameReader()
            last = time.monotonic()
            while not self._stop.is_set():
                chunk = data.read(65536)
                if chunk:
                    last = time.monotonic()
                    for f in reader.feed(chunk):
                        yield f.raw, f
                elif time.monotonic() - last > 3:
                    self._set("error", "No frames for 3 s. Check the cables; if it stays silent, press the radar's reset button.")
                    raise RuntimeError("radar silent")
        finally:
            data.close()

    def _start(self, cli_port: str) -> None:
        import serial
        from view import cli_send, send_cfg   # radar-lab/view.py: the same start sequence the recorder uses
        self._cli = serial.Serial(cli_port, 115200, timeout=0.05)
        for attempt in (1, 2):
            self._cli.reset_input_buffer()
            cli_send(self._cli, "", wait=0.3)       # a stray byte waiting on the port made the first line fail (2026-11-05)
            if send_cfg(self._cli, self.cfg_lines):
                return
            time.sleep(0.5)
        self._set("error", "The radar didn't accept its settings. Press its reset button (or replug its power) and wait 10 s.")
        raise RuntimeError("radar refused its settings")

    def _shutdown_radar(self) -> None:
        self._finish_recording()
        if self._cli is None:
            return
        try:
            from view import stop_radar
            stop_radar(self._cli)
        finally:
            self._cli.close()
            self._cli = None

    def _replay_frames(self):
        from radarlab.tlv import FrameReader
        from rec import session as S
        s = S.load(self.replay)
        idx = s.radar_index()
        raw = (s.dir / "radar.bin").read_bytes()
        self._set("ok", "replay")
        while not self._stop.is_set():
            t0, f0 = time.monotonic(), idx["t_s"][0]
            for t, off, n in zip(idx["t_s"], idx["offset"], idx["length"]):
                wait = t0 + (t - f0) / self.replay_speed - time.monotonic()
                if wait > 0 and self._stop.wait(wait):
                    return
                frames = FrameReader().feed(raw[off:off + n])
                if frames:
                    yield raw[off:off + n], frames[0]
            if not self.replay_loop:
                return
            self._prev_z = self._prev_no = None     # the loop jumps back in time: no phase across it

    # ------------------------------------------------------------------ per frame
    def _handle(self, raw: bytes, frame, loop: asyncio.AbstractEventLoop, emit: Emit) -> None:
        from trnet import radar as R
        c = self.contract
        if R.STATIC_HEATMAP not in frame.tlvs or R.RANGE_DOPPLER not in frame.tlvs:
            return
        now = time.monotonic()
        with self._lock:
            self._frames += 1
            if self._prev_no is not None and frame.number > self._prev_no + 1:
                self._missing += frame.number - self._prev_no - 1
            self._rate_n += 1
            if now - self._rate_t0 >= 1 / STATS_HZ:
                self._fps_in = self._rate_n / (now - self._rate_t0)
                self._rate_t0, self._rate_n = now, 0
            temp = R.temperature_c(frame.tlvs.get(R.TEMPERATURE, b""))
            if np.isfinite(temp):
                self._temp = temp
            if self._rec is not None:              # under the lock: Stop may close the files at any moment
                self._record(self._rec, raw, frame.number)
        z = R.angle_fft(R.static_iq(frame.tlvs[R.STATIC_HEATMAP], len(c.az_index)), c)
        rd = R.rd_db(frame.tlvs[R.RANGE_DOPPLER], c.range_bins)
        mag_db = 20 * np.log10(np.abs(z) + 1e-3)
        if self._refs is None:                       # the session reference: 99.5th percentile over the first 5 s
            self._ref_samples.append((float(np.percentile(mag_db, 99.5)), float(np.percentile(rd, 99.5))))
            if len(self._ref_samples) >= int(c.baseline_s * c.fps):
                self._refs = tuple(np.median(np.array(self._ref_samples), axis=0))
        ref_h, ref_d = self._refs or tuple(np.median(np.array(self._ref_samples), axis=0))
        consecutive = self._prev_no is not None and frame.number == self._prev_no + 1 and self._prev_z is not None
        phase = np.zeros_like(mag_db, dtype=np.float32)
        if consecutive:
            strong = (mag_db > ref_h - R.PHASE_GATE_DB) & (self._prev_mag > ref_h - R.PHASE_GATE_DB)
            phase = np.where(strong, np.angle(z * np.conj(self._prev_z)) / np.pi, 0).astype(np.float32)
        self._prev_z, self._prev_mag, self._prev_no = z, mag_db, frame.number
        step = max(1, int(round(c.fps / self.fps_out)))
        if frame.number % step:
            return
        t_ms = time.time() * 1000
        rows = self.rows
        maps = (
            ("range_azimuth", np.clip((mag_db - ref_h) / c.db_span + 1, 0, 1), self.x_angle, None),
            ("phase_change", phase, self.x_angle, "×π rad"),
            ("range_doppler", np.clip((rd - ref_d) / c.db_span + 1, 0, 1), self.x_speed, None),
        )
        for view, data, x, unit in maps:
            msg = Frame(view, np.ascontiguousarray(data[:rows], dtype=np.float32), t=t_ms, frame_index=int(frame.number),
                        unit=unit, x=x, y=self.y)
            loop.call_soon_threadsafe(emit, msg)

    # ------------------------------------------------------------------ recording (recorder format)
    def on_session_start(self, session: Session) -> None:
        from rec import session as S
        subject = session.user_id if session.user_id and S.SUBJECT_RE.match(session.user_id) else "KIT"
        exercise = session.exercise if session.exercise and S.EXERCISE_RE.match(session.exercise.replace(" ", "_")) else "session"
        self.record_dir.mkdir(parents=True, exist_ok=True)
        w = S.SessionWriter(self.record_dir, subject, exercise, notes=f"recorded by the Pi bridge, session {session.id}")
        c = self.contract
        w.add_source("radar", {"kind": "AWR2944PEVM mmWave demo (UART)" if not self.replay else f"replay of {self.replay.name}",
                               "port": self.data_port, "baud": self.data_baud, "range_res_m": c.range_res_m,
                               "vel_res_ms": c.vel_res_ms, "doppler_bins": c.doppler_bins, "virtual_antennas": 12,
                               "started_by_recorder": self.start_radar and not self.replay, "cfg_file": str(self.cfg_path),
                               "cfg_lines": list(self.cfg_lines)})
        rec = {"writer": w, "bin": open(w.dir / "radar.bin", "wb"), "idx": open(w.dir / "radar_index.csv", "w", newline=""),
               "offset": 0, "frames": 0, "first": None, "last": None, "missing": 0, "session": session.id}
        rec["csv"] = csv.writer(rec["idx"])
        rec["csv"].writerow(["frame_no", "t_ns", "offset", "length"])
        with self._lock:
            old, self._rec = self._rec, rec
            if old:
                self._close_rec(old)

    def _record(self, rec: dict[str, Any], raw: bytes, number: int) -> None:
        t = rec["writer"].t()
        rec["bin"].write(raw)
        rec["csv"].writerow([number, t, rec["offset"], len(raw)])
        rec["offset"] += len(raw)
        if rec["last"] is not None and number > rec["last"] + 1:
            rec["missing"] += number - rec["last"] - 1
        rec["first"] = rec["first"] if rec["first"] is not None else number
        rec["last"] = number
        rec["frames"] += 1

    def on_marker(self, label: str) -> None:
        with self._lock:
            if self._rec:
                self._rec["writer"].marker("x", label)

    def on_session_end(self, session: Session) -> None:
        self._finish_recording()

    def _finish_recording(self) -> None:
        with self._lock:
            rec, self._rec = self._rec, None
            if rec:
                self._close_rec(rec)

    @staticmethod
    def _close_rec(rec: dict[str, Any]) -> None:
        rec["bin"].close()
        rec["idx"].close()
        rec["writer"].close({"radar": {"frames": rec["frames"], "first_frame": rec["first"], "last_frame": rec["last"],
                                       "missing_frames": rec["missing"], "bytes_skipped": 0, "error": None},
                             "bridge_session": rec["session"]})


__all__ = ["RadarProvider", "find_xds110_ports"]
