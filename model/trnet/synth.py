"""Fake recorder sessions, in the exact recorder format, so the whole pipeline can be tested without sensors.

PLUMBING ONLY. A model that does well on these says nothing about real radar: the person, the fatigue, the
compensation and the "tremor" in the radar phase are all invented here.

What is real: the radar's empty-room background (real frames replayed when the recordings are on this
computer, otherwise the measured clutter + noise from calib/real_stats.json), the radar profile (64 range
bins, 8 azimuth antennas at their real columns, 16 Doppler bins, 60 fps), its frame-delivery jitter, the IMU's
noise, bias and uncalibrated |acc|, and the Wi-Fi delay/pause pattern. sEMG and pose use textbook values
("uncalibrated" in the stats file).

Protocol simulated: 5 s still -> 3 shoulder shrugs ('s' marker) -> sets of elbow flexion (space marker per rep)
with rests. Fatigue rises with every rep and recovers a little in rests; with fatigue, reps get slower and
smaller, sEMG median frequency drops, the shoulder starts to rise and the trunk to lean (per person).
"""
import csv
import dataclasses
import json
import struct
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from . import paths
from . import radar as R
from .calibrate import load_stats
from .contract import default_contract

LAM = R.WAVELENGTH_M
RADAR_Z = 1.20                       # radar height (m); the person's joints are placed relative to it
PROBLEMS = ("radar_gap", "wifi_drop", "no_emg", "no_imu", "no_pose", "no_radar", "emg_usb", "imu_saturation",
            "no_shrug", "long_rep", "name_subject", "raw_video", "emg_as_imu")


@dataclass
class Person:
    code: str
    seed: int
    distance_m: float = 1.3
    lateral_m: float = 0.0
    side: str = "r"
    rom_deg: float = 120.0
    rep_s: float = 2.4
    mdf_hz: float = 95.0
    fatigue_per_rep: float = 0.05
    recovery_per_s: float = 0.006
    shrug_cm: float = 4.0            # extra shoulder rise at full fatigue
    lean_deg: float = 16.0           # extra trunk lean at full fatigue
    tremor_mm: float = 0.25          # 10-Hz arm "tremor" amplitude at full fatigue (invented)
    reflect: float = 1.0


def make_person(code, seed):
    g = np.random.default_rng(seed)
    return Person(code, seed, distance_m=g.uniform(1.0, 1.6), lateral_m=g.uniform(-0.25, 0.25),
                  side=str(g.choice(["l", "r"])), rom_deg=g.uniform(105, 135), rep_s=g.uniform(2.0, 2.8),
                  mdf_hz=g.uniform(80, 110), fatigue_per_rep=g.uniform(0.035, 0.07),
                  recovery_per_s=g.uniform(0.003, 0.01), shrug_cm=g.uniform(2.0, 6.0),
                  lean_deg=g.uniform(8.0, 22.0), tremor_mm=g.uniform(0.1, 0.4), reflect=g.uniform(0.7, 1.3))


@dataclass
class Plan:
    still_s: float = 5.0
    shrugs: int = 3
    sets: int = 3
    reps_per_set: int = 10
    pause_s: float = 0.8
    set_rest_s: float = 20.0
    end_s: float = 3.0
    background: str = "auto"         # "real" (replay real empty-room frames), "stats", or "auto"
    problems: tuple = ()


# ---------------------------------------------------------------- the person's movement over time
@dataclass
class Timeline:
    t_end: float
    shrug_starts: list
    reps: list                       # dicts: start, end, rom, F, mdf, shrug_cm, lean_deg, tremor_mm, set
    markers: list = field(default_factory=list)


