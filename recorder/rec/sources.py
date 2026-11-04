"""Sensors as threads. Each one stamps what it receives with the session clock and writes its own file."""
import collections
import csv
import socket
import threading
import time

from . import radar_lab


class Source(threading.Thread):
    unit = "/s"

    def __init__(self, session, name):
        super().__init__(daemon=True, name=name)
        self.session = session
        self.key = name
        self.halt = threading.Event()
        self.count = 0
        self.error = None
        self._times = collections.deque(maxlen=5000)
        self._lock = threading.Lock()

    def _tick(self, t_ns, n=1):
        with self._lock:
            self.count += n
            self._times.extend([t_ns] * n)

    def rate(self):
        now = self.session.t()
        with self._lock:
            recent = [t for t in self._times if t > now - 2_000_000_000]
        return len(recent) / 2.0

    def status(self):
        if self.error:
            return f"{self.key} ERROR"
        return f"{self.key} {self.rate():.0f}{self.unit}"

    def run(self):
        try:
            self.loop()
        except Exception as e:  # keep the other sensors recording; show it on the status line
            self.error = f"{type(e).__name__}: {e}"
        finally:
            self.close()

    def close(self):
        pass

    def stop(self):
        self.halt.set()
        self.join(timeout=3)


class RadarSource(Source):
    """Saves every radar frame unchanged (radar.bin) with the host time it arrived (radar_index.csv)."""

    unit = " fps"

    def __init__(self, session, data_port=None, baud=3125000, sim_fps=None):
        super().__init__(session, "radar")
        self.sim = radar_lab.sim.Room(fps=sim_fps) if sim_fps else None
        self.sim_fps = sim_fps
        self.port = None if self.sim else radar_lab.open_serial(data_port, baud)
        self.reader = radar_lab.FrameReader()
        self.bin = open(session.dir / "radar.bin", "wb")
        self.idx_file = open(session.dir / "radar_index.csv", "w", newline="")
        self.idx = csv.writer(self.idx_file)
        self.idx.writerow(["frame_no", "t_ns", "offset", "length"])
        self.offset = 0
        self.first_no = self.last_no = None
        self.missing = 0

    def loop(self):
        next_t, last_flush = time.perf_counter(), time.perf_counter()
        while not self.halt.is_set():
            if self.sim:
                next_t += 1 / self.sim_fps
                time.sleep(max(0.0, next_t - time.perf_counter()))
                data = self.sim.frame()
            else:
                data = self.port.read(max(1, self.port.in_waiting))
            t = self.session.t()
            for f in self.reader.feed(data):
                if self.last_no is not None and f.number > self.last_no + 1:
                    self.missing += f.number - self.last_no - 1
                if self.first_no is None:
                    self.first_no = f.number
                self.last_no = f.number
                self.bin.write(f.raw)
                self.idx.writerow([f.number, t, self.offset, len(f.raw)])
                self.offset += len(f.raw)
                self._tick(t)
            if time.perf_counter() - last_flush > 0.5:  # a crash loses at most half a second
                self.bin.flush()
                self.idx_file.flush()
                last_flush = time.perf_counter()

    def close(self):
        self.bin.close()
        self.idx_file.close()
        if self.port:
            self.port.close()

    def status(self):
        s = super().status()
        return s + (f" (lost {self.missing})" if self.missing else "")

    def summary(self):
        return {"frames": self.count, "first_frame": self.first_no, "last_frame": self.last_no,
                "missing_frames": self.missing, "bytes_skipped": self.reader.dropped, "error": self.error}


def tcp_address(port):
    """'tcp://host:port' -> (host, port). Anything else (a serial port) -> None."""
    if not port.startswith("tcp://"):
        return None
    host, _, num = port[len("tcp://"):].rstrip("/").rpartition(":")
    if not host or not num.isdigit():
        raise ValueError(f"expected tcp://host:port, got {port!r}")
    return host.strip("[]"), int(num)


