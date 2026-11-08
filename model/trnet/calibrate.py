"""Measure the real recordings once -> calib/real_stats.json (small, no personal data; the fake-data generator
reads it, so it also works on a computer without the recordings).

  radar  empty-room sessions (notes say "nobody in front"). Room-specific numbers come from the longest one
         only: the two recordings of 2026-11-04 differ by up to 38 dB in some range bins (the setup changed).
         Static clutter per cell (complex mean, antenna domain); its fluctuation as patterns across the 8
         antennas per range bin (they move together: near bins are 74-99 % one pattern), each with its own
         frame-to-frame correlation (0.85-0.99 near, 0.1-0.6 further);
         range-Doppler level and spread; phase noise by signal level. Timing is pooled: frame period,
         missing-frame rate and the real delivery-jitter sequence (replayed by the generator).
  imu    real (not firmware-simulated) sessions: noise and bias per axis in still stretches, |acc| scale
         (the accelerometer is not calibrated yet); Wi-Fi extra delay sequence from the session that recorded
         USB and Wi-Fi copies of the same samples
  emg, pose  no real recordings yet: textbook values, marked "uncalibrated"
Run:  python -m trnet.calibrate        (rerun after the first real sessions to update everything)
"""
import argparse
import datetime
import json

import numpy as np

from . import paths
from . import radar as R
from . import truth as TR

FORMAT = "trnet-calib/1"


def is_simulated(session, name=None):
    """Firmware or recorder simulations are not real data: header says SIMULATED, exercise says sim, or radar kind sim."""
    ex = session.meta.get("exercise", "").lower().split("_")
    if "sim" in ex or "sim2" in ex:
        return True
    names = [name] if name else list(session.meta.get("sources", {}))
    for n in names:
        if (session.meta.get("sources", {}).get(n) or {}).get("kind") == "sim":
            return True
        if any("SIMULATED" in txt for _, txt in TR.comment_lines(session, n)):
            return True
    return False


def _sessions(root):
    from rec import session as S
    out = []
    for d in sorted(p for p in root.iterdir() if (p / "meta.json").exists()):
        try:
            out.append(S.load(d))
        except ValueError:
            pass
    return out


