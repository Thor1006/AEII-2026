"""
Probe: FrameEncoder + one linear head on the sandbox's SIMULATED compensation
task (correct / shoulder elevation / trunk lean), leave-one-subject-out.
Compared against the sandbox SmallCNN and the majority-class baseline.

Run:   python3 sandbox/Encoder_0.1/encoder_probe.py
Reuses ../ml_example.py (data, training loop, LOSO) without editing it.

WARNING: synthetic data. This shows the encoder plugs into the pipeline and
trains; it says NOTHING about performance on real radar recordings.
"""
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # sandbox/
import ml_example as mx                                            # noqa: E402
from frame_encoder import FrameEncoder, FrameEncoderConfig, InputContract, count_params  # noqa: E402

SEED = 0


def main():
    d = mx.load_dataset()
    y, subj = d["y"], d["subj"]
    X = np.stack([mx.to_image(m, r) for m, r in zip(d["md"], d["rt"])])   # (N, 1, 76, 48)
    print(f"dataset: {len(y)} reps, {len(np.unique(subj))} subjects, input {X.shape[1:]}  [SYNTHETIC]")

    # Same image as SmallCNN uses, so the comparison is like-for-like.
    contract = InputContract(
        view="sandbox_md_rt_stacked",
        axes=("channel", "velocity_bin(64) | range_bin(12)", "time_step"),
        shape=X.shape[1:],
        notes="sandbox only: micro-Doppler (64 rows) stacked above range-time (12 rows), "
              "each normalised to its own peak with a -40 dB floor (ml_example.to_image)",
    )
    cfg = FrameEncoderConfig(in_channels=1)

    def make_probe():
        return nn.Sequential(FrameEncoder(cfg, contract), nn.Linear(cfg.embed_dim, 3))

    print(f"\nmajority-class baseline        LOSO macro-F1: "
          f"{mx.macro_f1(mx.confusion(y, np.zeros_like(y))):.2f}")

    rows = []
    for name, make in [("sandbox SmallCNN", mx.SmallCNN), ("FrameEncoder v0.1 + linear", make_probe)]:
        torch.manual_seed(SEED)
        np.random.seed(SEED)
        f1, cm = mx.loso(make, X, y, subj, epochs=40, aug=True)
        rows.append((name, f1, cm))
        print(f"{name:<30} LOSO macro-F1: {f1.mean():.2f} ± {f1.std():.2f}   "
              f"params {count_params(make()):,}   per subject: {np.round(f1, 2)}")

    for name, _, cm in rows:
        print(f"\nconfusion ({name}); rows = true, cols = predicted {mx.CLASSES}")
        print(cm)


if __name__ == "__main__":
    main()