class SerialLineSource(Source):
    """Any line-based device (MyoWare sketch, IMU board): one row per line, as received.

    `port` is a serial port (/dev/cu...) or tcp://host:port (the IMU board's Wi-Fi link). A TCP link that
    closes or goes quiet is reconnected once a second; '# recorder: ...' rows mark the gap (comment rows,
    which the readers skip), and the device clock in the data shows how long it lasted.
    """

    TCP_IDLE_S = 6.0     # no bytes for this long = dead link (the IMU board sends 200 lines/s, a status every 5 s)
    TCP_RETRY_S = 1.0
    TCP_CONNECT_S = 2.0

    def __init__(self, session, name, port, baud=115200):
        super().__init__(session, name)
        self.url = port
        self.tcp = tcp_address(port)
        self.port = self.sock = None
        self.drops = self.fails = 0
        self.retry_at = 0.0
        if self.tcp:
            try:  # fail here, before the recording starts, if the board can't be reached
                self._resolve()
                self._connect()
            except OSError as e:
                raise OSError(f"can't reach {port} ({e}). Is the board on, and on the same Wi-Fi as this Mac?") from e
        else:
            import serial
            self.port = serial.Serial(port, baud, timeout=0.1)
            # macOS (CP2102 IMU board, 2026-11-04) replays stale bytes for a few ms after opening: one old
            # line ~50 times, the last copy spliced onto a new one. Drop everything that arrived before now.
            time.sleep(0.05)
            self.port.reset_input_buffer()
        self.file = open(session.dir / f"{name}.csv", "w", newline="")
        self.out = csv.writer(self.file)
        self.out.writerow(["t_ns", "line"])
        self.buf = b""

    def loop(self):
        last_flush = time.perf_counter()
        while not self.halt.is_set():
            data = self._read_tcp() if self.tcp else self.port.read(max(1, self.port.in_waiting))
            if data:
                t = self.session.t()
                self.buf += data
                *lines, self.buf = self.buf.split(b"\n")
                for ln in lines:
                    self.out.writerow([t, ln.decode("ascii", errors="replace").strip()])
                if lines:
                    self._tick(t, len(lines))
            if time.perf_counter() - last_flush > 0.5:
                self.file.flush()
                last_flush = time.perf_counter()

    # --- TCP link -------------------------------------------------------------------------------------
    def _resolve(self):
        """Look the name up; reconnects reuse the address. IPv4 first: for a .local name macOS otherwise
        waits 5 s for an IPv6 answer the board never sends (measured 2026-11-05: 5 ms vs 5005 ms)."""
        try:
            infos = socket.getaddrinfo(*self.tcp, family=socket.AF_INET, type=socket.SOCK_STREAM)
        except socket.gaierror:
            infos = socket.getaddrinfo(*self.tcp, type=socket.SOCK_STREAM)
        self.addr = infos[0]

    def _connect(self):
        family, kind, proto, _, sockaddr = self.addr
        s = socket.socket(family, kind, proto)
        try:
            s.settimeout(self.TCP_CONNECT_S)
            s.connect(sockaddr)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.settimeout(0.1)
        except OSError:
            s.close()
            raise
        self.sock = s
        self.last_rx = time.perf_counter()

    def _note(self, text):
        self.out.writerow([self.session.t(), f"# recorder: {text}"])

    def _lost(self, reason):
        self.sock.close()
        self.sock = None
        self.buf = b""  # half a line from before the drop must not join the first line after it
        self.drops += 1
        self.retry_at = time.perf_counter() + self.TCP_RETRY_S
        self._note(f"link lost ({reason})")

    def _read_tcp(self):
        now = time.perf_counter()
        if self.sock is None:
            if now < self.retry_at:
                time.sleep(min(0.1, self.retry_at - now))
                return b""
            try:
                if self.fails and self.fails % 5 == 0:
                    self._resolve()  # the board may have a new address after its Wi-Fi came back
                self._connect()
            except OSError:
                self.fails += 1
                self.retry_at = time.perf_counter() + self.TCP_RETRY_S
                return b""
            self.fails = 0
            self._note("link back")
            return b""
        try:
            data = self.sock.recv(65536)
        except socket.timeout:
            if now - self.last_rx > self.TCP_IDLE_S:
                self._lost(f"no data for {self.TCP_IDLE_S:.0f} s")
            return b""
        except OSError as e:
            self._lost(type(e).__name__)
            return b""
        if not data:
            self._lost("closed by the board")
            return b""
        self.last_rx = time.perf_counter()
        return data

    def status(self):
        if self.tcp and self.sock is None and not self.error:
            return f"{self.key} RECONNECTING"
        return super().status()

    def close(self):
        self.file.close()
        if self.port:
            self.port.close()
        if self.sock:
            self.sock.close()

    def summary(self):
        s = {"lines": self.count, "error": self.error}
        if self.tcp:
            s["link_drops"] = self.drops
        return s