def radar_stats(sessions):
    empty = [s for s in sessions if "radar" in s.meta.get("sources", {}) and not is_simulated(s, "radar")
             and "nobody" in s.meta.get("notes", "").lower() and (s.dir / "radar.bin").exists()]
    if not empty:
        return None
    recs = [R.load_radar(s) for s in empty]
    main = max(recs, key=lambda r: r.valid.sum())
    c = main.contract
    from radarlab.tlv import FrameReader
    idx = empty[recs.index(main)].radar_index()
    raw = (empty[recs.index(main)].dir / "radar.bin").read_bytes()
    iq = np.array([R.static_iq(FrameReader().feed(raw[o:o + n])[0].tlvs[R.STATIC_HEATMAP], len(c.az_index))
                   for o, n in zip(idx["offset"], idx["length"])])
    mean = iq.mean(0)
    dev = iq - mean
    comp_re, comp_im, comp_var, rho, resid = [], [], [], [], []
    for r in range(dev.shape[1]):              # per range bin: every pattern across the 8 antennas (eigenvectors)
        C = dev[:, r].T @ dev[:, r].conj() / len(dev)
        w, V = np.linalg.eigh(C)
        U = V[:, ::-1]                                                  # [8 antennas, 8 patterns], strongest first
        coef = dev[:, r] @ U.conj()                                     # [frames, 8]
        comp_re.append(U.real.T)
        comp_im.append(U.imag.T)
        comp_var.append(np.maximum(w[::-1], 0))
        rho.append([float(np.clip(np.abs(np.vdot(c[:-1], c[1:])) / max(np.vdot(c, c).real, 1e-9), 0, 0.995))
                    for c in coef.T])
        left = dev[:, r] - coef @ U.T
        resid.append(np.sqrt((np.abs(left) ** 2).mean(0) / 2))
    keep = main.valid
    mag_db = 20 * np.log10(np.abs(main.Z[keep]) + 1e-3)
    rd = main.rd_db[keep]
    pair = main.valid[1:] & main.valid[:-1]
    dphi = np.angle(main.Z[1:] * np.conj(main.Z[:-1]))[pair]
    lvl = (20 * np.log10(np.abs(main.Z[1:]) + 1e-3))[pair]
    phase_by_level = []
    for lo in range(0, 70, 10):
        sel = (lvl >= lo) & (lvl < lo + 10)
        if sel.sum() > 100:
            phase_by_level.append([lo, lo + 10, round(float(dphi[sel].std()), 4), int(sel.sum())])
    jitter_ms = (main.arrival_s - main.t_s)[main.valid] * 1000
    n_all = sum(len(r.valid) for r in recs)
    return {
        "sessions": [s.dir.name for s in empty],
        "frames": int(sum(r.valid.sum() for r in recs)),
        "profile": {"fps": c.fps, "range_bins": c.range_bins, "angle_bins": c.angle_bins,
                    "doppler_bins": c.doppler_bins, "az_cols": list(c.az_cols), "range_res_m": c.range_res_m,
                    "vel_res_ms": c.vel_res_ms},
        "frame_period_s": round(float(np.mean([np.diff(r.t_s).mean() for r in recs])), 7),
        "missing_frame_rate": round(float(sum((~r.valid).sum() for r in recs) / n_all), 6),
        "delivery_jitter_ms": {"quantiles_0_100_by_5": np.round(np.percentile(jitter_ms, np.arange(0, 101, 5)), 3).tolist(),
                               "sequence": np.round(jitter_ms, 2).tolist()},
        "room_from": empty[recs.index(main)].dir.name,
        "static_iq_mean_real": np.round(mean.real, 2).tolist(),
        "static_iq_mean_imag": np.round(mean.imag, 2).tolist(),
        "static_iq_pattern_real": np.round(comp_re, 3).tolist(),      # [64, 8 patterns, 8 antennas]
        "static_iq_pattern_imag": np.round(comp_im, 3).tolist(),
        "static_iq_pattern_var": np.round(comp_var, 3).tolist(),      # [64, 8]
        "static_iq_pattern_rho": np.round(rho, 4).tolist(),           # [64, 8] frame-to-frame correlation
        "static_iq_resid_std": np.round(resid, 3).tolist(),           # [64, 8]
        "static_db_median": np.round(np.median(mag_db, 0), 2).tolist(),
        "static_power_db": np.round(10 * np.log10((np.abs(main.Z[keep]) ** 2).mean(axis=(0, 2))), 2).tolist(),
        "rd_db_median": np.round(np.median(rd, 0), 3).tolist(),
        "rd_db_std": np.round(rd.std(0), 3).tolist(),
        "phase_noise_rad_by_level_db": phase_by_level,
        "temperature_c": [float(np.nanmin([np.nanmin(r.temp_c) for r in recs])),
                          float(np.nanmax([np.nanmax(r.temp_c) for r in recs]))],
        "points_per_frame_median": float(np.median(np.concatenate([r.n_points[r.valid] for r in recs]))),
        "motion_energy_db_p50_p99": np.round(np.nanpercentile(np.concatenate([R.motion_energy(r) for r in recs]),
                                                             [50, 99]), 2).tolist(),
    }


def _still_windows(imu, win_s=1.0):
    g = np.linalg.norm(imu.gyro_dps - np.median(imu.gyro_dps, 0), axis=1)
    a = np.linalg.norm(imu.acc_g, axis=1)
    n = int(win_s * imu.fs)
    med = np.median(a)
    return [slice(k, k + n) for k in range(0, len(g) - n, n)
            if g[k:k + n].std() < 0.5 and abs(np.median(a[k:k + n]) - med) < 0.05]


