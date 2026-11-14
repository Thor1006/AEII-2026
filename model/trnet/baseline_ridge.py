"""A tiny sanity model next to the network: ridge regression on a few hand-made numbers per rep.

If even this beats the mean baseline on a left-out person, the radar input carries the information and the big
network is the problem (too many parameters for the data). If it doesn't, more people are needed first.

Per rep, from the range-Doppler input D (moving cells only, 0.3-3 m):
  radar:  peak and mean of the strongest moving cell per frame, and the share of frames above the session's median;
          each minus the session's first 3 reps (the same personal baseline the labels use).
  timing: the same 2 numbers the network gets (rep duration, rest before). Duration comes from the rep finder
          (IMU), so "timing" alone shows how much is explained without the radar at all.
numpy only.
"""
import numpy as np

from .contract import InputContract
from .dataset import N_BASE
from .network import HEADS

REGRESSION = ("fatigue", "quality")
SETS = {"timing": ("timing",), "radar": ("radar",), "timing+radar": ("timing", "radar")}


def rep_features(s, contract: InputContract, r_min_m=0.3, r_max_m=3.0):
    """{"radar": [R, 3], "timing": [R, 2]} for one SessionData."""
    D = s.D[:, :, 0].astype(np.float32)                         # [R, T, range, doppler], 0..1, 0 where missing
    mid = D.shape[-1] // 2
    moving = np.delete(D, [mid - 1, mid, mid + 1], axis=-1)
    lo, hi = int(r_min_m / contract.range_res_m), min(int(r_max_m / contract.range_res_m) + 1, D.shape[-2])
    e = moving[:, :, lo:hi].max(axis=(2, 3))                    # [R, T]
    e = np.where(s.fmask, e, np.nan)
    med = np.nanmedian(e)
    with np.errstate(all="ignore"):
        radar = np.stack([np.nanmax(e, 1), np.nanmean(e, 1), np.nanmean(e > med, 1)], 1)
    radar = np.nan_to_num(radar)
    radar = radar - radar[:N_BASE].mean(0)
    return {"radar": radar, "timing": s.feats.astype(np.float32)}


def _stack(sessions, contract, k, which):
    X, y = [], []
    for s in sessions:
        f = rep_features(s, contract)
        m = s.ymask[:, k]
        X.append(np.hstack([f[w] for w in which])[m])
        y.append(s.y[m, k])
    return np.vstack(X), np.concatenate(y)


def ridge_fit_predict(Xtr, ytr, Xte, lam=1.0):
    """Ridge on standardized features (statistics from the training rows only), predictions clipped to 0..1."""
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
    A, B = (Xtr - mu) / sd, (Xte - mu) / sd
    w = np.linalg.solve(A.T @ A + lam * len(A) * np.eye(A.shape[1]), A.T @ (ytr - ytr.mean()))
    return np.clip(B @ w + ytr.mean(), 0, 1)


def evaluate(train_sessions, test_sessions, contract, lam=1.0):
    """{head: {"baseline": MAE, "timing": MAE, "radar": MAE, "timing+radar": MAE, "n": reps}} on the test person."""
    keep = lambda ss: [s for s in ss if s is not None and len(s.set_id) > N_BASE]  # noqa: E731  (as SetDataset)
    tr, te = keep(train_sessions), keep(test_sessions)
    out = {}
    for h in REGRESSION:
        k = HEADS.index(h)
        res = {}
        for name, which in SETS.items():
            Xtr, ytr = _stack(tr, contract, k, which)
            Xte, yte = _stack(te, contract, k, which)
            if not len(ytr) or not len(yte):
                break
            res[name] = float(np.abs(ridge_fit_predict(Xtr, ytr, Xte, lam) - yte).mean())
            res["baseline"] = float(np.abs(ytr.mean() - yte).mean())
            res["n"] = int(len(yte))
        if res:
            out[h] = res
    return out
