"""Ground-truth signals (training and checking only; the product stays radar-only).

  sEMG  "E,<micros>,<raw>,<env>" 1 kHz  -> median frequency (MDF) in 0.5-s windows (20-450 Hz, 50 Hz mains removed)
  IMU   "I,<micros>,ax..gz"      200 Hz -> forearm angle (complementary filter) = elbow flexion proxy
  pose  pose.csv (MediaPipe)     ~30 fps -> elbow flexion, ear-shoulder gap (shrug), trunk lean (rec/pose.py angles)
Device clocks are put on the host clock with the recorder's align_device_time (lower-edge fit).
"""
import csv
from dataclasses import dataclass, field

import numpy as np

from . import paths  # noqa: F401

ACC_PER_G, GYRO_PER_DPS = 16384.0, 131.0    # the IMU sketch's own header: raw counts, 16384 per g, 131 per deg/s
MAINS_HZ = 50.0                              # Thailand


def comment_lines(session, name):
    """[(t_s, text)] of the '#' lines a serial source sent (board header, status lines)."""
    out = []
    p = session.dir / f"{name}.csv"
    if not p.exists():
        return out
    with open(p, newline="") as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            if len(row) == 2 and row[1].startswith("#"):
                out.append((int(row[0]) / 1e9, row[1]))
    return out


def line_tags(session, name, limit=None):
    """Count line types in a serial source: {"E": n, "I": n, "#": n, "other": n}."""
    counts = {"E": 0, "I": 0, "#": 0, "other": 0}
    p = session.dir / f"{name}.csv"
    if not p.exists():
        return None
    with open(p, newline="") as f:
        r = csv.reader(f)
        next(r, None)
        for k, row in enumerate(r):
            if limit and k >= limit:
                break
            line = row[1] if len(row) == 2 else ""
            tag = "#" if line.startswith("#") else line[:2]
            counts[{"E,": "E", "I,": "I", "#": "#"}.get(tag, "other")] += 1
    return counts


def _gaps(t_s, fs):
    """Index i where a gap starts between sample i and i+1 (more than 1.5 sample periods)."""
    return np.flatnonzero(np.diff(t_s) > 1.5 / fs)


# ---------------------------------------------------------------- sEMG
@dataclass
class Emg:
    t_s: np.ndarray
    raw: np.ndarray
    env: np.ndarray
    t_host_s: np.ndarray
    dev_us: np.ndarray
    fs: float = 1000.0


def record_rows(session, name, tag):
    """The same rows, in the same order, as rec.session.Session.record_mode (same filters), plus the device
    microseconds: {"t_s" aligned, "t_host_s", "dev_us", "values"} or None."""
    from rec.session import align_device_time, unwrap_u32
    if name not in session.meta.get("sources", {}) or not (session.dir / f"{name}.csv").exists():
        return None
    t_host, lines = session.serial_lines(name)
    keep = [(t, ln.split(",")) for t, ln in zip(t_host, lines) if ln.startswith(tag + ",")]
    keep = [(t, p) for t, p in keep if all(x.lstrip("-").isdigit() for x in p[1:])]
    if not keep:
        return None
    width = max(len(p) for _, p in keep)
    keep = [(t, p) for t, p in keep if len(p) == width]
    keep = [kp for i, kp in enumerate(keep) if i == 0 or kp[1][1] != keep[i - 1][1][1]]
    th = np.array([t for t, _ in keep])
    dev = unwrap_u32([int(p[1]) for _, p in keep])
    vals = np.array([[int(x) for x in p[2:]] for _, p in keep], dtype=np.int64)
    return {"t_s": align_device_time(dev, th * 1e9) / 1e9, "t_host_s": th, "dev_us": dev, "values": vals}


def load_emg(session, name="emg"):
    d = record_rows(session, name, "E")
    if d is None or d["values"].shape[0] < 1000 or d["values"].shape[1] < 2:
        return None
    return Emg(d["t_s"], d["values"][:, 0].astype(float), d["values"][:, 1].astype(float), d["t_host_s"],
               d["dev_us"])


