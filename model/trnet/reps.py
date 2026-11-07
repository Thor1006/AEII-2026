"""Cut a session into reps from the elbow flexion angle (pose, or the IMU if there is no pose), or, without either,
from the sEMG envelope (find_reps_emg).

A rep = valley -> peak -> valley of the flexion angle with at least 30 deg range and 0.8 s length. Its start and
end are where the angle is within 10 % of the range from its valleys, so rest between reps isn't counted.
Reps closer than 8 s belong to the same set.
"""
from dataclasses import asdict, dataclass

import numpy as np

MIN_ROM_DEG = 30.0
EMG_SWING = 0.30          # an sEMG burst rises at least 30 % of the session's envelope range above the rest around it
EMG_NOISE_K = 15.0        # ... and at least 15x the resting envelope's own noise (so no activity = no reps)
EMG_REST_FRAC = 0.30      # curls are cut apart where the envelope comes down to 30 % of the lower neighbouring peak
EMG_SMOOTH_S = 0.2
MIN_DUR_S = 0.8
MAX_DUR_S = 8.0
SET_BREAK_S = 8.0
ONSET_FRAC = 0.10


@dataclass
class Rep:
    start_s: float
    peak_s: float
    end_s: float
    rom_deg: float
    peak_speed_dps: float
    sparc: float           # smoothness (spectral arc length); closer to 0 = smoother
    set_id: int = 0
    index_in_set: int = 0

    @property
    def duration_s(self):
        return self.end_s - self.start_s

    def to_dict(self):
        return {**asdict(self), "duration_s": self.duration_s}


def zigzag(x, thr):
    """Alternating valleys (-1) and peaks (+1) with swings of at least thr: [(index, kind)]."""
    out, trend, lo, hi = [], 0, 0, 0
    for i in range(1, len(x)):
        if trend == 0:
            if x[i] > x[hi]:
                hi = i
            if x[i] < x[lo]:
                lo = i
            if x[hi] - x[lo] >= thr:
                if lo < hi:
                    out.append((lo, -1))
                    trend = +1
                else:
                    out.append((hi, +1))
                    trend = -1
        elif trend == +1:
            if x[i] > x[hi]:
                hi = i
            elif x[hi] - x[i] >= thr:
                out.append((hi, +1))
                trend, lo = -1, i
        else:
            if x[i] < x[lo]:
                lo = i
            elif x[i] - x[lo] >= thr:
                out.append((lo, -1))
                trend, hi = +1, i
    if trend == +1:
        out.append((hi, +1))
    elif trend == -1:
        out.append((lo, -1))
    return out


def sparc(speed, fs, fc=10.0, amp_th=0.05, padlevel=4):
    """Spectral arc length of a speed profile (Balasubramanian et al. 2015). Negative; nearer 0 = smoother."""
    speed = np.asarray(speed, float)
    if len(speed) < 4 or not np.any(speed):
        return np.nan
    nfft = int(2 ** (np.ceil(np.log2(len(speed))) + padlevel))
    f = np.arange(nfft) * fs / nfft
    M = np.abs(np.fft.fft(speed, nfft))
    M = M / M.max()
    sel = f <= fc
    f, M = f[sel], M[sel]
    idx = np.flatnonzero(M >= amp_th)
    if idx.size == 0:
        return np.nan
    f, M = f[idx[0]:idx[-1] + 1], M[idx[0]:idx[-1] + 1]
    if len(f) < 2:
        return np.nan
    return float(-np.sum(np.sqrt((np.diff(f) / (f[-1] - f[0])) ** 2 + np.diff(M) ** 2)))


