"""
sEMG provider: the MyoWare 2.0 sensor on its Wireless Shield running firmware/myoware_record, which sends 1000
"E,<micros>,<raw>,<env>" lines per second plus "# ..." header and status lines.

  port = "tcp://truerehab-myoware.local:3334"   its Wi-Fi link (the default): the board on its battery, worn
  port = "/dev/ttyUSB0"                         its USB port (baud 921600): bench tests only. Never on a person
                                                while USB is plugged in (SparkFun's safety warning).

Live, in the dashboard's "Reference signals" panel:
  emg_env  the sensor's envelope (its ENV output), 50 values/s: how hard the muscle works. ADC counts, 0-4095.
  emg_mdf  median frequency of the raw signal, 4 values/s from 0.5-s windows, with the model's own code
           (model/trnet/truth.py window_mdf: 20-450 Hz, the 50-Hz mains and its harmonics left out). It falls as the
           muscle tires. Sent only while the muscle works (band power at least `active_ratio` = 9x the quietest
           recent window, i.e. 3x its amplitude): at rest it would measure the noise, not the muscle.
Recording: every line as received into emg.csv (t_ns,line) of the bridge's shared session folder: the file the
recorder's --emg writes, so model/check_session.py reads it unchanged.
Health in plain words: not reachable, silent, flat signal, clipping, samples lost.
"""
from __future__ import annotations

import asyncio
import collections
import csv
import socket
import threading
import time
from typing import TYPE_CHECKING, Any

import numpy as np

from ..protocol import Aux, AuxChannel, DeviceHealth, ManifestPart
from ..repo import use_repo_code
from .base import Emit, Provider

if TYPE_CHECKING:
    from ..recording import Recording

DEVICE = "emg"
LABEL = "MyoWare sEMG"
FS = 1000                        # samples per second (the sketch's SAMPLE_US = 1000)
MDF_WIN, MDF_HOP = 500, 250      # 0.5-s windows every 0.25 s, like the model's labels
REST_CREEP = 1.002               # the quietest-window level may rise 0.2 % per window (~27 % in 30 s)
MIN_WINDOWS = 8                  # 2 s of windows before the activity gate trusts its resting level
GAP_US = 1500                    # consecutive samples further apart than this: samples were lost
IDLE_S, RETRY_S, CONNECT_S = 6.0, 1.0, 2.0   # as the recorder's Wi-Fi link (recorder/rec/sources.py)


def tcp_address(port: str) -> tuple[str, int] | None:
    """'tcp://host:port' -> (host, port); a serial port -> None (the recorder's rule)."""
    if not port.startswith("tcp://"):
        return None
    host, _, num = port[len("tcp://"):].rstrip("/").rpartition(":")
    if not host or not num.isdigit():
        raise ValueError(f"expected tcp://host:port, got {port!r}")
    return host.strip("[]"), int(num)


class LinkLost(Exception):
    """The board stopped answering. The reason is shown and noted in the recording."""


class TcpLink:
    def __init__(self, host: str, port: int) -> None:
        try:  # IPv4 first: for a .local name macOS otherwise waits 5 s for an IPv6 answer the board never sends
            infos = socket.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_STREAM)
        except socket.gaierror:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        family, kind, proto, _, addr = infos[0]
        s = socket.socket(family, kind, proto)
        try:
            s.settimeout(CONNECT_S)
            s.connect(addr)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.settimeout(0.1)
        except OSError:
            s.close()
            raise
        self.sock = s
        self.last_rx = time.monotonic()

    def read(self) -> bytes:
        try:
            data = self.sock.recv(65536)
        except socket.timeout:
            if time.monotonic() - self.last_rx > IDLE_S:
                raise LinkLost(f"no data for {IDLE_S:.0f} s") from None
            return b""
        except OSError as exc:
            raise LinkLost(type(exc).__name__) from exc
        if not data:
            raise LinkLost("closed by the board")
        self.last_rx = time.monotonic()
        return data

    def close(self) -> None:
        self.sock.close()


class SerialLink:
    def __init__(self, path: str, baud: int) -> None:
        import serial  # pyserial; only needed for the USB port
        self.ser = serial.Serial(path, baud, timeout=0.1)
        time.sleep(0.05)                    # macOS replays stale bytes for a few ms after opening (2026-11-04)
        self.ser.reset_input_buffer()
        self.last_rx = time.monotonic()

    def read(self) -> bytes:
        try:
            data = self.ser.read(max(1, self.ser.in_waiting))
        except OSError as exc:              # pyserial's SerialException is an OSError
            raise LinkLost(f"port lost: {exc}") from exc
        if data:
            self.last_rx = time.monotonic()
        elif time.monotonic() - self.last_rx > IDLE_S:
            raise LinkLost(f"no data for {IDLE_S:.0f} s")
        return data

    def close(self) -> None:
        self.ser.close()


