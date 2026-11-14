"""The radar follows the arm: elbow curls counted from the radar alone, no learning, no wearable.

1. Person range: the range bin whose Doppler velocity repeats at curl pace (0.25-1 Hz) with the most moving power,
   0.3-3 m. Radar only; the IMU is never used to find it.
2. Radial velocity at that range: power-weighted Doppler centroid over that bin and its two neighbours, zero-speed
   bins (centre +-1) left out.
3. Arm position proxy: the velocity integrated with a leak (1.5 s), scaled so a session's typical swing is 100 units,
   with its sign chosen so the arm's still moments sit low (rest = arm down).
4. Reps: reps.find_reps on that proxy, the same valley -> peak -> valley rule used on the IMU angle.

Doppler sees speed along the line to the radar, not the angle, so the proxy has no unit and can't be read in degrees.
Its sign (which turning point is the top of the curl) is not reliable: the scores accept either turning point.
The IMU is only the answer key (score_reps).
"""
from dataclasses import dataclass

import numpy as np

from . import reps as RP

R_MIN_M, R_MAX_M = 0.3, 3.0
CURL_BAND_HZ = (0.25, 1.0)
LEAK_S = 1.5
SMOOTH_FRAMES = 5
MIN_SWING = 35.0           # on the 0-100 proxy scale
MATCH_S = 0.25             # a radar rep counts as found when it is this close to an IMU turning point


@dataclass
class ArmTrack:
    range_bin: int
    range_m: float
    velocity: np.ndarray       # [N] m/s along the line to the radar (0 where the frame is missing)
    proxy: np.ndarray          # [N] arm position proxy, ~0-100
    reps: list                 # reps.Rep, rom in proxy units (not degrees)


def _smooth(x, n):
    if n <= 1:
        return x
    return np.convolve(np.pad(x, (n // 2, n - 1 - n // 2), mode="edge"), np.ones(n) / n, mode="valid")


def doppler_velocity(rd_db, valid, vel_res_ms):
    """[N, range] power-weighted radial velocity per range bin (each bin with its 2 neighbours) and [N, range] power."""
    lin = 10 ** (rd_db.astype(np.float64) / 10)
    lin[~valid] = 0
    nd = lin.shape[-1]
    mid = nd // 2
    lin[..., mid - 1:mid + 2] = 0
    q = lin + np.roll(lin, 1, axis=1) + np.roll(lin, -1, axis=1)
    vel = (np.arange(nd) - mid) * vel_res_ms
    power = q.sum(-1)
    return (q * vel).sum(-1) / (power + 1e-9), power


def _band_share(x, fps, band=CURL_BAND_HZ):
    x = x - x.mean()
    spec = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1 / fps)
    return spec[(f >= band[0]) & (f <= band[1])].sum() / (spec[(f > 0.05) & (f < 10)].sum() + 1e-12)


def person_range(V, power, valid, range_res_m, fps):
    """Range bin of the curling arm, from the radar alone."""
    lo, hi = int(R_MIN_M / range_res_m), min(int(R_MAX_M / range_res_m) + 1, V.shape[1])
    score = [_band_share(V[valid, r], fps) * np.log10(power[valid, r].mean() + 1) for r in range(lo, hi)]
    return lo + int(np.argmax(np.nan_to_num(score)))


def _leaky(x, tau_s, fps):
    a = np.exp(-1 / (tau_s * fps))
    y, acc = np.empty_like(x), 0.0
    for i, xi in enumerate(x):
        acc = a * acc + xi / fps
        y[i] = acc
    return y


def track(rec) -> ArmTrack | None:
    """ArmTrack for a RadarRecording, or None if it has too few frames (< 10 s)."""
    valid = rec.valid
    if valid.sum() < 10 * 60:
        return None
    c = rec.contract
    V, power = doppler_velocity(rec.rd_db, valid, c.vel_res_ms)
    rb = person_range(V, power, valid, c.range_res_m, c.fps)
    x = _smooth(np.where(valid, V[:, rb], 0.0), SMOOTH_FRAMES)
    d = _leaky(x, LEAK_S, c.fps)
    d = d - np.median(d[valid])
    still = valid & (np.abs(x) < np.percentile(np.abs(x[valid]), 25))
    if still.any() and d[still].mean() > np.median(d[valid]):
        d = -d
    swing = np.percentile(d[valid], 98) - np.percentile(d[valid], 5)
    proxy = d / (swing + 1e-12) * 100
    proxy[~valid] = np.nan
    return ArmTrack(rb, rb * c.range_res_m, x, proxy, RP.find_reps(rec.t_s, proxy, min_rom=MIN_SWING))


def turning_points(reps):
    """Every IMU turning point and the rep it belongs to: (times, rep index). Rep i owns its top and the bottom
    before it; the bottom after the last rep belongs to the last rep."""
    if not reps:
        return np.zeros(0), np.zeros(0, int)
    pts = [(r.peak_s, i) for i, r in enumerate(reps)]
    pts += [(reps[0].start_s, 0), (reps[-1].end_s, len(reps) - 1)]
    pts += [((a.end_s + b.start_s) / 2, i + 1) for i, (a, b) in enumerate(zip(reps, reps[1:]))]
    pts.sort()
    return np.array([p[0] for p in pts]), np.array([p[1] for p in pts], int)


def _matched(times, turns, owner, tol):
    """How many different IMU reps have a radar rep within tol of one of their turning points (each radar rep
    counts once, at its nearest turning point)."""
    found = set()
    for t in times:
        if not len(turns):
            break
        j = int(np.argmin(np.abs(turns - t)))
        if abs(turns[j] - t) <= tol:
            found.add(int(owner[j]))
    return len(found)


def score_reps(radar_reps, imu_reps, tol=MATCH_S, n_chance=200, seed=0):
    """Radar reps against the IMU's (the answer key). A radar rep is found if its top lies within tol of an IMU
    turning point (top or bottom: the radar can't tell them apart). Chance = the same radar reps moved by a random
    1-10 s (wrapping around), so the rhythm stays but the timing is lost."""
    rt = np.array([r.peak_s for r in radar_reps])
    turns, owner = turning_points(imu_reps)
    hit = _matched(rt, turns, owner, tol)
    chance = []
    if len(rt) and len(turns):
        rng = np.random.default_rng(seed)
        t0, t1 = min(rt.min(), turns.min()) - 1, max(rt.max(), turns.max()) + 1
        for _ in range(n_chance):
            s = (rt - t0 + rng.uniform(1, 10)) % (t1 - t0) + t0
            chance.append(_matched(np.sort(s), turns, owner, tol))
    rate = lambda h: h / len(imu_reps) if imu_reps else float("nan")  # noqa: E731
    gaps_r, gaps_i = np.diff(rt), np.diff([r.peak_s for r in imu_reps])
    return {"imu_reps": len(imu_reps), "radar_reps": int(len(rt)), "count_error": int(len(rt) - len(imu_reps)),
            "found": hit, "found_share": rate(hit), "extra": int(max(len(rt) - hit, 0)),
            "chance_share": rate(float(np.mean(chance))) if chance else 0.0,
            "chance_p95_share": rate(float(np.percentile(chance, 95))) if chance else 0.0,
            "median_rep_interval_s": {"radar": float(np.median(gaps_r)) if len(gaps_r) else float("nan"),
                                      "imu": float(np.median(gaps_i)) if len(gaps_i) else float("nan")}}