def _smooth(x, n):
    if n <= 1:
        return x
    k = np.ones(n) / n
    return np.convolve(np.pad(x, (n // 2, n - 1 - n // 2), mode="edge"), k, mode="valid")


def find_reps(t, flexion_deg, min_rom=MIN_ROM_DEG, min_dur=MIN_DUR_S, max_dur=MAX_DUR_S):
    t = np.asarray(t, float)
    x = np.asarray(flexion_deg, float)
    ok = np.isfinite(x)
    if ok.sum() < 10:
        return []
    x = np.interp(t, t[ok], x[ok])
    fs = 1 / np.median(np.diff(t))
    xs = _smooth(x, max(1, int(round(0.15 * fs))))
    ext = zigzag(xs, min_rom)
    speed = np.abs(np.gradient(xs)) * fs       # by sample index: robust to repeated timestamps
    reps = []
    for (v1, k1), (p, k2), (v2, k3) in zip(ext, ext[1:], ext[2:]):
        if (k1, k2, k3) != (-1, +1, -1):
            continue
        rom = xs[p] - xs[v1]
        if rom < min_rom or xs[p] - xs[v2] < 0.7 * min_rom:
            continue
        up = np.flatnonzero(xs[v1:p + 1] <= xs[v1] + ONSET_FRAC * rom)
        down = np.flatnonzero(xs[p:v2 + 1] <= xs[v2] + ONSET_FRAC * (xs[p] - xs[v2]))
        i0 = v1 + (up[-1] if up.size else 0)
        i1 = p + (down[0] if down.size else v2 - p)
        dur = t[i1] - t[i0]
        if not (min_dur <= dur <= max_dur):
            continue
        reps.append(Rep(float(t[i0]), float(t[p]), float(t[i1]), float(rom), float(speed[i0:i1 + 1].max()),
                        sparc(speed[i0:i1 + 1], fs)))
    return group_sets(reps)


def find_reps_emg(t, env, swing=EMG_SWING, min_dur=MIN_DUR_S, max_dur=MAX_DUR_S):
    """Reps from the sEMG envelope, for sessions without a joint angle (no pose, no IMU): each curl is a burst of
    biceps activity. Rest -> burst -> rest, rising and falling by at least `swing` x the session's envelope range
    (95th minus 5th percentile) and by at least 15x the resting envelope's noise (min 1 count: a session without
    activity gives no reps), 0.8-8 s long. Bursts are cut apart only where the envelope comes down near rest (to 30 %
    of the lower neighbouring peak's height): a dip inside one curl stays higher. Start and end where the envelope is
    within 10 % of the burst's height from the rest on each side, peak at the envelope's peak.
    There is no angle, so rom, peak speed and smoothness are NaN: quality and compensation labels stay masked, only
    fatigue (sEMG median frequency) can be labelled. Curls without a pause between them can merge into one burst,
    and a dip in activity at the top of a curl can split one: the IMU or camera stay better for rep timing."""
    t = np.asarray(t, float)
    x = np.asarray(env, float)
    ok = np.isfinite(x)
    if ok.sum() < 10:
        return []
    x = np.interp(t, t[ok], x[ok])
    step = max(1, int(round(1 / (50 * np.median(np.diff(t))))))     # 50 values/s is plenty to find bursts
    n = len(x) // step * step
    tb, xb = t[:n].reshape(-1, step).mean(1), x[:n].reshape(-1, step).mean(1)
    if len(xb) < 10:
        return []
    fs = 1 / np.median(np.diff(tb))
    xs = _smooth(xb, max(1, int(round(EMG_SMOOTH_S * fs))))
    lo, hi = np.percentile(xs, [5, 95])
    thr = swing * (hi - lo)
    if thr <= 0:
        return []
    noise = max(1.0, float(np.std(xs[xs <= np.percentile(xs, 30)])))     # the quietest 30 %: rest
    need = max(thr, EMG_NOISE_K * noise)
    ext = zigzag(xs, thr)
    cuts = []
    for j, (i, kind) in enumerate(ext):
        peaks = [xs[ext[m][0]] for m in (j - 1, j + 1) if 0 <= m < len(ext)]
        if kind == -1 and (not peaks or xs[i] - lo <= EMG_REST_FRAC * (min(peaks) - lo)):
            cuts.append(i)
    reps = []
    for v1, v2 in zip(cuts, cuts[1:]):
        p = v1 + int(np.argmax(xs[v1:v2 + 1]))
        rise, fall = xs[p] - xs[v1], xs[p] - xs[v2]
        if rise < need or fall < max(0.7 * thr, EMG_NOISE_K * noise):
            continue
        up = np.flatnonzero(xs[v1:p + 1] <= xs[v1] + ONSET_FRAC * rise)
        down = np.flatnonzero(xs[p:v2 + 1] <= xs[v2] + ONSET_FRAC * fall)
        i0 = v1 + (up[-1] if up.size else 0)
        i1 = p + (down[0] if down.size else v2 - p)
        if not (min_dur <= tb[i1] - tb[i0] <= max_dur):
            continue
        reps.append(Rep(float(tb[i0]), float(tb[p]), float(tb[i1]), np.nan, np.nan, np.nan))
    return group_sets(reps)


def group_sets(reps, gap_s=SET_BREAK_S):
    set_id, k = 0, 0
    for i, r in enumerate(reps):
        if i and r.start_s - reps[i - 1].end_s > gap_s:
            set_id, k = set_id + 1, 0
        r.set_id, r.index_in_set = set_id, k
        k += 1
    return reps


def rest_before(reps):
    """Seconds since the previous rep ended (the first rep of the session gets 30 s)."""
    return [30.0 if i == 0 else max(0.0, r.start_s - reps[i - 1].end_s) for i, r in enumerate(reps)]


def count_marker(markers, key, start_s, end_s):
    return sum(1 for t, k, _ in markers if k == key and start_s <= t <= end_s)


def rep_frames(rep, frame_t, valid, T):
    """Radar frame indices for a rep: every frame from start to end, cropped to T around the peak if longer.
    -> (idx [T] (-1 = padding), mask [T] bool, cropped bool)."""
    inside = np.flatnonzero((frame_t >= rep.start_s) & (frame_t <= rep.end_s))
    cropped = len(inside) > T
    if cropped:
        p = int(np.argmin(np.abs(frame_t[inside] - rep.peak_s)))
        a = min(max(0, p - T // 2), len(inside) - T)
        inside = inside[a:a + T]
    idx = np.full(T, -1)
    idx[: len(inside)] = inside
    mask = idx >= 0
    mask[mask] = valid[idx[mask]]
    return idx, mask, cropped
