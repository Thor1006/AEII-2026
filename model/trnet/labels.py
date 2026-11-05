"""Labels per rep, measured on the ground-truth sensors and compared with the session's first reps.

ALL NUMBERS IN PLACEHOLDER_THRESHOLDS ARE PLACEHOLDERS, to be agreed with a physiotherapist.
  fatigue      = MDF drop vs the baseline reps, 20 % drop -> 1.0                      (needs sEMG)
  quality      = mean of ROM, peak speed and smoothness, each vs baseline, 0..1      (needs pose or IMU)
  comp_shrug   = shoulder rises more than 2 cm beyond baseline (ear-shoulder gap)   (needs pose)
  comp_lean    = trunk leans more than 10 deg beyond baseline                       (needs pose)
  comp_rom     = ROM under 80 % of baseline                                         (needs pose or IMU)
  risk         = any compensation flag in the next 3 reps of the same set           (needs pose)
A label that can't be measured is masked (left out of training), never set to 0.
"""
import numpy as np

from .network import AUX, HEADS

PLACEHOLDER_THRESHOLDS = {
    "baseline_reps": 3,
    "fatigue_full_mdf_drop": 0.20,
    "shrug_cm": 2.0,
    "lean_deg": 10.0,
    "reduced_rom_ratio": 0.80,
    "risk_next_reps": 3,
    "still_s": 5.0,
    "mdf_smooth_reps": 3,    # MDF label smoothed over 3 neighbouring reps (labels only)          # the protocol starts with 5 s standing still: reference for the shoulder gap
}
AUX_SCALE = {"rom": 100.0, "shoulder_rise": 5.0, "trunk_lean": 20.0, "mdf_ratio": 1.0}


def _in(t, a, b):
    return (t >= a) & (t <= b)


def rep_measures(reps, mdf=None, pose=None, still_s=PLACEHOLDER_THRESHOLDS["still_s"]):
    """Raw measurements per rep: rom_deg, peak_speed_dps, sparc, mdf_hz, rise_cm, lean_deg (NaN = unknown)."""
    gap_ref = np.nan
    if pose is not None:
        early = _in(pose.t_s, pose.t_s[0], pose.t_s[0] + still_s) & np.isfinite(pose.gap_m)
        gap_ref = np.nanmedian(pose.gap_m[early]) if early.any() else np.nanmedian(pose.gap_m)
    rows = []
    for r in reps:
        m = {"rom_deg": r.rom_deg, "peak_speed_dps": r.peak_speed_dps, "sparc": r.sparc,
             "mdf_hz": np.nan, "rise_cm": np.nan, "lean_deg": np.nan}
        if mdf is not None:                      # MDF while the muscle works: windows with at least half the
            t, f, pw = mdf                       # rep's highest band power, weighted by that power
            sel = _in(t, r.start_s, r.end_s)
            if sel.sum() >= 1:
                w = pw[sel] * (pw[sel] >= 0.5 * pw[sel].max())
                m["mdf_hz"] = float(np.sum(w * f[sel]) / np.sum(w))
        if pose is not None:
            sel = _in(pose.t_s, r.start_s, r.end_s)
            if np.isfinite(pose.gap_m[sel]).sum() >= 3:
                m["rise_cm"] = float(100 * (gap_ref - np.nanmin(pose.gap_m[sel])))
                m["lean_deg"] = float(np.nanmax(pose.trunk_lean_deg[sel]))
        rows.append(m)
    return rows


def smooth_over_reps(x, n=3):
    """Centred running mean over n neighbouring reps (NaN-aware). sEMG MDF from one 2-s rep scatters by ~5 %,
    which is a quarter of the full fatigue scale; labels may look at neighbouring reps, the model never does."""
    x = np.asarray(x, float)
    out = np.full_like(x, np.nan)
    h = n // 2
    for i in range(len(x)):
        w = x[max(0, i - h):i + h + 1]
        if np.isfinite(w).any():
            out[i] = np.nanmean(w)
    out[~np.isfinite(x)] = np.nan
    return out


