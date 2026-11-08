"""Recorded radar frames -> network input (H, D, mask) on a regular frame grid.

Units, measured 2026-11-05 on the real recordings:
  static heatmap (TLV 4): 64 range bins x 8 azimuth antennas, complex int16 stored imaginary first; it is the
      zero-Doppler bin, so it holds what is NOT moving (radar-lab maps.range_azimuth reads it the same way)
  range-Doppler (TLV 5): uint16 = 256 * log2(magnitude) (median 40 dB in an empty room), zero speed in column 0
  temperature (TLV 9): '<iI10h' valid flag (0 = valid), time ms, 10 sensors (the 10th is reserved)
  detected points (TLV 1): float32 x, y, z, radial speed per point (x across, y forward, z up, metres);
      side info (TLV 7): int16 SNR, int16 noise per point, in 0.1 dB. ~7 points per frame (median, Nov 5 curls).
Points and heatmaps come in the same frame, so they are the same instant: point_cells() puts each point on the
heatmap's range x angle grid, and PointWindow turns the last points_window frames of points into the height and
presence layers (contract v1). points_on_heatmap() measures how well they agree (still points should sit on
bright static-heatmap cells); it also fixed which way x runs along the angle axis (contract.points_az_sign).
Times: the radar has no clock of its own in the output, but frames come exactly one period apart, so
frame_no x period is used as a device clock and fitted to the host arrivals (lower edge, same as the IMU).
That removes the USB bunching (arrivals median 15.9 ms apart, p99 19.4 ms, although the mean is 16.667 ms).
"""
import collections
import dataclasses
import struct
from dataclasses import dataclass, field

import numpy as np

from . import paths  # noqa: F401
from .contract import InputContract, default_contract

DETECTED_POINTS, STATIC_HEATMAP, RANGE_DOPPLER, SIDE_INFO, TEMPERATURE = 1, 4, 5, 7, 9
LOG2_Q8_TO_DB = 20 * np.log10(2) / 256
WAVELENGTH_M = 3e8 / 77e9
PHASE_GATE_DB = 30.0   # phase is only trusted in cells within 30 dB of the session reference


def static_iq(payload, n_ant=8):
    """Static heatmap payload -> complex [range_bins, n_ant]."""
    iq = np.frombuffer(payload, "<i2").reshape(-1, n_ant, 2).astype(np.float32)
    return iq[..., 1] + 1j * iq[..., 0]


def angle_fft(iq, contract: InputContract):
    """Complex [range, 8 antennas] -> complex [range, angle_bins], antennas at their real columns, zero angle
    in the middle (same as radar-lab maps.range_azimuth, but keeping the phase)."""
    cols = np.asarray(contract.az_cols)
    row = np.zeros(iq.shape[:-1] + (cols.max() + 1,), np.complex64)
    row[..., cols] = iq[..., list(contract.az_index)]
    return np.fft.fftshift(np.fft.fft(row, contract.angle_bins, axis=-1), axes=-1).astype(np.complex64)


def rd_db(payload, range_bins):
    """Range-Doppler payload -> dB [range, doppler], zero speed in the middle column."""
    rd = np.frombuffer(payload, "<u2").astype(np.float32).reshape(range_bins, -1)
    return np.fft.fftshift(rd, axes=1) * LOG2_Q8_TO_DB


def points_of(tlvs):
    """One frame's detected points -> float32 [n, 5]: x, y, z (m), radial speed (m/s), SNR (dB; NaN if not sent)."""
    raw = tlvs.get(DETECTED_POINTS, b"")
    p = np.frombuffer(raw, "<f4").reshape(-1, 4) if len(raw) >= 16 else np.zeros((0, 4), np.float32)
    out = np.full((len(p), 5), np.nan, np.float32)
    out[:, :4] = p
    side = tlvs.get(SIDE_INFO, b"")
    if len(p) and len(side) == 4 * len(p):
        out[:, 4] = np.frombuffer(side, "<i2").reshape(-1, 2)[:, 0] / 10.0
    return out


def point_cells(pts, contract: InputContract):
    """(range bin, angle bin, inside) of each point on the H grid, the same axes as angle_fft (fftshifted).
    The angle bin comes from the direction cosine along the antenna row, u = x / r: bin = A/2 (1 + sign u)."""
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 5)
    r = np.sqrt((pts[:, :3] ** 2).sum(1))
    u = np.divide(pts[:, 0], r, out=np.zeros_like(r), where=r > 0)
    rb = np.rint(r / contract.range_res_m).astype(int)
    n = contract.angle_bins
    ab = np.clip(np.rint(n / 2 * (1 + contract.points_az_sign * u)).astype(int), 0, n - 1)
    inside = (r > 0) & (rb < contract.range_bins) & np.isfinite(pts[:, 2])
    return rb, ab, inside