def imu_stats(sessions):
    real, used, acc_sd, gyro_sd, bias, norms, usb_jit = [], [], [], [], [], [], []
    for s in sessions:
        if "imu" not in s.meta.get("sources", {}) or is_simulated(s, "imu"):
            continue
        imu = TR.load_imu(s)
        if imu is None:
            continue
        wins = _still_windows(imu)
        if not wins:
            continue
        used.append(s.dir.name)
        acc_sd += [imu.acc_g[w].std(0) for w in wins]
        gyro_sd += [imu.gyro_dps[w].std(0) for w in wins]
        bias += [imu.gyro_dps[w].mean(0) for w in wins]
        norms += [np.linalg.norm(imu.acc_g[w], axis=1).mean() for w in wins]
        if not str(s.meta["sources"]["imu"].get("port", "")).startswith("tcp://"):
            usb_jit.append((imu.t_host_s - imu.t_s) * 1000)
    if not used:
        return None
    out = {"sessions": used, "still_windows_s": len(acc_sd),
           "counts_per_g": TR.ACC_PER_G, "counts_per_dps": TR.GYRO_PER_DPS, "fs": 200.0,
           "acc_noise_std_g": np.round(np.median(acc_sd, 0), 5).tolist(),
           "gyro_noise_std_dps": np.round(np.median(gyro_sd, 0), 4).tolist(),
           "gyro_bias_dps": np.round(np.median(bias, 0), 3).tolist(),
           "acc_norm_g": round(float(np.median(norms)), 4),
           "acc_note": "|acc| is above 1 g because the accelerometer's 6-face calibration has not been run"}
    if usb_jit:
        j = np.concatenate(usb_jit)
        out["usb_delivery_ms_quantiles_0_100_by_5"] = np.round(np.percentile(j, np.arange(0, 101, 5)), 3).tolist()
    return out


def wifi_stats(sessions):
    """Wi-Fi extra delay vs USB for the same samples, from a session that recorded both copies."""
    for s in sessions:
        src = s.meta.get("sources", {})
        if not str((src.get("imu") or {}).get("port", "")).startswith("tcp://") or "emg" not in src:
            continue
        usb, wifi = TR.record_rows(s, "emg", "I"), TR.record_rows(s, "imu", "I")
        if usb is None or wifi is None:
            continue
        t_usb = dict(zip(usb["dev_us"].tolist(), usb["t_host_s"].tolist()))
        both = [(d, t) for d, t in zip(wifi["dev_us"].tolist(), wifi["t_host_s"].tolist()) if d in t_usb]
        if len(both) < 1000:
            continue
        dev = np.array([d for d, _ in both])
        extra_ms = np.array([(t - t_usb[d]) * 1000 for d, t in both])
        arr = np.array([t for _, t in both])
        gaps = np.diff(arr)
        lost = np.diff(dev) > 1.5 * 5000
        pauses = gaps[(gaps > 0.5) & ~lost]
        minutes = (arr[-1] - arr[0]) / 60
        return {"session": s.dir.name, "samples": len(both),
                "extra_delay_ms_quantiles_0_100_by_5": np.round(np.percentile(extra_ms, np.arange(0, 101, 5)), 2).tolist(),
                "extra_delay_ms_every_20ms": np.round(extra_ms[::4], 1).tolist(),
                "pauses_per_min": round(len(pauses) / minutes, 3),
                "pause_s": np.round(pauses, 3).tolist(),
                "share_over_30ms": round(float((extra_ms > 30).mean()), 4),
                "share_over_100ms": round(float((extra_ms > 100).mean()), 4)}
    return None


