"""Shrug sync: each sensor's leftover time offset against the radar, from the 3 shoulder shrugs at the start.

Every sensor is turned into a "how fast is it moving" signal of the same kind (a speed, not a position or an
acceleration) and smoothed the same way (0.2 s, symmetric, so nothing is shifted); then each is slid against the
radar's (+-0.3 s, 5-ms steps, refined between steps) to find where they match best.
  radar  mean |phase change| in 0.3-2.5 m (phase change per frame is proportional to radial speed)
  pose   speed of the shoulder rise (ear-shoulder gap)
  IMU    speed from the high-passed acceleration (a shrug lifts the whole arm; the forearm hardly turns) The radar is the reference because the network sees radar time.
  corrected sensor time = sensor time + offset
Applied to pose and IMU. For sEMG it is reported only: muscle activity starts ~50 ms before movement
(electromechanical delay), so a shrug offset there is physiology, not a clock error; its device clock is used.
"""
import numpy as np

from . import radar as R

GRID_HZ = 200.0
SMOOTH_S = 0.2
MAX_LAG_S = 0.3
WARN_MS = 17.0          # one radar frame
MIN_CORR = 0.3


def _movavg(x, n):
    """Centred moving average (odd length, so nothing is shifted in time)."""
    n = max(1, int(n)) | 1
    if n == 1:
        return x
    k = np.ones(n) / n
    return np.convolve(np.pad(x, (n // 2, n - 1 - n // 2), mode="edge"), k, mode="valid")


def _fill(x):
    x = np.asarray(x, float)
    ok = np.isfinite(x)
    if not ok.any():
        return np.zeros_like(x)
    return np.interp(np.arange(len(x)), np.flatnonzero(ok), x[ok])


def radar_activity(rec, r_min_m=0.3, r_max_m=2.5):
    """Per radar frame: mean |phase change| over trusted cells in front (motion energy if phase is off)."""
    c = rec.contract
    lo, hi = int(r_min_m / c.range_res_m), int(r_max_m / c.range_res_m) + 1
    if c.use_phase:
        H, _, _ = R.to_inputs(rec)
        a = np.abs(H[:, 1, lo:hi]).mean(axis=(1, 2))
        a[~rec.valid] = np.nan
        t = rec.t_s - 0.5 / c.fps        # a phase change belongs to the middle of its two frames
    else:
        a = R.motion_energy(rec, r_min_m, r_max_m)
        t = rec.t_s
    return t, _movavg(_fill(a), SMOOTH_S * c.fps)


def pose_activity(pose):
    """Speed of the shoulder rise."""
    fs = 1 / np.median(np.diff(pose.t_s))
    rise = _movavg(-_fill(pose.gap_m), SMOOTH_S * fs)
    return pose.t_s, _movavg(np.abs(np.gradient(rise)) * fs, SMOOTH_S * fs)


def imu_activity(imu):
    """Speed of the arm from the high-passed acceleration (1-s high-pass before and after integrating)."""
    fs = imu.fs
    a = np.linalg.norm(imu.acc_g, axis=1)
    a = a - _movavg(a, 1.0 * fs)
    v = (np.cumsum(a) - 0.5 * a) / fs       # trapezoid: velocity at the sample, not half a sample later
    v = v - _movavg(v, 1.0 * fs)
    return imu.t_s, _movavg(np.abs(v), SMOOTH_S * fs)


def emg_activity(emg):
    return emg.t_s, _movavg(emg.env - np.median(emg.env), SMOOTH_S * emg.fs)


def shrug_window(markers, t_first, t_last, length_s=10.0):
    """[start, end] seconds: from 1 s before the 's' (sync shrugs) marker until just before the first rep
    marker (at most length_s); without an 's' marker, the first 30 s."""
    s = [t for t, k, _ in markers if k == "s"]
    if s:
        end = s[0] + length_s
        later = [t for t, k, _ in markers if k == "space" and t > s[0]]
        if later:
            end = min(end, later[0] - 0.3)
        return max(t_first, s[0] - 1.0), min(t_last, end)
    return t_first, min(t_last, t_first + 30.0)


def count_peaks(t, a, window, min_sep_s=0.6, z=1.5):
    sel = (t >= window[0]) & (t <= window[1])
    if sel.sum() < 10:
        return 0
    x = a[sel]
    x = (x - np.median(x)) / (np.std(x) + 1e-9)
    tt = t[sel]
    peaks, last = 0, -np.inf
    above = x > z
    for i in range(1, len(x) - 1):
        if above[i] and x[i] >= x[i - 1] and x[i] >= x[i + 1] and tt[i] - last >= min_sep_s:
            peaks += 1
            last = tt[i]
    return peaks


def estimate_offset(t_ref, a_ref, t_x, a_x, window, max_lag_s=MAX_LAG_S):
    """-> (offset_s, correlation): t_x + offset_s lines the sensor up with the reference."""
    grid = np.arange(window[0], window[1], 1 / GRID_HZ)
    if grid.size < 2 * max_lag_s * GRID_HZ + 10:
        return np.nan, 0.0
    r = np.interp(grid, t_ref, a_ref)
    r = (r - r.mean()) / (r.std() + 1e-9)
    L = int(round(max_lag_s * GRID_HZ))
    lags = np.arange(-L, L + 1)
    corr = np.empty(len(lags))
    for k, lag in enumerate(lags):
        x = np.interp(grid + lag / GRID_HZ, t_x, a_x)     # the sensor seen `lag` steps later
        x = (x - x.mean()) / (x.std() + 1e-9)
        corr[k] = np.mean(r * x)
    k = int(np.argmax(corr))
    shift = 0.0
    if 0 < k < len(lags) - 1:                              # refine between grid steps
        y0, y1, y2 = corr[k - 1], corr[k], corr[k + 1]
        den = y0 - 2 * y1 + y2
        shift = 0.5 * (y0 - y2) / den if den else 0.0
    delay = (lags[k] + shift) / GRID_HZ
    return -delay, float(corr[k])


def sync_offsets(rec, markers, emg=None, imu=None, pose=None):
    """{sensor: {"offset_ms", "corr", "shrugs_found", "applied", "note"}} with the radar as reference."""
    t_r, a_r = radar_activity(rec)
    window = shrug_window(markers, t_r[0], t_r[-1])
    out = {"radar": {"offset_ms": 0.0, "corr": 1.0, "shrugs_found": count_peaks(t_r, a_r, window),
                     "applied": False, "note": "reference", "window_s": [round(w, 2) for w in window]}}
    for name, obj, fn, apply in (("pose", pose, pose_activity, True), ("imu", imu, imu_activity, True),
                                 ("emg", emg, emg_activity, False)):
        if obj is None:
            continue
        t_x, a_x = fn(obj)
        off, corr = estimate_offset(t_r, a_r, t_x, a_x, window)
        found = count_peaks(t_x, a_x, window)
        ok = np.isfinite(off) and corr >= MIN_CORR and found >= 2
        note = "" if ok else "shrugs not clear enough to measure"
        if name == "emg":
            note = ("reported only: includes the muscle's electromechanical delay" if ok
                    else "no shrugs seen in sEMG (fine if the sensor is on the biceps)")
        out[name] = {"offset_ms": None if not np.isfinite(off) else round(1000 * off, 1), "corr": round(corr, 3),
                     "shrugs_found": found, "applied": bool(ok and apply), "note": note}
    return out