def make_labels(reps, measures, th=PLACEHOLDER_THRESHOLDS):
    """-> targets {head: [R]} and masks {head: [R]} (+ "aux" [R,4] and "aux_mask" [R,4])."""
    R = len(reps)
    nb = th["baseline_reps"]
    col = {k: np.array([m[k] for m in measures], float) for k in measures[0]} if R else {}
    if R:
        col["mdf_hz"] = smooth_over_reps(col["mdf_hz"], th.get("mdf_smooth_reps", 3))
    tgt = {h: np.zeros(R, np.float32) for h in HEADS}
    msk = {h: np.zeros(R, bool) for h in HEADS}
    aux = np.zeros((R, len(AUX)), np.float32)
    aux_m = np.zeros((R, len(AUX)), bool)
    if R <= nb:
        return tgt, msk, aux, aux_m

    def base(k):
        v = col[k][:nb]
        return float(np.median(v)) if np.isfinite(v).all() else np.nan

    with np.errstate(invalid="ignore", divide="ignore"):
        b_mdf = base("mdf_hz")
        if np.isfinite(b_mdf):
            ratio = col["mdf_hz"] / b_mdf
            ok = np.isfinite(ratio)
            tgt["fatigue"][ok] = np.clip((1 - ratio[ok]) / th["fatigue_full_mdf_drop"], 0, 1)
            msk["fatigue"] = ok
            aux[ok, AUX.index("mdf_ratio")] = ratio[ok]
            aux_m[:, AUX.index("mdf_ratio")] = ok

        b_rom, b_spd, b_sp = base("rom_deg"), base("peak_speed_dps"), base("sparc")
        if np.isfinite(b_rom):
            parts = [np.clip(col["rom_deg"] / b_rom, 0, 1)]
            if np.isfinite(b_spd) and b_spd > 0:
                parts.append(np.clip(col["peak_speed_dps"] / b_spd, 0, 1))
            if np.isfinite(b_sp) and b_sp < 0:
                parts.append(np.clip(b_sp / col["sparc"], 0, 1))
            q = np.nanmean(np.vstack(parts), axis=0)
            ok = np.isfinite(q)
            tgt["quality"][ok], msk["quality"] = q[ok], ok
            red = col["rom_deg"] < th["reduced_rom_ratio"] * b_rom
            tgt["comp_rom"], msk["comp_rom"] = red.astype(np.float32), np.isfinite(col["rom_deg"])
            aux[:, AUX.index("rom")] = col["rom_deg"] / AUX_SCALE["rom"]
            aux_m[:, AUX.index("rom")] = np.isfinite(col["rom_deg"])

        b_rise, b_lean = base("rise_cm"), base("lean_deg")
        if np.isfinite(b_rise) and np.isfinite(b_lean):
            rise = col["rise_cm"] - b_rise
            lean = col["lean_deg"] - b_lean
            ok = np.isfinite(rise) & np.isfinite(lean)
            tgt["comp_shrug"][ok] = (rise[ok] > th["shrug_cm"]).astype(np.float32)
            tgt["comp_lean"][ok] = (lean[ok] > th["lean_deg"]).astype(np.float32)
            msk["comp_shrug"], msk["comp_lean"] = ok.copy(), ok.copy()
            aux[ok, AUX.index("shoulder_rise")] = rise[ok] / AUX_SCALE["shoulder_rise"]
            aux[ok, AUX.index("trunk_lean")] = lean[ok] / AUX_SCALE["trunk_lean"]
            aux_m[:, AUX.index("shoulder_rise")] = ok
            aux_m[:, AUX.index("trunk_lean")] = ok

    flags_known = msk["comp_shrug"] & msk["comp_lean"] & msk["comp_rom"]
    any_flag = (tgt["comp_shrug"] + tgt["comp_lean"] + tgt["comp_rom"]) > 0
    n = th["risk_next_reps"]
    for i, r in enumerate(reps):
        nxt = [j for j in range(i + 1, min(R, i + 1 + n)) if reps[j].set_id == r.set_id]
        if nxt and flags_known[nxt].all():
            tgt["risk"][i] = float(any_flag[nxt].any())
            msk["risk"][i] = True
    return tgt, msk, aux, aux_m   # baseline reps keep their labels: they are what 'normal' looks like