class PointWindow:
    """Height and presence layers [range, angle] from the points of the last contract.points_window frames.
    Frame by frame, so the Pi bridge (live) and to_inputs (recordings) compute exactly the same thing."""

    def __init__(self, contract: InputContract):
        self.c = contract
        shape = (contract.range_bins, contract.angle_bins)
        self.n, self.w, self.wz = np.zeros(shape), np.zeros(shape), np.zeros(shape)
        self.hist = collections.deque()

    def push(self, pts):
        """Add one frame's points ([n, 5] from points_of; None or empty for no points or a missing frame)."""
        entry = None
        if pts is not None and len(pts):
            rb, ab, ok = point_cells(pts, self.c)
            if ok.any():
                w = np.nan_to_num(np.asarray(pts, float)[ok, 4], nan=10.0).clip(1.0, None)  # SNR (dB) as the weight
                entry = (rb[ok], ab[ok], w, w * np.asarray(pts, float)[ok, 2])
        self._add(entry, 1.0)
        self.hist.append(entry)
        if len(self.hist) > self.c.points_window:
            self._add(self.hist.popleft(), -1.0)

    def _add(self, entry, sign):
        if entry is None:
            return
        rb, ab, w, wz = entry
        np.add.at(self.n, (rb, ab), sign)
        np.add.at(self.w, (rb, ab), sign * w)
        np.add.at(self.wz, (rb, ab), sign * wz)

    def layers(self):
        """(height -1..1, presence 0..1), float32."""
        has = self.n > 0.5
        height = np.zeros(self.n.shape, np.float32)
        height[has] = np.clip(self.wz[has] / np.maximum(self.w[has], 1e-9) / self.c.height_scale_m, -1, 1)
        return height, np.clip(self.n / self.c.presence_full, 0, 1).astype(np.float32)


def temperature_c(payload):
    """Hottest valid sensor in deg C, or NaN when the radar marks the reading invalid."""
    if len(payload) < 28:
        return np.nan
    valid, _ms, *sensors = struct.unpack_from("<iI10h", payload)
    return float(max(sensors[:9])) if valid == 0 else np.nan


@dataclass
class RadarRecording:
    frame_no: np.ndarray        # [N] every frame number from first to last (a regular grid)
    t_s: np.ndarray             # [N] fitted host-clock time of each frame (also for missing ones)
    valid: np.ndarray           # [N] False where the frame never arrived or couldn't be parsed
    Z: np.ndarray               # [N, 64, A] complex angle spectrum of the static heatmap (0 when missing)
    rd_db: np.ndarray           # [N, 64, 16] range-Doppler dB (0 when missing)
    temp_c: np.ndarray          # [N] NaN when missing/invalid
    n_points: np.ndarray        # [N]
    arrival_s: np.ndarray       # [N] host arrival time, NaN when missing
    contract: InputContract
    problems: list = field(default_factory=list)
    points: list = field(default_factory=list)   # [N] float32 [n, 5] per frame (points_of), None when missing

    @property
    def fps(self):
        return (len(self.t_s) - 1) / (self.t_s[-1] - self.t_s[0]) if len(self.t_s) > 1 else float("nan")


def contract_for(session_meta, **overrides):
    """Contract matching a session's recorded radar profile (falls back to the default profile)."""
    lines = (session_meta.get("sources", {}).get("radar", {}) or {}).get("cfg_lines")
    return InputContract.from_radar_cfg(lines, **overrides) if lines else default_contract(**overrides)


def load_radar(session, contract: InputContract | None = None):
    """session: a recorder Session (rec.session.load). Returns a RadarRecording."""
    from radarlab.tlv import FrameReader
    from rec.session import align_device_time

    contract = contract or contract_for(session.meta)
    idx = session.radar_index()
    raw = (session.dir / "radar.bin").read_bytes()
    nums, arrivals, statics, rds, temps, npts, pts = [], [], [], [], [], [], []
    problems = []
    n_ant = len(contract.az_index)
    for no, t, off, n in zip(idx["frame_no"], idx["t_s"], idx["offset"], idx["length"]):
        frames = FrameReader().feed(raw[off:off + n])
        if not frames:
            problems.append(f"frame {no}: could not be parsed")
            continue
        f = frames[0]
        if STATIC_HEATMAP not in f.tlvs or RANGE_DOPPLER not in f.tlvs:
            problems.append(f"frame {no}: heatmap TLVs missing")
            continue
        iq = static_iq(f.tlvs[STATIC_HEATMAP], n_ant)
        if iq.shape[0] != contract.range_bins:
            raise ValueError(f"static heatmap has {iq.shape[0]} range bins, contract says {contract.range_bins}")
        nums.append(int(no))
        arrivals.append(float(t))
        statics.append(iq)
        rds.append(rd_db(f.tlvs[RANGE_DOPPLER], contract.range_bins))
        temps.append(temperature_c(f.tlvs.get(TEMPERATURE, b"")))
        npts.append(f.num_points)
        pts.append(points_of(f.tlvs))
    if len(nums) < 2:
        raise ValueError(f"{session.dir.name}: fewer than 2 usable radar frames")
    nums = np.array(nums)
    order = np.argsort(nums, kind="stable")
    nums, keep = np.unique(nums[order], return_index=True)
    order = order[keep]
    period_us = 1e6 / contract.fps
    aligned = align_device_time(np.round(nums * period_us).astype(np.int64), np.array(arrivals)[order] * 1e9) / 1e9
    slope, icpt = np.polyfit(nums, aligned, 1)
    grid = np.arange(nums[0], nums[-1] + 1)
    k = grid.size
    pos = nums - nums[0]
    valid = np.zeros(k, bool)
    valid[pos] = True
    Z = np.zeros((k, contract.range_bins, contract.angle_bins), np.complex64)
    Z[pos] = angle_fft(np.array(statics)[order], contract)
    RD = np.zeros((k, contract.range_bins, contract.doppler_bins), np.float32)
    RD[pos] = np.array(rds, np.float32)[order]
    temp = np.full(k, np.nan)
    temp[pos] = np.array(temps)[order]
    n_points = np.zeros(k, int)
    n_points[pos] = np.array(npts)[order]
    arr = np.full(k, np.nan)
    arr[pos] = np.array(arrivals)[order]
    points = [None] * k
    for j, o in zip(pos, order):
        points[j] = pts[o]
    return RadarRecording(grid, slope * grid + icpt, valid, Z, RD, temp, n_points, arr, contract, problems, points)