def plan_timeline(person: Person, plan: Plan, rng):
    t = plan.still_s + 0.5
    shrugs = []
    markers = []
    if "no_shrug" not in plan.problems and plan.shrugs:
        markers.append((t - 0.3, "s", "sync shrugs"))
        for _ in range(plan.shrugs):
            shrugs.append(t)
            t += 1.2
    t += 3.0
    F, reps = 0.0, []
    long_at = plan.reps_per_set // 2 if "long_rep" in plan.problems else -1
    for s in range(plan.sets):
        for k in range(plan.reps_per_set):
            dur = person.rep_s * (1 + 0.35 * F) * rng.uniform(0.95, 1.05)
            if s == 0 and k == long_at:
                dur = 3.6
            on_s = max(0.0, F - 0.35) / 0.65
            on_l = max(0.0, F - 0.45) / 0.55
            reps.append({"start": t, "end": t + dur, "set": s,
                         "rom": person.rom_deg * (1 - 0.3 * F) * rng.uniform(0.97, 1.03),
                         "F": F, "mdf": person.mdf_hz * (1 - 0.25 * F) * rng.uniform(0.98, 1.02),
                         "shrug_cm": person.shrug_cm * on_s * rng.uniform(0.8, 1.2),
                         "lean_deg": person.lean_deg * on_l * rng.uniform(0.8, 1.2),
                         "tremor_mm": person.tremor_mm * F})
            markers.append((t + rng.normal(0.1, 0.08), "space", "rep start"))
            if F > 0.7 and not any(m[1] == "t" for m in markers):
                markers.append((t + dur, "t", "feels tired"))
            t += dur + plan.pause_s * rng.uniform(0.8, 1.2)
            F = min(1.0, F + person.fatigue_per_rep)
        if s < plan.sets - 1:
            F = max(0.0, F - person.recovery_per_s * plan.set_rest_s)
            t += plan.set_rest_s
    return Timeline(t + plan.end_s, shrugs, reps, sorted(markers))


def _bump(t, start, length):
    """0 -> 1 -> 0 smoothly over [start, start+length]."""
    x = np.clip((t - start) / length, 0, 1)
    return 0.5 * (1 - np.cos(2 * np.pi * x))


def kinematics(person: Person, tl: Timeline, t):
    """Joint angles/offsets at times t: flexion (deg), shoulder rise (m), trunk lean (deg), tremor (m)."""
    t = np.asarray(t, float)
    flex = np.zeros_like(t)
    rise = np.zeros_like(t)
    lean = np.zeros_like(t)
    trem = np.zeros_like(t)
    for s0 in tl.shrug_starts:
        rise += 0.04 * _bump(t, s0, 0.6)
    for r in tl.reps:
        dur = r["end"] - r["start"]
        b = _bump(t, r["start"], dur)
        flex += r["rom"] * b
        rise += r["shrug_cm"] / 100 * b
        lean += r["lean_deg"] * b
        inside = (t >= r["start"]) & (t <= r["end"])
        trem += np.where(inside, r["tremor_mm"] / 1000 * np.sin(2 * np.pi * 10.0 * t), 0.0)
    return flex, rise, lean, trem


def joints(person: Person, flex, rise, lean, trem, t):
    """Joint positions in radar coordinates (x sideways, y away from the radar, z up), shape [n, 3] each."""
    n = len(t)
    sgn = -1.0 if person.side == "r" else 1.0           # facing the radar: the person's right is the radar's -x
    lam = np.radians(lean)
    breath = 0.003 * np.sin(2 * np.pi * 0.25 * t)       # chest moves +-3 mm
    hip = np.tile([person.lateral_m, person.distance_m + 0.05, 0.95 - RADAR_Z], (n, 1))
    up = np.stack([np.zeros(n), np.sin(lam), np.cos(lam)], 1)          # leaning back, away from the radar
    sh_c = hip + 0.50 * up
    chest = hip + 0.32 * up + np.stack([np.zeros(n), -0.12 - breath, np.zeros(n)], 1)
    head = sh_c + 0.24 * up
    sh = sh_c + np.stack([sgn * 0.19 * np.ones(n), np.zeros(n), rise], 1)
    sh_o = sh_c + np.stack([-sgn * 0.19 * np.ones(n), np.zeros(n), np.zeros(n)], 1)
    elbow = sh + np.stack([np.zeros(n), np.zeros(n), -0.30 * np.ones(n)], 1)
    phi = np.radians(flex + lean)                        # forearm angle from straight down, towards the radar
    fdir = np.stack([np.zeros(n), -np.sin(phi), -np.cos(phi)], 1)
    wrist = elbow + 0.26 * fdir + np.stack([np.zeros(n), trem, np.zeros(n)], 1)
    hand = wrist + 0.08 * fdir
    elbow_o = sh_o + np.array([0, 0, -0.30])
    wrist_o = elbow_o + np.array([0, 0, -0.26])
    ear = head + np.stack([sgn * 0.07 * np.ones(n), np.zeros(n), -0.05 * np.ones(n)], 1)
    ear_o = head + np.stack([-sgn * 0.07 * np.ones(n), np.zeros(n), -0.05 * np.ones(n)], 1)
    return {"hip": hip, "sh_c": sh_c, "chest": chest, "head": head, "sh": sh, "sh_o": sh_o, "elbow": elbow,
            "wrist": wrist, "hand": hand, "elbow_o": elbow_o, "wrist_o": wrist_o, "ear": ear, "ear_o": ear_o,
            "phi": phi}


