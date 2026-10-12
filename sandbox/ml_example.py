"""
Example ML pipeline on SIMULATED radar data (learning sandbox).

Task: classify each elbow-flexion rep as
    0 = correct form, 1 = shoulder elevation, 2 = trunk lean (compensation types)

Run:   python3 sandbox/ml_example.py
Needs numpy, matplotlib, torch. First run simulates the dataset (~1 min) and
caches it in sandbox/out/sim_dataset.npz.

WARNING: the data is synthetic, so the accuracy here says NOTHING about real
performance. The point is the workflow: features -> baseline -> CNN ->
leave-one-subject-out evaluation.
"""
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

import fmcw_chain as fc

OUT = Path(__file__).parent / "out"
CLASSES = ["correct", "shoulder elev.", "trunk lean"]
N_SUBJECTS, REPS_PER_CLASS = 8, 8
T_BINS = 48                   # every rep is resampled to 48 time steps
R_LO, R_HI = 0.4, 1.6         # range window that contains the subject [m]
SEED = 0


# =========================================================================
# 1. Dataset: simulate reps -> radar images + labels + subject id
# =========================================================================
def resample_time(img, n=T_BINS):
    """(rows, frames) -> (rows, n) by linear interpolation along time."""
    old = np.linspace(0, 1, img.shape[1])
    new = np.linspace(0, 1, n)
    return np.stack([np.interp(new, old, row) for row in img])


def rep_to_images(cube):
    """One rep's raw cube -> (micro-Doppler dB, range-time dB, static range profile)."""
    r = fc.range_fft(cube)
    rd = fc.doppler_fft(fc.remove_static(r))
    md = fc.micro_doppler(rd, R_LO, R_HI)                                   # (64, frames)

    bins = (fc.RANGE_AXIS >= R_LO) & (fc.RANGE_AXIS <= R_HI)
    mid = fc.N_LOOPS // 2
    moving = np.abs(rd[..., bins]) ** 2
    moving[:, mid - 1:mid + 2] = 0                                           # drop ~zero velocity
    rt = 10 * np.log10(moving.sum(axis=(1, 2)).T + 1e-12)                   # (range bins, frames)
    static = np.abs(r[..., bins]).mean(axis=(0, 1, 2))                       # where the body is
    return resample_time(md), resample_time(rt), static


def make_dataset():
    rng = np.random.default_rng(SEED)
    md_all, rt_all, static_all, y, subj = [], [], [], [], []
    for s in range(N_SUBJECTS):
        body = dict(dist=rng.uniform(0.9, 1.2), arm_x=rng.uniform(0.15, 0.22),
                    forearm=rng.uniform(0.24, 0.30))
        rom, period = rng.uniform(110, 145), rng.uniform(2.0, 3.2)
        for label in range(3):
            for _ in range(REPS_PER_CLASS):
                p = dict(body, rom_deg=rom * rng.uniform(0.92, 1.05),
                         rep_period=period * rng.uniform(0.9, 1.1),
                         breath_mm=rng.uniform(2, 5))
                if label == 0:     # correct, but nobody is perfectly still
                    p.update(shoulder_lift=rng.uniform(0, 0.006), trunk_lean_deg=rng.uniform(-1.5, 1.5))
                elif label == 1:   # shoulder elevation, from subtle to obvious
                    p.update(shoulder_lift=rng.uniform(0.015, 0.05), trunk_lean_deg=rng.uniform(-1.5, 1.5))
                else:              # trunk lean back
                    p.update(shoulder_lift=rng.uniform(0, 0.006), trunk_lean_deg=rng.uniform(4, 12))
                n_frames = int(np.ceil(p["rep_period"] / fc.FRAME_PERIOD))
                cube = fc.simulate(n_frames, single_antenna=True, rng=rng, **p)
                md, rt, st = rep_to_images(cube)
                md_all.append(md); rt_all.append(rt); static_all.append(st)
                y.append(label); subj.append(s)
        print(f"  simulated subject {s + 1}/{N_SUBJECTS}")
    return dict(md=np.array(md_all, np.float32), rt=np.array(rt_all, np.float32),
                static=np.array(static_all, np.float32), y=np.array(y), subj=np.array(subj))


def load_dataset():
    path = OUT / "sim_dataset.npz"
    if path.exists():
        return dict(np.load(path))
    OUT.mkdir(exist_ok=True)
    print("simulating dataset (cached afterwards)...")
    data = make_dataset()
    np.savez_compressed(path, **data)
    return data