TEXTBOOK = {
    "emg": {"uncalibrated": True, "fs": 1000.0, "mdf_hz_fresh": [80.0, 110.0], "mdf_drop_when_tired": 0.25,
            "raw_center": 1900, "raw_rest_std": 6.0, "raw_active_std": [120.0, 300.0],
            "bluetooth_batch_ms": 20, "bluetooth_delay_ms": [8.0, 40.0],
            "note": "textbook-style values; replace by rerunning calibrate after a real MyoWare record session"},
    "pose": {"uncalibrated": True, "fps": 30.0, "latency_ms": 60.0, "latency_jitter_ms": 8.0,
             "jitter_m": 0.004, "visibility": 0.95,
             "note": "webcam latency and MediaPipe jitter not measured yet; the shrug sync is meant to find the latency"},
}


def measure(root=paths.SESSIONS):
    sessions = _sessions(root)
    return {"format": FORMAT,
            "made": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "from": str(root.relative_to(paths.REPO)) if root.is_relative_to(paths.REPO) else str(root),
            "skipped_simulated": [s.dir.name for s in sessions if is_simulated(s)],
            "radar": radar_stats(sessions), "imu": imu_stats(sessions), "wifi": wifi_stats(sessions),
            **TEXTBOOK}


def _dump(obj, indent=0):
    """JSON with dicts indented and lists of numbers on one line (keeps the file readable and small)."""
    pad = " " * indent
    if isinstance(obj, dict):
        items = [f'{pad} "{k}": {_dump(v, indent + 1).lstrip()}' for k, v in obj.items()]
        return pad + "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(obj, list) and any(isinstance(v, (dict, list)) for v in obj) and not all(
            isinstance(v, list) and all(not isinstance(x, (dict, list)) for x in v) for v in obj):
        return pad + "[\n" + ",\n".join(_dump(v, indent + 1) for v in obj) + "\n" + pad + "]"
    return pad + json.dumps(obj, separators=(",", ":"))


def save(stats, path=paths.CALIB):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump(stats) + "\n")
    return path


def load_stats(path=paths.CALIB):
    if not path.exists():
        raise FileNotFoundError(f"{path} missing: run `python -m trnet.calibrate` on a computer with the recordings")
    s = json.loads(path.read_text())
    if s.get("format") != FORMAT:
        raise ValueError(f"{path} is not {FORMAT}")
    return s


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sessions", default=str(paths.SESSIONS), help="folder with recorder sessions")
    ap.add_argument("--out", default=str(paths.CALIB))
    a = ap.parse_args(argv)
    from pathlib import Path
    stats = measure(Path(a.sessions))
    p = save(stats, Path(a.out))
    r, i, w = stats["radar"], stats["imu"], stats["wifi"]
    print(f"wrote {p} ({p.stat().st_size // 1024} KB)")
    print(f"  skipped (simulated): {', '.join(stats['skipped_simulated']) or 'none'}")
    if r:
        print(f"  radar: {r['frames']} empty-room frames from {len(r['sessions'])} sessions, "
              f"{1 / r['frame_period_s']:.2f} fps, missing {r['missing_frame_rate']:.4%}, "
              f"jitter p50/p95 {r['delivery_jitter_ms']['quantiles_0_100_by_5'][10]}/"
              f"{r['delivery_jitter_ms']['quantiles_0_100_by_5'][19]} ms")
    if i:
        print(f"  imu: {i['still_windows_s']} s still from {len(i['sessions'])} sessions, acc noise {i['acc_noise_std_g']} g, "
              f"gyro noise {i['gyro_noise_std_dps']} dps, |acc| {i['acc_norm_g']} g")
    if w:
        q = w["extra_delay_ms_quantiles_0_100_by_5"]
        print(f"  wifi: {w['samples']} paired samples, extra delay median {q[10]} ms, "
              f">30 ms {w['share_over_30ms']:.1%}, >100 ms {w['share_over_100ms']:.1%}, pauses {w['pause_s']}")
    print("  emg, pose: uncalibrated (no real recordings yet)")


if __name__ == "__main__":
    main()
