"""Session folders -> training samples, cached as .npz (model/data/cache, git-ignored).

Only sessions that pass the check are used. One sample = one set of reps (at most 15; longer sets are split)
plus the session's first 3 reps as the personal baseline. Labels compare every rep with those first reps, so
fatigue keeps building across sets even though each sample is one set.
"""
import json
from dataclasses import dataclass, fields
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

from . import paths
from .check import check_and_process
from .contract import InputContract
from .labels import PLACEHOLDER_THRESHOLDS
from .network import AUX, HEADS
from .pipeline import rep_inputs
from .reps import rest_before

CODE_VERSION = 1
MAX_REPS = 15
N_BASE = PLACEHOLDER_THRESHOLDS["baseline_reps"]


@dataclass
class SessionData:
    name: str
    subject: str
    fake: bool
    H: np.ndarray          # [R, T, C, 64, 16] float16
    D: np.ndarray          # [R, T, 1, 64, 16] float16
    fmask: np.ndarray      # [R, T] bool
    feats: np.ndarray      # [R, 2] float32: duration/3 s, rest before/60 s
    set_id: np.ndarray     # [R]
    y: np.ndarray          # [R, 6] targets (HEADS order)
    ymask: np.ndarray      # [R, 6]
    aux: np.ndarray        # [R, 4]
    aux_mask: np.ndarray   # [R, 4]
    cropped: np.ndarray    # [R]

    def save(self, path):
        np.savez_compressed(path, **{f.name: getattr(self, f.name) for f in fields(self)})

    @classmethod
    def load(cls, path):
        z = np.load(path, allow_pickle=False)
        d = {f.name: z[f.name] for f in fields(cls)}
        d["name"], d["subject"], d["fake"] = str(d["name"]), str(d["subject"]), bool(d["fake"])
        return cls(**d)


def build(path, contract: InputContract, cache_dir=paths.DATA / "cache", log=print):
    """SessionData for one session, or None if the check says it can't be used (the reason is logged)."""
    path = Path(path)
    cache_dir = Path(cache_dir)
    cache = cache_dir / f"{path.name}_{contract.key()}_v{CODE_VERSION}.npz"
    meta = path / "meta.json"
    if cache.exists() and meta.exists() and cache.stat().st_mtime >= meta.stat().st_mtime:
        return SessionData.load(cache)
    report, p = check_and_process(path, contract)
    if not report["usable"]:
        why = "; ".join(f"{k}: {v['why']}" for k, v in report["can_train"].items() if not v["ok"])
        log(f"skip {path.name}: not usable ({why})")
        return None
    H, D, fm, cropped = rep_inputs(p, contract)
    R = len(p.reps)
    feats = np.stack([[r.duration_s / 3.0 for r in p.reps],
                      [min(x, 60.0) / 60.0 for x in rest_before(p.reps)]], 1).astype(np.float32)
    y = np.stack([p.targets[h] for h in HEADS], 1).astype(np.float32)
    ym = np.stack([p.masks[h] for h in HEADS], 1)
    data = SessionData(path.name, str(p.session.meta.get("subject")), "fake" in p.session.meta, H, D, fm, feats,
                       np.array([r.set_id for r in p.reps]), y, ym, p.aux.astype(np.float32), p.aux_mask, cropped)
    if R:
        cache_dir.mkdir(parents=True, exist_ok=True)
        data.save(cache)
    return data


def samples_of(data: SessionData, max_reps=MAX_REPS):
    """[(set index list)]: each set's reps, split into chunks of at most max_reps."""
    out = []
    for s in np.unique(data.set_id):
        idx = np.flatnonzero(data.set_id == s)
        out += [idx[i:i + max_reps] for i in range(0, len(idx), max_reps)]
    return out