# =========================================================================
# 2. Hand-crafted features (the baseline's input)
# =========================================================================
def features(md, rt, static):
    """A few physically meaningful numbers per rep."""
    v = fc.VEL_AXIS
    p = 10 ** (md / 10)
    p = p / p.sum()
    v_profile = p.sum(axis=1)                                 # energy per velocity bin
    strong = md > md.max() - 20                               # within 20 dB of the peak

    rng_axis = fc.RANGE_AXIS[(fc.RANGE_AXIS >= R_LO) & (fc.RANGE_AXIS <= R_HI)]
    body_r = rng_axis[np.argmax(static)]                      # subject distance
    q = 10 ** (rt / 10)
    r_profile = q.sum(axis=1) / q.sum()                       # moving energy per range bin
    r_centroid = (r_profile * rng_axis).sum()
    r_spread = np.sqrt((r_profile * (rng_axis - r_centroid) ** 2).sum())

    return np.array([
        -v[strong.any(axis=1)].min(),                         # fastest toward radar
        v[strong.any(axis=1)].max(),                          # fastest away
        (v_profile * np.abs(v)).sum(),                        # mean |velocity|
        v_profile[np.abs(v) < 0.3].sum(),                     # share of slow motion (trunk/shoulder)
        r_centroid - body_r,                                  # where the movement is, vs body
        r_spread,                                             # how spread out it is in range
        r_profile[rng_axis > body_r].sum(),                   # movement behind the body front
    ], np.float32)


FEATURE_NAMES = ["v_toward_max", "v_away_max", "mean_|v|", "slow_share",
                 "range_offset", "range_spread", "behind_share"]


# =========================================================================
# 3. Models
# =========================================================================
class LogReg(nn.Module):
    """Baseline: multinomial logistic regression = one linear layer + softmax."""
    def __init__(self, n_in, n_classes=3):
        super().__init__()
        self.fc = nn.Linear(n_in, n_classes)

    def forward(self, x):
        return self.fc(x)


class SmallCNN(nn.Module):
    """Small 2D CNN. Input: one image = micro-Doppler stacked on top of range-time."""
    def __init__(self, n_classes=3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.BatchNorm2d(16), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.AdaptiveAvgPool2d(1), nn.Flatten(),
            nn.Dropout(0.3), nn.Linear(64, n_classes),
        )

    def forward(self, x):
        return self.net(x)


def to_image(md, rt):
    """Normalise each part to [0, 1] relative to its own peak (-40 dB floor), then stack."""
    def norm(a):
        a = np.clip(a - a.max(), -40, 0)
        return (a + 40) / 40
    return np.concatenate([norm(md), norm(rt)], axis=0)[None]   # (1, 64 + range bins, 48)


def augment(x):
    """Cheap augmentation for spectrogram-like images: time shift + one time mask."""
    x = torch.roll(x, shifts=int(np.random.randint(-4, 5)), dims=-1)
    t0 = np.random.randint(0, x.shape[-1] - 6)
    x = x.clone()
    x[..., t0:t0 + np.random.randint(0, 6)] = 0
    return x


def train(model, Xtr, ytr, Xva, yva, *, epochs, lr=1e-3, wd=1e-2, batch=16, aug=False, patience=8):
    """AdamW + cosine LR + early stopping on the validation subject's loss."""
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=wd)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    counts = torch.bincount(ytr, minlength=3).float()
    loss_fn = nn.CrossEntropyLoss(weight=counts.sum() / (3 * counts.clamp(min=1)))  # class weights

    best, best_state, bad = np.inf, None, 0
    for _ in range(epochs):
        model.train()
        perm = torch.randperm(len(Xtr))
        for i in range(0, len(Xtr), batch):
            idx = perm[i:i + batch]
            xb = augment(Xtr[idx]) if aug else Xtr[idx]
            opt.zero_grad()
            loss = loss_fn(model(xb), ytr[idx])
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        sched.step()

        model.eval()
        with torch.no_grad():
            val = loss_fn(model(Xva), yva).item()
        if val < best - 1e-4:
            best, bad = val, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    model.load_state_dict(best_state)
    return model


