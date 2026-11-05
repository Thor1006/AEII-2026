"""A recording session on disk: one folder, one file per sensor, every time on one host clock.

Folder layout (format "truerehab-session/1"):
  meta.json          who/what/when, sensor settings, summary
  radar.bin          radar frames exactly as received, back to back
  radar_index.csv    frame_no, t_ns, offset, length   (t_ns = host time the frame arrived)
  <name>.csv         t_ns, line                       (one serial line per row, as received)
  markers.csv        t_ns, key, label
All t_ns are nanoseconds since the session's t0 on time.perf_counter_ns (monotonic, same in every thread).
"""
import csv
import datetime
import json
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

FORMAT = "truerehab-session/1"
now_ns = time.perf_counter_ns
MARKER_KEYS = {" ": "rep start", "s": "sync shrugs", "t": "feels tired", "c": "compensating", "x": "note"}
SUBJECT_RE = re.compile(r"^[A-Za-z0-9_-]{1,12}$")
EXERCISE_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def git_commit(repo):
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=5).stdout.strip() or None
    except Exception:
        return None


class SessionWriter:
    def __init__(self, root, subject, exercise, notes=""):
        if not SUBJECT_RE.match(subject):
            raise ValueError("subject must be a short code like S01 (letters, digits, - or _), never a name")
        exercise = exercise.replace(" ", "_")
        if not EXERCISE_RE.match(exercise):
            raise ValueError("exercise must be a short label like elbow_flexion")
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        base = Path(root) / f"{stamp}_{subject}_{exercise}"
        self.dir, k = base, 2
        while True:  # two sessions in the same second (e.g. Stop then Start in the dashboard) get _2, _3, ...
            try:
                self.dir.mkdir(parents=True, exist_ok=False)
                break
            except FileExistsError:
                self.dir, k = base.with_name(f"{base.name}_{k}"), k + 1
        self.t0_ns = now_ns()
        self.meta = {
            "format": FORMAT,
            "subject": subject,
            "exercise": exercise,
            "notes": notes,
            "started": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "clock": "t_ns = time.perf_counter_ns() - t0_ns (monotonic host clock)",
            "t0_ns": self.t0_ns,
            "wall_t0_ns": time.time_ns(),
            "software": {"git": git_commit(Path(__file__).parent), "python": sys.version.split()[0],
                         "platform": platform.platform()},
            "sources": {},
            "markers_legend": {("space" if k == " " else k): v for k, v in MARKER_KEYS.items()},
        }
        self._markers_file = open(self.dir / "markers.csv", "w", newline="")
        self._markers = csv.writer(self._markers_file)
        self._markers.writerow(["t_ns", "key", "label"])
        self.n_markers = 0
        self.write_meta()

    def t(self):
        return now_ns() - self.t0_ns

    def add_source(self, name, info):
        self.meta["sources"][name] = info
        self.write_meta()

    def marker(self, key, label=None):
        label = label or MARKER_KEYS.get(key, key)
        self._markers.writerow([self.t(), "space" if key == " " else key, label])
        self._markers_file.flush()
        self.n_markers += 1
        return label

    def close(self, summary):
        self.meta["ended"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        self.meta["duration_s"] = round(self.t() / 1e9, 3)
        self.meta["summary"] = summary
        self.write_meta()
        self._markers_file.close()

    def write_meta(self):
        tmp = self.dir / "meta.json.tmp"
        tmp.write_text(json.dumps(self.meta, indent=2))
        tmp.replace(self.dir / "meta.json")  # never leave a half-written meta.json


# ---------------------------------------------------------------- reading back

def unwrap_u32(values):
    """Undo the wrap of a 32-bit microsecond counter (ESP32 micros() wraps every ~71.6 min)."""
    v = np.asarray(values, dtype=np.int64)
    jumps = np.diff(v) < -(1 << 31)
    return v + np.concatenate([[0], np.cumsum(jumps)]) * (1 << 32)


def _window_minima(x, resid, window):
    """Index of the smallest residual in each window of x (x need not be sorted)."""
    w = np.floor(x / window).astype(np.int64)
    order = np.argsort(w, kind="stable")
    ws = w[order]
    starts = np.flatnonzero(np.r_[True, ws[1:] != ws[:-1]])
    ends = np.r_[starts[1:], len(ws)]
    return np.array([order[s + np.argmin(resid[order[s:e]])] for s, e in zip(starts, ends)])


def align_device_time(dev_us, host_ns, window_s=2.0):
    """Put device timestamps on the host clock.

    A sample made at device time d reaches the host at k*d + offset + delay, with delay >= 0 and
    jittery (Bluetooth delivers in bursts; Wi-Fi sometimes pauses ~1 s and then delivers the backlog).
    The slope k (clock drift) is fitted through the least-delayed sample of each 2-s window, i.e. the
    lower edge of the arrivals, and the offset is taken from that edge. A fit through all samples gets
    tilted by delay bursts: on a real 2-min Wi-Fi recording (2026-11-05) the Wi-Fi-aligned times then
    wandered by 37 ms against the USB copy of the same samples; with the lower edge, by 0.0 ms (a constant
    4.1 ms apart). Returns host-clock nanoseconds for each sample.
    """
    d = unwrap_u32(dev_us).astype(np.float64) * 1e3  # -> ns
    h = np.asarray(host_ns, dtype=np.float64)
    if len(d) < 2:
        return h.copy()
    x = d - d[0]
    k, _ = np.polyfit(x, h, 1)  # first guess, through everything
    for _ in range(2):          # then through the lower edge (needs >= 3 windows, i.e. >= ~6 s of data)
        edge = _window_minima(x, h - k * x, window_s * 1e9)
        if len(edge) < 3:
            break
        k, _ = np.polyfit(x[edge], h[edge], 1)
    offset = np.percentile(h - k * x, 1)  # lower edge, robust to a few early arrivals
    return k * x + offset


@dataclass
class Session:
    dir: Path
    meta: dict
    markers: list = field(default_factory=list)  # (t_s, key, label)

    def radar_index(self):
        a = np.loadtxt(self.dir / "radar_index.csv", delimiter=",", skiprows=1, dtype=np.int64, ndmin=2)
        return {"frame_no": a[:, 0], "t_s": a[:, 1] / 1e9, "offset": a[:, 2], "length": a[:, 3]}

    def radar_frames(self):
        """Yield (t_s, Frame) for every saved radar frame, parsed with radar-lab's reader."""
        from .radar_lab import FrameReader
        idx = self.radar_index()
        with open(self.dir / "radar.bin", "rb") as f:
            for t, off, n in zip(idx["t_s"], idx["offset"], idx["length"]):
                f.seek(off)
                frames = FrameReader().feed(f.read(n))
                if frames:
                    yield t, frames[0]

    def serial_lines(self, name):
        """(host t_s array, list of lines) for a serial source, comment lines dropped."""
        t, lines = [], []
        with open(self.dir / f"{name}.csv", newline="") as f:
            r = csv.reader(f)
            next(r)
            for row in r:
                if len(row) == 2 and row[1] and not row[1].startswith("#"):
                    t.append(int(row[0]))
                    lines.append(row[1])
        return np.array(t, dtype=np.int64) / 1e9, lines

    def record_mode(self, name, tag):
        """Rows of the record-mode sketch ("E,us,raw,env" / "I,us,ax,...") on the host clock.

        Returns {"t_s": aligned times, "t_host_s": arrival times, "values": int array [n, k]}.
        """
        t_host, lines = self.serial_lines(name)
        keep = [(t, ln.split(",")) for t, ln in zip(t_host, lines) if ln.startswith(tag + ",")]
        keep = [(t, p) for t, p in keep if all(x.lstrip("-").isdigit() for x in p[1:])]
        if not keep:
            return {"t_s": np.zeros(0), "t_host_s": np.zeros(0), "values": np.zeros((0, 0), int)}
        width = max(len(p) for _, p in keep)
        keep = [(t, p) for t, p in keep if len(p) == width]  # drop rows cut short by a dropout
        # A row with the same device time as the row before is a repeat (macOS replays stale bytes when
        # a port opens; the last copy can be spliced onto a new line), never a new sample.
        keep = [kp for i, kp in enumerate(keep) if i == 0 or kp[1][1] != keep[i - 1][1][1]]
        th = np.array([t for t, _ in keep])
        dev = np.array([int(p[1]) for _, p in keep], dtype=np.int64)
        vals = np.array([[int(x) for x in p[2:]] for _, p in keep], dtype=np.int64)
        return {"t_s": align_device_time(dev, th * 1e9) / 1e9, "t_host_s": th, "values": vals}

    def pose(self):
        """Video pose: {"t_s", "person" (bool), "image" [n, 33, 4], "world" [n, 33, 3]}; NaN where no person."""
        n_lm = 33
        t, person, rows = [], [], []
        with open(self.dir / "pose.csv", newline="") as f:
            r = csv.reader(f)
            next(r)
            for row in r:
                t.append(int(row[0]))
                person.append(row[2] == "1")
                rows.append([float(x) for x in row[3:]] if row[2] == "1" else [np.nan] * (n_lm * 7))
        a = np.array(rows, dtype=float).reshape(-1, n_lm * 7)
        return {"t_s": np.array(t, dtype=np.int64) / 1e9, "person": np.array(person, bool),
                "image": a[:, : n_lm * 4].reshape(-1, n_lm, 4), "world": a[:, n_lm * 4:].reshape(-1, n_lm, 3)}


def load(path):
    path = Path(path)
    meta = json.loads((path / "meta.json").read_text())
    if meta.get("format") != FORMAT:
        raise ValueError(f"{path} is not a {FORMAT} session")
    markers = []
    with open(path / "markers.csv", newline="") as f:
        r = csv.reader(f)
        next(r)
        markers = [(int(t) / 1e9, k, lbl) for t, k, lbl in r]
    return Session(path, meta, markers)
