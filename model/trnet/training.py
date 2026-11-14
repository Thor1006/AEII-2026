"""Loss, metrics, one training fold and leave-one-subject-out (LOSO) evaluation.

Loss: smooth-L1 (Huber scaled so its pull matches the flags) on fatigue and quality (scores 0..1), binary
cross-entropy on the 3 compensation flags and the next-rep risk (extra weight on the rarer positives, at most
5x), smooth-L1 on the training-only extra head (weight 0.5). Every head starts at its training average.
Labels that couldn't be measured are left out (masked), never counted as 0.
"""
import copy
import time

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from .dataset import SetDataset, collate, loso_splits, session_val_splits
from .network import HEADS, TrueRehabNet

REGRESSION = ("fatigue", "quality")
FLAGS = ("comp_shrug", "comp_lean", "comp_rom", "risk")
AUX_WEIGHT = 0.5
TO_DEVICE = ("H", "D", "fmask", "feats", "rmask", "base_H", "base_D", "base_fmask", "base_feats", "base_rmask",
             "y", "ymask", "aux", "aux_mask")


def pick_device(name="auto"):
    if name != "auto":
        return torch.device(name)
    return torch.device("mps" if torch.backends.mps.is_available() else "cpu")


def to_device(batch, device):
    return {k: (v.to(device) if k in TO_DEVICE else v) for k, v in batch.items()}


def pos_weights(ds: SetDataset):
    """Per flag: negatives/positives in the training labels (1 .. 10)."""
    w = {}
    for h in FLAGS:
        k = HEADS.index(h)
        y = np.concatenate([s.y[:, k][s.ymask[:, k]] for s in ds.sessions]) if ds.sessions else np.zeros(0)
        pos = float(y.sum())
        w[h] = float(np.clip((len(y) - pos) / pos, 1.0, 5.0)) if pos else 1.0
    return w


def loss_fn(out, batch, pw):
    rm = batch["rmask"]
    parts = {}
    for k, h in enumerate(HEADS):
        m = batch["ymask"][..., k] & rm
        if not m.any():
            continue
        y = batch["y"][..., k][m]
        logit = out[h][m]
        if h in REGRESSION:
            parts[h] = F.smooth_l1_loss(torch.sigmoid(logit), y, beta=0.1)
        else:
            parts[h] = F.binary_cross_entropy_with_logits(logit, y, pos_weight=torch.tensor(pw.get(h, 1.0),
                                                                                         device=logit.device))
    am = batch["aux_mask"] & rm.unsqueeze(-1)
    if am.any():
        parts["aux"] = AUX_WEIGHT * F.smooth_l1_loss(out["aux"][am], batch["aux"][am], beta=0.1)
    total = sum(parts.values()) if parts else torch.zeros((), device=rm.device)
    return total, {k: float(v.detach()) for k, v in parts.items()}


@torch.no_grad()
def predict_all(model, ds, device, batch_size=2):
    """Per head: (prediction 0..1, target, mask) over every real rep in the dataset."""
    model.eval()
    acc = {h: ([], [], []) for h in HEADS}
    for batch in DataLoader(ds, batch_size=batch_size, collate_fn=collate):
        b = to_device(batch, device)
        out = model(b)
        rm = b["rmask"]
        for k, h in enumerate(HEADS):
            acc[h][0].append(torch.sigmoid(out[h])[rm].cpu().numpy())
            acc[h][1].append(b["y"][..., k][rm].cpu().numpy())
            acc[h][2].append(b["ymask"][..., k][rm].cpu().numpy())
    return {h: tuple(np.concatenate(v) for v in acc[h]) for h in HEADS}


def macro_f1(pred, y):
    f1s = []
    for c in (0, 1):
        tp = np.sum((pred == c) & (y == c))
        fp = np.sum((pred == c) & (y != c))
        fn = np.sum((pred != c) & (y == c))
        f1s.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 1.0)
    return float(np.mean(f1s))


def metrics(preds, train_ds):
    """MAE for fatigue/quality, macro-F1 for flags; with the majority/mean baseline from the training labels."""
    res = {}
    for k, h in enumerate(HEADS):
        p, y, m = preds[h]
        if not m.any():
            continue
        p, y = p[m], y[m]
        ytr = np.concatenate([s.y[:, k][s.ymask[:, k]] for s in train_ds.sessions])
        if h in REGRESSION:
            res[h] = {"mae": float(np.abs(p - y).mean()), "baseline_mae": float(np.abs(ytr.mean() - y).mean()),
                      "n": int(m.sum())}
        else:
            maj = float(ytr.mean() >= 0.5)
            one_class = y.min() == y.max()          # F1 means nothing when the test person has only one class
            res[h] = {"macro_f1": None if one_class else macro_f1(p >= 0.5, y >= 0.5),
                      "baseline_macro_f1": None if one_class else macro_f1(np.full(len(y), maj) >= 0.5, y >= 0.5),
                      "n": int(m.sum()), "positives": int(y.sum())}
    return res