def reference_levels(rec: RadarRecording):
    """dB levels that map to 1.0: the 99.5th percentile in the first baseline_s seconds (all frames if empty)."""
    c = rec.contract
    early = rec.valid & (rec.t_s - rec.t_s[0] <= c.baseline_s)
    use = early if early.sum() >= 10 else rec.valid
    mag_db = 20 * np.log10(np.abs(rec.Z[use]) + 1e-3)
    return float(np.percentile(mag_db, 99.5)), float(np.percentile(rec.rd_db[use], 99.5))


def to_inputs(rec: RadarRecording, refs=None):
    """-> H [N,C,64,A], D [N,1,64,16] (float32, 0..1 and -1..1 for phase), mask [N] (bool)."""
    c = rec.contract
    ref_h, ref_d = refs or reference_levels(rec)
    mag_db = 20 * np.log10(np.abs(rec.Z) + 1e-3)
    Hm = np.clip((mag_db - ref_h) / c.db_span + 1, 0, 1).astype(np.float32)
    Dm = np.clip((rec.rd_db - ref_d) / c.db_span + 1, 0, 1).astype(np.float32)[:, None]
    chans = [Hm]
    if c.use_phase:
        P = np.zeros_like(Hm)
        both = rec.valid[1:] & rec.valid[:-1]                       # never across a gap
        strong = mag_db > ref_h - PHASE_GATE_DB
        gate = both[:, None, None] & strong[1:] & strong[:-1]
        dphi = np.angle(rec.Z[1:] * np.conj(rec.Z[:-1])) / np.pi
        P[1:] = np.where(gate, dphi, 0).astype(np.float32)
        chans.append(P)
    if c.use_points:
        win = PointWindow(c)
        height, presence = np.zeros_like(Hm), np.zeros_like(Hm)
        for i in range(len(rec.valid)):
            win.push(rec.points[i] if rec.valid[i] and i < len(rec.points) else None)
            height[i], presence[i] = win.layers()
        chans += [height, presence]
    H = np.stack(chans, 1)
    H[~rec.valid] = 0
    Dm[~rec.valid] = 0
    return H, Dm, rec.valid.copy()


def points_on_heatmap(rec: RadarRecording, sign=None, still_only=True):
    """Agreement of the points with the static heatmap of the same frame: (median dB by which the heatmap cell under
    each still point is brighter than the median of its range bin, number of points used). A clearly positive lift
    means they agree; testing sign=+1 and -1 tells which way x runs along the angle axis."""
    c = rec.contract if sign is None else dataclasses.replace(rec.contract, points_az_sign=int(sign))
    lifts = []
    for i in np.flatnonzero(rec.valid):
        p = rec.points[i] if i < len(rec.points) else None
        if p is None or not len(p):
            continue
        if still_only:
            p = p[np.abs(p[:, 3]) < c.vel_res_ms / 2]
        rb, ab, ok = point_cells(p, c)
        ok &= rb > 0
        if not ok.any():
            continue
        mag = 20 * np.log10(np.abs(rec.Z[i]) + 1e-3)
        lifts.extend((mag[rb[ok], ab[ok]] - np.median(mag[rb[ok]], axis=1)).tolist())
    return (float(np.median(lifts)) if lifts else float("nan")), len(lifts)


def motion_energy(rec: RadarRecording, r_min_m=0.3, r_max_m=3.0):
    """Per frame: how much is moving in front (dB above each cell's session median, non-zero speeds only)."""
    c = rec.contract
    lo, hi = int(r_min_m / c.range_res_m), min(int(r_max_m / c.range_res_m) + 1, c.range_bins)
    mid = c.doppler_bins // 2
    moving = np.delete(rec.rd_db[:, lo:hi], [mid - 1, mid, mid + 1], axis=2)
    base = np.median(moving[rec.valid], axis=0)
    e = (moving - base).max(axis=(1, 2))
    e[~rec.valid] = np.nan
    return e