def emg_mdf(emg: Emg, win_s=0.5, hop_s=0.25, band=(20.0, 450.0)):
    """-> (t_center_s, mdf_hz, band_power) per window; windows across a dropout are skipped."""
    n, hop = int(win_s * emg.fs), int(hop_s * emg.fs)
    freqs = np.fft.rfftfreq(n, 1 / emg.fs)
    keep = (freqs >= band[0]) & (freqs <= band[1])
    for h in np.arange(MAINS_HZ, band[1] + 1, MAINS_HZ):
        keep &= np.abs(freqs - h) > 2.5
    win = np.hanning(n)
    gap_at = set(_gaps(emg.t_s, emg.fs))
    gap_idx = np.array(sorted(gap_at))
    ts, mdf, power = [], [], []
    for s in range(0, len(emg.raw) - n + 1, hop):
        if gap_idx.size and np.any((gap_idx >= s) & (gap_idx < s + n - 1)):
            continue
        seg = emg.raw[s:s + n] - emg.raw[s:s + n].mean()
        P = np.abs(np.fft.rfft(seg * win)) ** 2
        P[~keep] = 0
        c = np.cumsum(P)
        if c[-1] <= 0:
            continue
        ts.append(emg.t_s[s + n // 2])
        mdf.append(freqs[np.searchsorted(c, c[-1] / 2)])
        power.append(c[-1])
    return np.array(ts), np.array(mdf), np.array(power)


# ---------------------------------------------------------------- IMU
@dataclass
class Imu:
    t_s: np.ndarray
    acc_g: np.ndarray       # [n, 3]
    gyro_dps: np.ndarray    # [n, 3]
    t_host_s: np.ndarray
    dev_us: np.ndarray
    fs: float = 200.0


def load_imu(session, name="imu"):
    d = record_rows(session, name, "I")
    if d is None or d["values"].shape[0] < 200 or d["values"].shape[1] < 6:
        return None
    v = d["values"]
    return Imu(d["t_s"], v[:, :3] / ACC_PER_G, v[:, 3:6] / GYRO_PER_DPS, d["t_host_s"], d["dev_us"])


def forearm_flexion(imu: Imu, alpha=0.98, rest_s=2.0):
    """Elbow flexion proxy in degrees (0 = the forearm's angle in the first rest_s seconds, positive = flexed)
    and its angular speed. Rotation axis = the gyro axis that moves most."""
    ax = int(np.argmax(imu.gyro_dps.var(0)))
    o1, o2 = [(1, 2), (2, 0), (0, 1)][ax]
    acc_angle = np.degrees(np.unwrap(np.arctan2(imu.acc_g[:, o1], imu.acc_g[:, o2])))
    w = imu.gyro_dps[:, ax] - np.median(imu.gyro_dps[: max(10, int(rest_s * imu.fs)), ax])
    th = np.empty(len(w))
    th[0] = acc_angle[0]
    dt = np.diff(imu.t_s, prepend=imu.t_s[0])
    for i in range(1, len(w)):
        th[i] = alpha * (th[i - 1] + w[i] * dt[i]) + (1 - alpha) * acc_angle[i]
    rest = np.median(th[imu.t_s - imu.t_s[0] <= rest_s])
    dev = th - rest
    sign = 1.0 if abs(np.percentile(dev, 99)) >= abs(np.percentile(dev, 1)) else -1.0
    return sign * dev, sign * w


# ---------------------------------------------------------------- pose
@dataclass
class Pose:
    t_s: np.ndarray
    person: np.ndarray
    side: str                     # "l" or "r": the arm that moves most
    flexion_deg: np.ndarray       # 180 - elbow angle of that arm (NaN where no person)
    gap_m: np.ndarray             # ear-to-shoulder vertical gap on that side; a shrug makes it smaller
    trunk_lean_deg: np.ndarray
    visible: np.ndarray           # fraction of key landmarks with visibility > 0.5, per frame
    extra: dict = field(default_factory=dict)


KEY_LANDMARKS = (11, 12, 13, 14, 15, 16, 23, 24)   # shoulders, elbows, wrists, hips


def _nan_median_filter(x, k):
    if k <= 1:
        return x
    pad = k // 2
    xp = np.pad(x, pad, mode="edge")
    win = np.lib.stride_tricks.sliding_window_view(xp, k)
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return np.nanmedian(win, axis=1)


def load_pose(session, smooth=5, min_person=0.2):
    if "pose" not in session.meta.get("sources", {}) or not (session.dir / "pose.csv").exists():
        return None
    from rec.pose import angles
    p = session.pose()
    if len(p["t_s"]) < 30 or p["person"].mean() < min_person:
        return None
    a = {k: _nan_median_filter(np.asarray(v, float), smooth) for k, v in angles(p["world"]).items()}
    flex = {s: 180.0 - a[f"elbow_{s}"] for s in "lr"}
    rng = {s: np.nanpercentile(flex[s], 95) - np.nanpercentile(flex[s], 5) for s in "lr"}
    side = max(rng, key=rng.get)
    vis = np.nan_to_num((p["image"][:, list(KEY_LANDMARKS), 3] > 0.5).mean(1))
    return Pose(p["t_s"], p["person"], side, flex[side], a[f"ear_shoulder_{side}"], a["trunk_lean"], vis,
                {"flexion_other": flex["r" if side == "l" else "l"]})


def shift(obj, offset_s):
    """Copy of an Emg/Imu/Pose with its times moved by offset_s (used to apply the shrug sync)."""
    import dataclasses
    return dataclasses.replace(obj, t_s=obj.t_s + offset_s)
