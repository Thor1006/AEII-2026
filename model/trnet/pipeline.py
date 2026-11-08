"""One session folder -> radar input, synced ground truth, reps and labels (used by the check and the dataset)."""
from dataclasses import dataclass, field

import numpy as np

from . import labels as L
from . import radar as R
from . import reps as RP
from . import sync as SY
from . import truth as TR


@dataclass
class Processed:
    session: object
    radar: object = None              # RadarRecording
    emg: object = None
    imu: object = None
    pose: object = None
    sync: dict = field(default_factory=dict)
    rep_source: str = None            # reps found from: "pose" or "imu" (elbow angle), or "emg" (envelope, fallback)
    reps: list = field(default_factory=list)
    measures: list = field(default_factory=list)
    targets: dict = field(default_factory=dict)
    masks: dict = field(default_factory=dict)
    aux: np.ndarray = None
    aux_mask: np.ndarray = None
    notes: list = field(default_factory=list)

    @property
    def name(self):
        return self.session.dir.name


def process(path, contract=None, apply_sync=True):
    from rec import session as S
    s = S.load(path)
    out = Processed(s)
    src = s.meta.get("sources", {})
    if "radar" in src and (s.dir / "radar.bin").exists():
        try:
            out.radar = R.load_radar(s, contract)
        except ValueError as exc:                 # e.g. no frames saved: the check reports it, it doesn't crash
            out.notes.append(str(exc))
    out.emg, out.imu, out.pose = TR.load_emg(s), TR.load_imu(s), TR.load_pose(s)
    if out.radar is not None:
        out.sync = SY.sync_offsets(out.radar, s.markers, out.emg, out.imu, out.pose)
        if apply_sync:
            for name in ("pose", "imu"):
                info = out.sync.get(name)
                if info and info["applied"]:
                    setattr(out, name, TR.shift(getattr(out, name), info["offset_ms"] / 1000))
    if out.pose is not None:
        out.rep_source, out.reps = "pose", RP.find_reps(out.pose.t_s, out.pose.flexion_deg)
    elif out.imu is not None:
        flex, _ = TR.forearm_flexion(out.imu)
        out.rep_source, out.reps = "imu", RP.find_reps(out.imu.t_s, flex)
    if not out.reps and out.emg is not None:      # no angle, or no reps in it: the sEMG bursts instead
        if out.rep_source:
            out.notes.append(f"no reps in the {out.rep_source} elbow angle: reps from the sEMG envelope instead")
        out.rep_source, out.reps = "emg", RP.find_reps_emg(out.emg.t_s, out.emg.env)
    if out.rep_source is None:
        out.notes.append("no pose, IMU or sEMG: reps can't be found")
        return out
    mdf = TR.emg_mdf(out.emg) if out.emg is not None else None
    out.measures = L.rep_measures(out.reps, mdf, out.pose)
    if out.reps:
        out.targets, out.masks, out.aux, out.aux_mask = L.make_labels(out.reps, out.measures)
    return out


def rep_inputs(p: Processed, contract=None):
    """Radar input per rep: H [R,T,C,64,16], D [R,T,1,64,16], fmask [R,T], cropped [R] (float16 to save space)."""
    rec = p.radar
    c = contract or rec.contract
    H, D, valid = R.to_inputs(rec)
    T = c.frames_per_rep
    n = len(p.reps)
    Hr = np.zeros((n, T) + H.shape[1:], np.float16)
    Dr = np.zeros((n, T) + D.shape[1:], np.float16)
    fm = np.zeros((n, T), bool)
    cropped = np.zeros(n, bool)
    for i, rep in enumerate(p.reps):
        idx, mask, cropped[i] = RP.rep_frames(rep, rec.t_s, rec.valid, T)
        ok = idx >= 0
        Hr[i, ok] = H[idx[ok]]
        Dr[i, ok] = D[idx[ok]]
        fm[i] = mask
    return Hr, Dr, fm, cropped