class SetDataset(Dataset):
    """Torch dataset of sets. augment=True adds range shift (+-2 bins), gain (+-3 dB) and hides 10 % of frames,
    the same way for the set and its baseline reps."""

    def __init__(self, sessions, contract: InputContract, augment=False, seed=0):
        self.sessions = [s for s in sessions if s is not None and len(s.set_id) > N_BASE]
        self.items = [(k, idx) for k, s in enumerate(self.sessions) for idx in samples_of(s)]
        self.contract = contract
        self.augment = augment
        self.rng = np.random.default_rng(seed)

    def __len__(self):
        return len(self.items)

    def subjects(self):
        return sorted({s.subject for s in self.sessions})

    def _aug(self, H, D, fm):
        shift = int(self.rng.integers(-2, 3))
        if shift:
            H = np.roll(H, shift, axis=-2)
            D = np.roll(D, shift, axis=-2)
            sl = slice(0, shift) if shift > 0 else slice(shift, None)
            H[..., sl, :] = 0
            D[..., sl, :] = 0
        gain = self.rng.uniform(-3, 3) / self.contract.db_span
        on_h, on_d = H[..., 0, :, :] > 0, D > 0
        H[..., 0, :, :] = np.where(on_h, np.clip(H[..., 0, :, :] + gain, 0, 1), 0)
        D = np.where(on_d, np.clip(D + gain, 0, 1), 0)
        hide = self.rng.random(fm.shape) < 0.10
        fm = fm & ~hide
        H[~fm] = 0
        D[~fm] = 0
        return H, D, fm

    def __getitem__(self, i):
        k, idx = self.items[i]
        s = self.sessions[k]
        base = np.arange(min(N_BASE, len(s.set_id)))
        H = np.concatenate([s.H[idx], s.H[base]]).astype(np.float32)
        D = np.concatenate([s.D[idx], s.D[base]]).astype(np.float32)
        fm = np.concatenate([s.fmask[idx], s.fmask[base]])
        if self.augment:
            H, D, fm = self._aug(H, D, fm)
        n = len(idx)
        t = torch.from_numpy
        return {"H": t(H[:n]), "D": t(D[:n]), "fmask": t(fm[:n]), "feats": t(s.feats[idx]),
                "rmask": torch.ones(n, dtype=torch.bool),
                "base_H": t(H[n:]), "base_D": t(D[n:]), "base_fmask": t(fm[n:]), "base_feats": t(s.feats[base]),
                "base_rmask": torch.ones(len(base), dtype=torch.bool),
                "y": t(s.y[idx]), "ymask": t(s.ymask[idx]), "aux": t(s.aux[idx]), "aux_mask": t(s.aux_mask[idx]),
                "subject": s.subject}


def collate(items):
    """Pad the reps of a batch to the longest set (rmask marks real reps)."""
    out = {}
    for key in items[0]:
        if key == "subject":
            out[key] = [it[key] for it in items]
            continue
        vals = [it[key] for it in items]
        n = max(v.shape[0] for v in vals)
        pad = []
        for v in vals:
            extra = torch.zeros((n - v.shape[0],) + tuple(v.shape[1:]), dtype=v.dtype)
            pad.append(torch.cat([v, extra]))
        out[key] = torch.stack(pad)
    return out


def loso_splits(subjects):
    """Leave one subject out: [(test, val, train list)]; the validation person comes from the training group."""
    subjects = sorted(subjects)
    if len(subjects) < 3:
        raise ValueError(f"leave-one-subject-out needs at least 3 people, got {len(subjects)}")
    out = []
    for i, test in enumerate(subjects):
        val = subjects[(i + 1) % len(subjects)]
        out.append((test, val, [s for s in subjects if s not in (test, val)]))
    return out


def summary(sessions):
    rows = [s for s in sessions if s is not None]
    return {"sessions": len(rows), "subjects": sorted({s.subject for s in rows}),
            "reps": int(sum(len(s.set_id) for s in rows)),
            "cropped_reps": int(sum(s.cropped.sum() for s in rows)),
            "labels": {h: int(sum(s.ymask[:, k].sum() for s in rows)) for k, h in enumerate(HEADS)},
            "positives": {h: int(sum((s.y[:, k] * s.ymask[:, k]).sum() for s in rows))
                          for k, h in enumerate(HEADS) if h.startswith("comp") or h == "risk"},
            "aux": AUX}


def describe(sessions):
    return json.dumps(summary(sessions), indent=1)