class _Stream:
    """What one connection's processing remembers (reader thread only)."""

    def __init__(self) -> None:
        self.prev_us: int | None = None
        self.dev_ms = 0.0                                   # device time since the link opened, unwrapped
        self.env_sum, self.env_n = 0, 0
        self.ring: collections.deque[int] = collections.deque(maxlen=MDF_WIN)
        self.since = 0                                      # samples since the last median-frequency window
        self.offsets: collections.deque[tuple[float, float]] = collections.deque()  # (arrival ms, wall - device)
        self.last_t = {"emg_env": -1e18, "emg_mdf": -1e18}


class EmgProvider(Provider):
    name = "emg"
    records = True

    def __init__(self, port: str = "tcp://truerehab-myoware.local:3334", baud: int = 921600, env_hz: float = 50.0,
                 active_ratio: float = 9.0, **options: Any) -> None:
        super().__init__(**options)
        self.port = str(port)
        self.tcp = tcp_address(self.port)
        self.baud = int(baud)
        self.env_block = max(1, int(round(FS / float(env_hz))))
        self.active_ratio = float(active_ratio)
        use_repo_code()
        from trnet.truth import mdf_setup, window_mdf      # numpy only
        self._window_mdf = window_mdf
        self._setup = mdf_setup(MDF_WIN, FS)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._st = _Stream()
        self._rest: float | None = None                     # band power of the quietest recent window
        self._windows = 0
        # shared with health() and the recording hooks (under _lock)
        self._link, self._link_msg = "connecting", f"Connecting to {self._where()}…"
        self._connected_at = 0.0
        self._last_sample: float | None = None
        self._arrivals: collections.deque[tuple[float, int]] = collections.deque()
        self._recent: collections.deque[int] = collections.deque(maxlen=2 * FS)
        self._lost = 0
        self._header: list[str] = []
        self._board: dict[str, str] = {}
        self._board_first: dict[str, str] | None = None
        self._rec: dict[str, Any] | None = None

    # ------------------------------------------------------------------ manifest / health
    def manifest(self) -> ManifestPart:
        return ManifestPart(aux=[
            AuxChannel("emg_env", "sEMG envelope", "ADC", FS / self.env_block, DEVICE),
            AuxChannel("emg_mdf", "sEMG median frequency", "Hz", FS / MDF_HOP, DEVICE),
        ])

    def _where(self) -> str:
        return f"{self.tcp[0]}:{self.tcp[1]}" if self.tcp else self.port

    def health(self) -> dict[str, DeviceHealth]:
        now = time.monotonic()
        with self._lock:
            link, msg = self._link, self._link_msg
            last, since = self._last_sample, now - self._connected_at
            n = sum(k for t, k in self._arrivals if now - t <= 2.0)
            raw = np.array(self._recent, dtype=float) if len(self._recent) >= 200 else None
            lost, board, first = self._lost, dict(self._board), self._board_first or {}
            rec_s = self._rec["samples"] / FS if self._rec else None
        if link != "up":
            return {DEVICE: DeviceHealth("missing", LABEL, msg)}
        if last is None or now - last > 3:
            return {DEVICE: DeviceHealth("error", LABEL, "Connected, but no sEMG samples for 3 s. Is the board "
                                                         "running the record sketch (firmware/myoware_record)?")}
        state, parts = "ok", [f"{n / min(2.0, max(since, 0.25)):.0f} samples/s"]
        if raw is not None:
            if raw.std() < 1.0:
                state = "error"
                parts.insert(0, "Flat signal: is the sensor switched on and pressed onto the shield?")
            clip = float(np.mean((raw <= 0) | (raw >= 4095)))
            if clip > 0.01:
                parts.append(f"clipping in {clip:.0%} of samples: check the electrodes")
        if "rssi_dbm" in board:
            parts.append(f"Wi-Fi {board['rssi_dbm']} dBm")
        if lost:
            parts.append(f"{lost} samples lost")
        dropped = _int(board.get("link_dropped")) - _int(first.get("link_dropped"))
        if dropped > 0:
            parts.append(f"the board dropped {dropped} lines (Wi-Fi too slow)")
        if rec_s is not None:
            parts.append(f"recording {rec_s:.0f} s")
        return {DEVICE: DeviceHealth(state, LABEL, ", ".join(parts))}

    def _set_link(self, state: str, message: str) -> None:
        with self._lock:
            self._link, self._link_msg = state, message

    def _cant_reach(self, exc: BaseException) -> str:
        if not self.tcp:
            if isinstance(exc, FileNotFoundError) or "No such file" in str(exc):
                return f"Not plugged in ({self.port})"
            return f"Can't open {self.port}: {exc}"
        why = ("name not found" if isinstance(exc, socket.gaierror) else "refused" if isinstance(exc, ConnectionRefusedError)
               else "no answer" if isinstance(exc, TimeoutError) else type(exc).__name__)
        return (f"Not reachable at {self._where()} ({why}). Is the MyoWare switched on (battery), running the Wi-Fi "
                "sketch, and on the same Wi-Fi as this computer?")

    # ------------------------------------------------------------------ run
    async def run(self, emit: Emit) -> None:
        loop = asyncio.get_running_loop()
        self._stop.clear()
        error: list[BaseException] = []

        def send(msg: Any) -> None:
            try:
                loop.call_soon_threadsafe(emit, msg)
            except RuntimeError:            # the event loop closed while the bridge was stopping
                pass

        def target() -> None:
            try:
                self._read_forever(send)
            except BaseException as exc:  # noqa: BLE001  handed to the supervisor, which restarts us
                error.append(exc)

        thread = threading.Thread(target=target, name="emg-reader", daemon=True)
        thread.start()
        try:
            while thread.is_alive():
                await asyncio.sleep(0.25)
        finally:
            self._stop.set()
            await asyncio.to_thread(thread.join, 3)
        if error:
            raise RuntimeError(str(error[0])) from error[0]

    def _read_forever(self, emit: Emit) -> None:
        reconnect = False
        while not self._stop.is_set():
            try:
                link: TcpLink | SerialLink = TcpLink(*self.tcp) if self.tcp else SerialLink(self.port, self.baud)
            except OSError as exc:
                self._set_link("missing", self._cant_reach(exc))
                self._stop.wait(RETRY_S)
                continue
            self._st = _Stream()
            with self._lock:
                self._link, self._link_msg = "up", ""
                self._connected_at = time.monotonic()
                self._last_sample, self._board_first = None, None
                self._arrivals.clear()
            if reconnect:
                self._note("link back")
            buf = b""
            try:
                while not self._stop.is_set():
                    data = link.read()
                    if not data:
                        continue
                    arrival_ms = time.time() * 1000
                    buf += data
                    *lines, buf = buf.split(b"\n")
                    if lines:
                        self._handle_lines(lines, arrival_ms, emit)
            except LinkLost as lost:
                reconnect = True
                self._set_link("missing", f"Link lost ({lost}); reconnecting…")
                self._note(f"link lost ({lost})", drop=True)
                self._stop.wait(RETRY_S)
            finally:
                link.close()

    # ------------------------------------------------------------------ per chunk
    def _handle_lines(self, lines: list[bytes], arrival_ms: float, emit: Emit) -> None:
        """One chunk from the board: record it as received, then the live envelope and median frequency."""
        texts = [s for s in (ln.decode("ascii", "replace").strip() for ln in lines) if s]
        if not texts:
            return
        dev: list[int] = []
        raw: list[int] = []
        env: list[int] = []
        for s in texts:
            if s.startswith("E,"):
                p = s.split(",")
                if len(p) == 4 and p[1].isdigit() and p[2].isdigit() and p[3].isdigit():
                    dev.append(int(p[1]))
                    raw.append(int(p[2]))
                    env.append(int(p[3]))
            elif s.startswith("#"):
                self._comment(s)
        with self._lock:
            rec = self._rec
            if rec is not None:
                t = rec["rec"].t()
                rec["csv"].writerows([t, s] for s in texts)
                rec["lines"] += len(texts)
                rec["samples"] += len(dev)
                if time.monotonic() - rec["flushed"] > 0.5:       # a crash loses at most half a second
                    rec["file"].flush()
                    rec["flushed"] = time.monotonic()
        if dev:
            self._samples(dev, raw, env, arrival_ms, emit)

    def _comment(self, s: str) -> None:
        with self._lock:
            if s.startswith("# truerehab-record"):
                self._header = [s]
            elif s.startswith("# E,") and len(self._header) == 1:
                self._header.append(s)
            elif s.startswith("# status"):
                self._board = dict(kv.split("=", 1) for kv in s[len("# status"):].split() if "=" in kv)
                if self._board_first is None:
                    self._board_first = dict(self._board)

    def _samples(self, dev: list[int], raw: list[int], env: list[int], arrival_ms: float, emit: Emit) -> None:
        st = self._st
        lost = accepted = 0
        env_out: list[tuple[float, float]] = []
        mdf_out: list[tuple[float, float]] = []
        for us, r, e in zip(dev, raw, env):
            if st.prev_us is not None:
                d = (us - st.prev_us) & 0xFFFFFFFF          # micros() wraps every 71.6 min
                if d == 0:
                    continue                                # a repeat, not a new sample
                if d >= 1 << 31:                            # the clock went back: the board restarted
                    self._st = st = _Stream()
                else:
                    if d > GAP_US:
                        lost += round(d / 1000) - 1
                        st.ring.clear()                     # no median-frequency window across a gap
                        st.since = 0
                    st.dev_ms += d / 1000
            st.prev_us = us
            accepted += 1
            st.env_sum += e
            st.env_n += 1
            if st.env_n == self.env_block:
                env_out.append((st.dev_ms, st.env_sum / st.env_n))
                st.env_sum = st.env_n = 0
            st.ring.append(r)
            st.since += 1
            if len(st.ring) == MDF_WIN and st.since >= MDF_HOP:
                st.since = 0
                res = self._window_mdf(np.fromiter(st.ring, float, MDF_WIN), self._setup)
                if res is not None and self._active(res[1]):
                    mdf_out.append((st.dev_ms - MDF_WIN / 2, res[0]))      # stamped at the window's centre
        now = time.monotonic()
        with self._lock:
            self._arrivals.append((now, accepted))
            while self._arrivals and now - self._arrivals[0][0] > 2.0:
                self._arrivals.popleft()
            self._recent.extend(raw)
            self._lost += lost
            if accepted:
                self._last_sample = now
        if not accepted:
            return
        # Device time -> wall clock for the charts: the least-delayed arrival of the last 5 s sets the offset, so
        # Wi-Fi bursts don't bunch the points. Times only move forward.
        st.offsets.append((arrival_ms, arrival_ms - st.dev_ms))
        while arrival_ms - st.offsets[0][0] > 5000:
            st.offsets.popleft()
        offset = min(o for _, o in st.offsets)
        for key, values in (("emg_env", env_out), ("emg_mdf", mdf_out)):
            for dev_ms, v in values:
                t = max(dev_ms + offset, st.last_t[key] + 0.1)
                st.last_t[key] = t
                emit(Aux({key: round(v, 1)}, t=t))

    def _active(self, power: float) -> bool:
        """Is the muscle working in this window? Band power >= active_ratio x the quietest recent window."""
        self._rest = power if self._rest is None else min(self._rest * REST_CREEP, power)
        self._windows += 1
        if self.active_ratio <= 0:
            return True
        return self._windows >= MIN_WINDOWS and power >= self.active_ratio * self._rest

    # ------------------------------------------------------------------ recording (recorder format)
    def on_recording_start(self, rec: Recording) -> None:
        rec.add_source("emg", {"port": self.port, "baud": None if self.tcp else self.baud,
                               "format": "t_ns,line (as received)",
                               "kind": "MyoWare 2.0 + Wireless Shield (firmware/myoware_record), via the Pi bridge"})
        f = open(rec.dir / "emg.csv", "w", newline="")
        out = csv.writer(f)
        out.writerow(["t_ns", "line"])
        files = {"rec": rec, "file": f, "csv": out, "lines": 0, "samples": 0, "drops": 0, "flushed": time.monotonic()}
        with self._lock:
            t = rec.t()
            for h in self._header:                 # what the board said when the link opened
                out.writerow([t, h])
            if self._link != "up":
                out.writerow([t, f"# bridge: no link to the board when the recording started ({self._link_msg})"])
            old, self._rec = self._rec, files
        if old:
            old["file"].close()

    def _note(self, text: str, drop: bool = False) -> None:
        with self._lock:
            if self._rec is not None:
                self._rec["csv"].writerow([self._rec["rec"].t(), f"# bridge: {text}"])
                self._rec["drops"] += int(drop)

    def on_recording_end(self) -> dict[str, Any]:
        with self._lock:                            # after this the reader thread no longer touches the file
            files, self._rec = self._rec, None
        if not files:
            return {}
        files["file"].close()
        return {"emg": {"lines": files["lines"], "samples": files["samples"], "link_drops": files["drops"],
                        "error": None}}


def _int(x: Any) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


__all__ = ["EmgProvider", "tcp_address"]