REFLECTORS = {"chest": 2600, "head": 700, "hip": 900, "sh": 500, "sh_o": 400, "upper": 400, "fore": 650,
              "hand": 450, "elbow_o": 350, "wrist_o": 300}


def _reflector_points(J):
    upper = (J["sh"] + J["elbow"]) / 2
    fore = (J["elbow"] + J["wrist"]) / 2
    return {"chest": J["chest"], "head": J["head"], "hip": J["hip"], "sh": J["sh"], "sh_o": J["sh_o"],
            "upper": upper, "fore": fore, "hand": J["hand"], "elbow_o": J["elbow_o"], "wrist_o": J["wrist_o"]}


# ---------------------------------------------------------------- radar
class RadarBackground:
    """Empty-room antenna data and range-Doppler raw values, from real frames or from the measured stats."""

    def __init__(self, stats, mode, rng):
        self.rng = rng
        self.real = None
        if mode in ("real", "auto"):
            names = (stats.get("radar") or {}).get("sessions", [])
            src = [paths.SESSIONS / n for n in names if (paths.SESSIONS / n / "radar.bin").exists()]
            if src:
                from radarlab.tlv import FrameReader
                from rec import session as S
                s = S.load(src[0])
                idx = s.radar_index()
                raw = (s.dir / "radar.bin").read_bytes()
                fr = [FrameReader().feed(raw[o:o + n])[0] for o, n in zip(idx["offset"], idx["length"])]
                self.real = ([R.static_iq(f.tlvs[R.STATIC_HEATMAP]) for f in fr],
                             [np.frombuffer(f.tlvs[R.RANGE_DOPPLER], "<u2").astype(float).reshape(64, 16) for f in fr])
                self.mode = "real:" + src[0].name
            elif mode == "real":
                raise FileNotFoundError("real background asked for, but the empty-room recordings aren't here")
        if self.real is None:
            r = stats["radar"]
            self.mean = np.array(r["static_iq_mean_real"]) + 1j * np.array(r["static_iq_mean_imag"])
            self.U = np.array(r["static_iq_pattern_real"]) + 1j * np.array(r["static_iq_pattern_imag"])  # [64,K,8]
            self.sd = np.sqrt(np.array(r["static_iq_pattern_var"]) / 2)                               # [64,K]
            self.rho = np.array(r["static_iq_pattern_rho"])                                            # [64,K]
            self.resid = np.array(r["static_iq_resid_std"])
            self.coef = self._cgauss(self.sd.shape) * self.sd
            med = np.fft.ifftshift(np.array(r["rd_db_median"]), axes=1) / R.LOG2_Q8_TO_DB   # back to raw layout
            sd = np.fft.ifftshift(np.array(r["rd_db_std"]), axes=1) / R.LOG2_Q8_TO_DB
            self.rd_med, self.rd_sd = med, sd
            self.mode = "stats"
        self.start = int(rng.integers(0, len(self.real[0]))) if self.real else 0

    def _cgauss(self, shape):
        return self.rng.standard_normal(shape) + 1j * self.rng.standard_normal(shape)

    def frame(self, k):
        if self.real:
            n = len(self.real[0])
            m = (self.start + k) % (2 * n - 2)            # forwards then backwards: no jump at the end
            j = m if m < n else 2 * n - 2 - m
            return self.real[0][j].copy(), self.real[1][j].copy()
        self.coef = self.rho * self.coef + np.sqrt(1 - self.rho ** 2) * self.sd * self._cgauss(self.sd.shape)
        z = self.mean + np.einsum("rk,rka->ra", self.coef, self.U) + self.resid * self._cgauss(self.mean.shape)
        rd = self.rd_med + self.rd_sd * self.rng.standard_normal(self.rd_med.shape)
        return z, rd