def init_heads(model, ds):
    """Start every head at its training average (logit of the mean), so training begins at the baseline."""
    with torch.no_grad():
        for k, h in enumerate(HEADS):
            y = np.concatenate([s.y[:, k][s.ymask[:, k]] for s in ds.sessions])
            if len(y):
                p = float(np.clip(y.mean(), 0.02, 0.98))
                model.heads.bias[k] = float(np.log(p / (1 - p)))
        for j in range(model.aux.bias.shape[0]):
            a = np.concatenate([s.aux[:, j][s.aux_mask[:, j]] for s in ds.sessions])
            if len(a):
                model.aux.bias[j] = float(a.mean())


def train_fold(train_ds, val_ds, contract, device, epochs=40, patience=8, lr=1e-3, batch_size=2, log=print,
               seed=0):
    torch.manual_seed(seed)
    model = TrueRehabNet(contract)
    init_heads(model, train_ds)
    model = model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-2)
    pw = pos_weights(train_ds)
    gen = torch.Generator().manual_seed(seed)
    loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, collate_fn=collate, generator=gen)
    best, best_state, wait, history = float("inf"), None, 0, []
    for ep in range(epochs):
        model.train()
        t0, tl = time.time(), []
        for batch in loader:
            b = to_device(batch, device)
            loss, _ = loss_fn(model(b), b, pw)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            tl.append(float(loss.detach()))   # a number for the log; the graph is not needed
        vl = evaluate_loss(model, val_ds, device, pw)
        history.append({"epoch": ep + 1, "train_loss": float(np.mean(tl)), "val_loss": vl,
                        "seconds": round(time.time() - t0, 1)})
        log(f"    epoch {ep + 1:2d}  train {np.mean(tl):.4f}  val {vl:.4f}  ({time.time() - t0:.1f} s)")
        if vl < best - 1e-4:
            best, best_state, wait = vl, copy.deepcopy(model.state_dict()), 0
        else:
            wait += 1
            if wait >= patience:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    return model, history


@torch.no_grad()
def evaluate_loss(model, ds, device, pw):
    model.eval()
    losses = [float(loss_fn(model(b), b, pw)[0]) for b in
              (to_device(x, device) for x in DataLoader(ds, batch_size=2, collate_fn=collate))]
    return float(np.mean(losses)) if losses else float("nan")


def loso_folds(sessions, val="person"):
    """[(test subject, val label, train sessions, val sessions, test sessions)].

    val="person": a whole other person validates (early stopping), the rest train (loso_splits).
    val="sessions": every other person trains, minus their last session, which validates
    (session_val_splits; for few people, where a whole validation person leaves too few to train on)."""
    usable = [s for s in sessions if s is not None]
    folds = []
    if val == "person":
        for test, v, train in loso_splits(sorted({s.subject for s in usable})):
            folds.append((test, v, [s for s in usable if s.subject in train],
                          [s for s in usable if s.subject == v], [s for s in usable if s.subject == test]))
    elif val == "sessions":
        for test, vn, tn in session_val_splits(usable):
            folds.append((test, "last session of " + ", ".join(sorted({s.subject for s in usable if s.name in vn})),
                          [s for s in usable if s.name in tn], [s for s in usable if s.name in vn],
                          [s for s in usable if s.subject == test]))
    else:
        raise ValueError(f"val must be 'person' or 'sessions', got {val!r}")
    return folds


def run_loso(sessions, contract, device, epochs=40, patience=8, out_dir=None, log=print, max_folds=None,
             val="person"):
    folds = loso_folds(sessions, val)
    folds = folds[:max_folds] if max_folds else folds
    results = []
    for test, val_label, tr_s, va_s, te_s in folds:
        train = sorted({s.subject for s in tr_s})
        log(f"  fold: test {test}, validate {val_label}, train {', '.join(train)}")
        tr, va, te = SetDataset(tr_s, contract, augment=True), SetDataset(va_s, contract), SetDataset(te_s, contract)
        model, hist = train_fold(tr, va, contract, device, epochs, patience, log=log)
        m = metrics(predict_all(model, te, device), tr)
        results.append({"test": test, "val": val_label, "val_sessions": [s.name for s in va_s], "train": train,
                        "metrics": m, "history": hist})
        if out_dir is not None:
            model.to("cpu").save(out_dir / f"fold_{test}.pt", extra={"test": test, "val": val_label})
    return results


def summarize(results):
    """Mean over folds per head and metric."""
    out = {}
    for r in results:
        for h, m in r["metrics"].items():
            for k, v in m.items():
                out.setdefault(h, {}).setdefault(k, []).append(v)
    def mean(v):
        v = [x for x in v if x is not None]
        return float(np.mean(v)) if v else None
    return {h: {k: (mean(v) if "f1" in k or "mae" in k else int(np.sum(v))) for k, v in d.items()}
            for h, d in out.items()}