# =========================================================================
# 4. Metrics + leave-one-subject-out evaluation
# =========================================================================
def confusion(y_true, y_pred, k=3):
    m = np.zeros((k, k), int)
    for t, p in zip(y_true, y_pred):
        m[t, p] += 1
    return m


def macro_f1(cm):
    tp = np.diag(cm)
    prec = tp / np.maximum(cm.sum(axis=0), 1)
    rec = tp / np.maximum(cm.sum(axis=1), 1)
    return np.mean(2 * prec * rec / np.maximum(prec + rec, 1e-12))


def loso(make_model, X, y, subj, *, epochs, standardize=False, aug=False):
    """Leave-one-subject-out. For each test subject, one OTHER subject is the
    validation set for early stopping, so the test subject is never peeked at."""
    cm_total = np.zeros((3, 3), int)
    f1s = []
    for test_s in np.unique(subj):
        train_subjects = [s for s in np.unique(subj) if s != test_s]
        val_s = train_subjects[test_s % len(train_subjects)]
        tr = (subj != test_s) & (subj != val_s)
        va, te = subj == val_s, subj == test_s

        Xtr, Xva, Xte = X[tr], X[va], X[te]
        if standardize:                           # fit the scaler on TRAIN only
            mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
            Xtr, Xva, Xte = (Xtr - mu) / sd, (Xva - mu) / sd, (Xte - mu) / sd

        t = lambda a: torch.tensor(a, dtype=torch.float32)
        model = train(make_model(), t(Xtr), torch.tensor(y[tr]), t(Xva), torch.tensor(y[va]),
                      epochs=epochs, aug=aug)
        model.eval()
        with torch.no_grad():
            pred = model(t(Xte)).argmax(1).numpy()
        cm = confusion(y[te], pred)
        cm_total += cm
        f1s.append(macro_f1(cm))
    return np.array(f1s), cm_total


# =========================================================================
# 5. Run everything
# =========================================================================
def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    d = load_dataset()
    y, subj = d["y"], d["subj"]
    print(f"dataset: {len(y)} reps, {len(np.unique(subj))} subjects, classes {np.bincount(y)}")

    # majority-class baseline: what "learning nothing" scores
    print(f"\nmajority-class baseline macro-F1: {macro_f1(confusion(y, np.zeros_like(y))):.2f}")

    # A) hand-crafted features + logistic regression
    F = np.stack([features(m, r, s) for m, r, s in zip(d["md"], d["rt"], d["static"])])
    f1_lr, cm_lr = loso(lambda: LogReg(F.shape[1]), F, y, subj, epochs=300, standardize=True)
    print(f"features + logistic regression  LOSO macro-F1: {f1_lr.mean():.2f} ± {f1_lr.std():.2f}"
          f"   per subject: {np.round(f1_lr, 2)}")

    # B) small CNN on the radar images
    X = np.stack([to_image(m, r) for m, r in zip(d["md"], d["rt"])])
    f1_cnn, cm_cnn = loso(SmallCNN, X, y, subj, epochs=40, aug=True)
    print(f"small CNN (AdamW)               LOSO macro-F1: {f1_cnn.mean():.2f} ± {f1_cnn.std():.2f}"
          f"   per subject: {np.round(f1_cnn, 2)}")

    # --- figure: one example input per class + both confusion matrices ------
    fig, ax = plt.subplots(1, 5, figsize=(20, 4))
    for k in range(3):
        i = np.where(y == k)[0][0]
        ax[k].imshow(X[i, 0], aspect="auto", origin="lower", cmap="viridis")
        ax[k].axhline(fc.N_LOOPS - 0.5, color="w", lw=1)
        ax[k].set(title=f"CNN input: {CLASSES[k]}", xlabel="time step",
                  ylabel="micro-Doppler (bottom) | range-time (top)")
    for a, cm, name in [(ax[3], cm_lr, "logistic regression"), (ax[4], cm_cnn, "CNN")]:
        a.imshow(cm, cmap="Blues")
        for (r, c), v in np.ndenumerate(cm):
            a.text(c, r, v, ha="center", va="center")
        a.set(title=f"LOSO confusion: {name}", xticks=range(3), yticks=range(3),
              xticklabels=CLASSES, yticklabels=CLASSES, xlabel="predicted", ylabel="true")
    fig.tight_layout()
    fig.savefig(OUT / "ml_example.png", dpi=110)
    print(f"saved {OUT / 'ml_example.png'}")


if __name__ == "__main__":
    main()