def radar_frames(person, tl, stats, plan, rng, contract, bg):
    """Yields (frame_no, true_time_s, payload bytes)."""
    from radarlab.tlv import encode_frame
    period = stats["radar"]["frame_period_s"]
    n = int(tl.t_end / period)
    t = np.arange(n) * period
    flex, rise, lean, trem = kinematics(person, tl, t)
    J = _reflector_points(joints(person, flex, rise, lean, trem, t))
    names = list(REFLECTORS)
    P = np.stack([J[k] for k in names], 1)                   # [n, m, 3]
    amp = np.array([REFLECTORS[k] for k in names]) * person.reflect
    r = np.linalg.norm(P, axis=2)
    v = np.gradient(r, period, axis=0)                       # radial speed (m/s)
    sin_az = P[..., 0] / np.hypot(P[..., 0], P[..., 1])
    a = amp * (1.3 / r) ** 2
    res, vres = contract.range_res_m, contract.vel_res_ms
    cols = np.array(contract.az_cols)
    rbins = np.arange(contract.range_bins)
    sd = np.arange(contract.doppler_bins)
    signed = np.where(sd < contract.doppler_bins // 2, sd, sd - contract.doppler_bins)
    gap = set()
    if "radar_gap" in plan.problems:
        g0 = int(n * 0.6)
        gap = set(range(g0, g0 + 18))                       # 0.3 s of frames never arrive
    temp0 = rng.uniform(44, 46)
    for k in range(n):
        if k in gap:
            continue
        iq, rd_raw = bg.frame(k)
        kr = np.sinc(rbins[:, None] - r[k] / res) * np.exp(-((rbins[:, None] - r[k] / res) / 2.5) ** 2)   # [64, m]
        still = np.abs(np.sinc(v[k] / vres))                                   # only slow things in the static map
        phase = np.exp(-1j * 4 * np.pi * r[k] / LAM)
        steer = np.exp(1j * np.pi * cols[None, :] * sin_az[k][:, None])        # [m, 8] antennas at real columns
        iq_cols = (kr * (a[k] * still * phase)) @ steer                             # [64, 8] in column order
        z = iq.copy()
        z[:, list(contract.az_index)] += iq_cols
        kd = np.sinc(signed[:, None] - v[k] / vres)                             # [16, m]
        lin = 2 ** (rd_raw / 256) + 8 * (np.abs(kr) * a[k]) @ np.abs(kd).T          # [64, 16]
        rd_payload = np.clip(256 * np.log2(np.maximum(lin, 1)), 0, 65535).astype("<u2").tobytes()
        st = np.stack([z.imag, z.real], -1).round().clip(-32768, 32767).astype("<i2").tobytes()
        moving = np.flatnonzero(np.abs(v[k]) > vres)
        pts = [(P[k, i, 0], P[k, i, 1], P[k, i, 2], v[k, i]) for i in moving[:6]] + \
              [(P[k, 0, 0], P[k, 0, 1], P[k, 0, 2], 0.0)]
        points = b"".join(struct.pack("<ffff", *p) for p in pts)
        side = b"".join(struct.pack("<hh", 200, 50) for _ in pts)
        stats_tlv = struct.pack("<6I", 1200, 900, 14000, 0, 31, 22)
        hot = int(round(temp0 + 6 * k / n))
        temp = struct.pack("<iI10h", 0, int(t[k] * 1000), *([hot - 3, hot - 2, hot - 1, hot - 3, hot - 1, hot,
                                                              hot, hot, hot, 0]))
        yield k + 1, float(t[k]), encode_frame(k + 1, {1: points, 7: side, 4: st, 5: rd_payload, 6: stats_tlv,
                                                      9: temp})


# ---------------------------------------------------------------- sEMG
def emg_samples(person, tl, stats, rng):
    fs = stats["emg"]["fs"]
    n = int(tl.t_end * fs)
    t = np.arange(n) / fs
    amp = np.full(n, stats["emg"]["raw_rest_std"])
    mdf = np.full(n, person.mdf_hz)
    active_std = rng.uniform(*stats["emg"]["raw_active_std"])
    for r in tl.reps:
        sel = (t >= r["start"]) & (t <= r["end"])
        ph = (t[sel] - r["start"]) / (r["end"] - r["start"])
        amp[sel] += active_std * (0.3 + 0.7 * np.sin(np.pi * ph)) * (1 + 0.5 * r["F"])
        mdf[sel] = r["mdf"]
    raw = np.empty(n)
    blk = int(0.25 * fs)
    freqs = np.fft.rfftfreq(blk, 1 / fs)
    for s in range(0, n, blk):
        m = min(blk, n - s)
        fp = mdf[s] / 1.337                     # f^2 exp(-2f/fp) has its median at ~1.337 fp
        shape = (freqs / fp) * np.exp(-freqs / fp)
        x = np.fft.irfft(np.fft.rfft(rng.standard_normal(blk)) * shape, blk)[:m]
        raw[s:s + m] = x / (x.std() + 1e-9)
    raw = stats["emg"]["raw_center"] + raw * amp + 4 * np.sin(2 * np.pi * 50 * t)
    raw = np.clip(np.round(raw), 0, 4095)
    rect = np.abs(raw - stats["emg"]["raw_center"])
    env = np.clip(np.round(2 * np.convolve(rect, np.ones(50) / 50, mode="same")), 0, 4095)
    return t, raw.astype(int), env.astype(int)


# ---------------------------------------------------------------- IMU (on the moving forearm)
def imu_samples(person, tl, stats, rng):
    s = stats["imu"]
    fs = s["fs"]
    n = int(tl.t_end * fs)
    t = np.arange(n) / fs
    flex, rise, lean, trem = kinematics(person, tl, t)
    phi = np.radians(flex + lean)
    zacc = np.gradient(np.gradient(rise, t), t) / 9.81                  # shrug lifts the whole arm
    tacc = np.gradient(np.gradient(trem, t), t) / 9.81
    # sensor axes: x = elbow axis, y = along the forearm (0,-sin,-cos), z = (0,cos,-sin); reading = axes . (up + a/g)
    acc = np.stack([np.zeros(n), -np.cos(phi) * (1 + zacc) - tacc * np.sin(phi),
                    -np.sin(phi) * (1 + zacc) + tacc * np.cos(phi)], 1) * s["acc_norm_g"]
    gyro = np.stack([-np.degrees(np.gradient(phi, t)), np.zeros(n), np.zeros(n)], 1) + np.array(s["gyro_bias_dps"])
    acc += rng.standard_normal(acc.shape) * np.array(s["acc_noise_std_g"])
    gyro += rng.standard_normal(gyro.shape) * np.array(s["gyro_noise_std_dps"])
    return t, np.round(acc * s["counts_per_g"]).astype(int), np.round(gyro * s["counts_per_dps"]).astype(int)


# ---------------------------------------------------------------- pose
POSE_FROM = {0: "head", 7: "ear_l", 8: "ear_r", 11: "sh_l", 12: "sh_r", 13: "elbow_l", 14: "elbow_r",
             15: "wrist_l", 16: "wrist_r", 23: "hip_l", 24: "hip_r"}


def pose_rows(person, tl, stats, rng):
    """[(t_true_s, row values)]: 33 landmarks (image x,y,z,v + world x,y,z), MediaPipe-style coordinates."""
    p = stats["pose"]
    t = np.arange(0, tl.t_end, 1 / p["fps"])
    flex, rise, lean, trem = kinematics(person, tl, t)
    J = joints(person, flex, rise, lean, trem, t)
    mov, oth = ("r", "l") if person.side == "r" else ("l", "r")
    named = {"head": J["head"], f"ear_{mov}": J["ear"], f"ear_{oth}": J["ear_o"], f"sh_{mov}": J["sh"],
             f"sh_{oth}": J["sh_o"], f"elbow_{mov}": J["elbow"], f"elbow_{oth}": J["elbow_o"],
             f"wrist_{mov}": J["wrist"], f"wrist_{oth}": J["wrist_o"]}
    hip_c = J["hip"]
    sgn = -1.0 if person.side == "r" else 1.0
    named[f"hip_{mov}"] = hip_c + np.array([sgn * 0.12, 0, 0])
    named[f"hip_{oth}"] = hip_c - np.array([sgn * 0.12, 0, 0])
    n = len(t)
    world = np.zeros((n, 33, 3))
    vis = np.full((n, 33), 0.3)
    for k, name in POSE_FROM.items():
        q = named[name] - hip_c
        world[:, k] = np.stack([q[:, 0], -q[:, 2], q[:, 1]], 1)        # x sideways, y down, z depth
        vis[:, k] = p["visibility"]
    for k in range(33):                                                 # the rest: near the closest joint
        if k not in POSE_FROM:
            src = 0 if k < 11 else (15 if k in (17, 19, 21) else 16 if k in (18, 20, 22) else 23 if k % 2 else 24)
            world[:, k] = world[:, src] + rng.normal(0, 0.02, 3)
    world += rng.normal(0, p["jitter_m"], world.shape)
    img = np.zeros((n, 33, 4))
    depth = person.distance_m + world[..., 2]
    img[..., 0] = 0.5 + world[..., 0] / (1.2 * depth)
    img[..., 1] = 0.45 + world[..., 1] / (1.2 * depth)
    img[..., 2] = world[..., 2]
    img[..., 3] = vis
    return t, img, world


# ---------------------------------------------------------------- writing a session folder
def _u32(us):
    return np.asarray(us, np.int64) % (1 << 32)


def _write_lines(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_ns", "line"])
        w.writerows(rows)


def _monotonic(t):
    return np.maximum.accumulate(t)


def make_session(root, person: Person, plan: Plan = Plan(), seed=None, stats=None, subject=None):
    """Write one fake session folder under root; returns its path."""
    stats = stats or load_stats()
    rng = np.random.default_rng(person.seed if seed is None else seed)
    contract = default_contract()
    tl = plan_timeline(person, plan, rng)
    subject = subject or ("Alice" if "name_subject" in plan.problems else person.code)
    d = Path(root) / f"2026-01-01_{person.seed % 1000000:06d}_{subject}_elbow_flexion"
    d.mkdir(parents=True, exist_ok=False)
    sensors = [s for s in ("radar", "emg", "imu", "pose") if f"no_{s}" not in plan.problems]
    meta = {"format": "truerehab-session/1", "subject": subject, "exercise": "elbow_flexion",
            "notes": "FAKE data from trnet.synth (plumbing only)", "started": "2026-01-01T00:00:00+07:00",
            "clock": "t_ns = time.perf_counter_ns() - t0_ns (monotonic host clock)", "t0_ns": 0,
            "wall_t0_ns": 0, "software": {"git": None, "python": "fake", "platform": "trnet.synth"},
            "sources": {}, "markers_legend": {"space": "rep start", "s": "sync shrugs", "t": "feels tired",
                                              "c": "compensating", "x": "note"}}
    summary, offsets = {}, {}

    if "radar" in sensors:
        jit = np.array(stats["radar"]["delivery_jitter_ms"]["sequence"]) / 1000
        j0 = int(rng.integers(0, len(jit)))
        rows, off, count, nos = [], 0, 0, []
        with open(d / "radar.bin", "wb") as f:
            bg = RadarBackground(stats, plan.background, rng)
            for no, t_true, b in radar_frames(person, tl, stats, plan, rng, contract, bg):
                arrive = t_true + 0.004 + jit[(j0 + no) % len(jit)] - jit.min()
                f.write(b)
                rows.append([no, int(round(arrive * 1e9)), off, len(b)])
                off += len(b)
                count += 1
                nos.append(no)
        arr = _monotonic(np.array([r[1] for r in rows], float))
        with open(d / "radar_index.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["frame_no", "t_ns", "offset", "length"])
            for r, a in zip(rows, arr):
                w.writerow([r[0], int(a), r[2], r[3]])
        meta["sources"]["radar"] = {"kind": "fake (trnet.synth)", "port": "fake", "baud": 3125000,
                                    "range_res_m": contract.range_res_m, "vel_res_ms": contract.vel_res_ms,
                                    "doppler_bins": contract.doppler_bins, "virtual_antennas": 12,
                                    "started_by_recorder": True, "cfg_file": str(paths.RADAR_CFG),
                                    "cfg_lines": list(contract.cfg_lines)}
        missing = (nos[-1] - nos[0] + 1) - count
        summary["radar"] = {"frames": count, "first_frame": nos[0], "last_frame": nos[-1],
                            "missing_frames": missing, "bytes_skipped": 0, "error": None}
        offsets["radar_delivery_ms"] = round(1000 * (0.004 + float(np.median(jit - jit.min()))), 2)

    if "emg" in sensors:
        t, raw, env = emg_samples(person, tl, stats, rng)
        drift, dev0 = rng.uniform(-20e-6, 20e-6), rng.uniform(5, 60)
        dev = _u32(np.round((t + dev0) * (1 + drift) * 1e6))
        e = stats["emg"]
        batch = int(e["bluetooth_batch_ms"])
        arrive = np.empty(len(t))
        for s in range(0, len(t), batch):
            arrive[s:s + batch] = t[min(len(t) - 1, s + batch - 1)] + rng.uniform(*e["bluetooth_delay_ms"]) / 1000
        arrive = _monotonic(arrive)
        rows = [[0, "# truerehab-record v1 emg_hz=1000"]]
        tag = "I" if "emg_as_imu" in plan.problems else "E"
        if tag == "I":
            rows += [[int(a * 1e9), f"I,{u},{r},{v},16384,0,0,0"] for a, u, r, v in zip(arrive, dev, raw, env)]
        else:
            rows += [[int(a * 1e9), f"E,{u},{r},{v}"] for a, u, r, v in zip(arrive, dev, raw, env)]
        _write_lines(d / "emg.csv", rows)
        port = "/dev/cu.usbserial-0002" if "emg_usb" in plan.problems else "/dev/cu.TrueRehab-MyoWare"
        meta["sources"]["emg"] = {"port": port, "baud": 921600 if "emg_usb" in plan.problems else 115200,
                                  "format": "t_ns,line (as received)"}
        summary["emg"] = {"lines": len(rows), "error": None}

    if "imu" in sensors:
        t, acc, gyro = imu_samples(person, tl, stats, rng)
        if "imu_saturation" in plan.problems:
            sat = (t > tl.reps[1]["start"]) & (t < tl.reps[1]["start"] + 0.5)
            acc[sat] = np.where(acc[sat] >= 0, 32767, -32768)
        drift, dev0 = rng.uniform(-20e-6, 20e-6), rng.uniform(5, 60)
        dev = _u32(np.round((t + dev0) * (1 + drift) * 1e6))
        w = stats["wifi"]
        extra = np.array(w["extra_delay_ms_every_20ms"]) / 1000
        k0 = int(rng.integers(0, len(extra)))
        arrive = t + 0.0015 + extra[(k0 + np.arange(len(t)) // 4) % len(extra)]
        keep = np.ones(len(t), bool)
        lost_at = None
        if "wifi_drop" in plan.problems:
            lost_at = tl.reps[len(tl.reps) // 2]["start"]
            keep &= ~((t >= lost_at) & (t < lost_at + 1.0))
        arrive = _monotonic(arrive)
        rows = [[0, "# wifi link: tcp port 3333 at truerehab-imu.local, one client at a time"],
                [0, "# accel_cal none (send a, or hold BOOT 3 s, to calibrate)"],
                [0, "# I,micros,ax,ay,az,gx,gy,gz  (counts: 16384 per g, 131 per deg/s; raw, no bias or calibration)"]]
        last_status = 0.0
        sat_count = 0
        for i in range(len(t)):
            if lost_at is not None and abs(t[i] - lost_at) < 0.0025:
                rows.append([int(arrive[i] * 1e9), "# recorder: link lost (no data for 6 s)"])
            if not keep[i]:
                continue
            if lost_at is not None and abs(t[i] - lost_at - 1.0) < 0.0025:
                rows.append([int(arrive[i] * 1e9), "# recorder: link back"])
            if t[i] - last_status >= 5.0:
                last_status = t[i]
                rows.append([int(arrive[i] * 1e9),
                             f"# status up_s={int(t[i] + dev0)} imu=ok samples={i} rate_hz=200.0 skipped=0 "
                             f"i2c_err=0 recoveries=0 frozen=0 saturated={sat_count} i2c_hz=400000 gyro_cal=ok "
                             f"wifi=ok ip=192.168.1.85 rssi_dbm=-40 link_clients=1 link_dropped=0 link_send_fails=0"])
            if "imu_saturation" in plan.problems and abs(acc[i]).max() >= 32767:
                sat_count += 1
            a, g = acc[i], gyro[i]
            rows.append([int(arrive[i] * 1e9), f"I,{dev[i]},{a[0]},{a[1]},{a[2]},{g[0]},{g[1]},{g[2]}"])
        _write_lines(d / "imu.csv", rows)
        meta["sources"]["imu"] = {"port": "tcp://truerehab-imu.local:3333", "baud": None,
                                  "format": "t_ns,line (as received)"}
        summary["imu"] = {"lines": len(rows), "error": None, "link_drops": 1 if lost_at is not None else 0}

    if "pose" in sensors:
        p = stats["pose"]
        t, img, world = pose_rows(person, tl, stats, rng)
        lat = p["latency_ms"] / 1000 + rng.normal(0, p["latency_jitter_ms"] / 1000, len(t))
        arrive = t + lat
        for k in range(1, len(arrive)):                 # frames are read one after another: strictly increasing
            arrive[k] = max(arrive[k], arrive[k - 1] + 0.002)
        from rec.pose import HEADER
        with open(d / "pose.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(HEADER)
            for k in range(len(t)):
                w.writerow([int(arrive[k] * 1e9), k, 1] + [f"{v:.5f}" for v in img[k].ravel()]
                           + [f"{v:.5f}" for v in world[k].ravel()])
        meta["sources"]["pose"] = {"camera": 0, "model": "pose_landmarker_full.task",
                                   "raw_video": "raw_video" in plan.problems,
                                   "format": "rec/pose.py HEADER: 33 MediaPipe landmarks, image + world (m)"}
        summary["pose"] = {"frames": len(t), "with_person": len(t), "error": None}
        offsets["pose_latency_ms"] = p["latency_ms"]

    with open(d / "markers.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_ns", "key", "label"])
        for t_m, key, label in tl.markers:
            w.writerow([int(t_m * 1e9), key, label])
    summary["markers"] = len(tl.markers)
    meta.update({"ended": "2026-01-01T00:10:00+07:00", "duration_s": round(tl.t_end, 3), "summary": summary,
                 "fake": {"generator": "trnet.synth", "warning": "FAKE DATA: tests the code only",
                          "seed": person.seed, "person": asdict(person),
                          "plan": {**asdict(plan), "problems": list(plan.problems)},
                          "background": bg.mode if "radar" in sensors else None,
                          "truth": {"reps": [{k: round(v, 4) if isinstance(v, float) else v for k, v in r.items()}
                                             for r in tl.reps],
                                    "shrug_starts": [round(s, 3) for s in tl.shrug_starts],
                                    "delays": offsets}}})
    (d / "meta.json").write_text(json.dumps(meta, indent=2))
    return d


def make_dataset(root, n_people=6, plan=None, seed=0, sessions_per_person=1, stats=None):
    """Several fake people (codes F01, F02, ...), one or more sessions each. Returns the folders."""
    stats = stats or load_stats()
    plan = plan or Plan()
    out = []
    for i in range(n_people):
        person = make_person(f"F{i + 1:02d}", seed * 1000 + i)
        for k in range(sessions_per_person):
            p = dataclasses.replace(person, seed=person.seed * 10 + k)
            out.append(make_session(root, p, plan, stats=stats))
    return out
