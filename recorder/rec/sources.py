"""Sensors as threads. Each one stamps what it receives with the session clock and writes its own file."""
import collections
import csv
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


class SerialLineSource(Source):
    """Any line-based serial device (MyoWare sketch, IMU board): one row per line, as received."""

    def __init__(self, session, name, port, baud=115200):
        super().__init__(session, name)
        import serial
        self.port = serial.Serial(port, baud, timeout=0.1)
        self.file = open(session.dir / f"{name}.csv", "w", newline="")
        self.out = csv.writer(self.file)
        self.out.writerow(["t_ns", "line"])
        self.buf = b""

    def loop(self):
        last_flush = time.perf_counter()
        while not self.halt.is_set():
            data = self.port.read(max(1, self.port.in_waiting))
            if not data:
                continue
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

    def close(self):
        self.file.close()
        self.port.close()

    def summary(self):
        return {"lines": self.count, "error": self.error}
