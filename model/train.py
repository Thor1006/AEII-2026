"""Train and test the radar-only network with leave-one-subject-out (LOSO).

  python train.py --fake 6                fake people (made once in model/data/fake_v<N>, N = the fake-data version): tests the code only
  python train.py --sessions DIR          real recorder sessions (only those that pass the session check)

Writes model/runs/<date>_<time>/: report.md (per person and mean, against the majority baseline),
results.json, dataset.json and one model file per fold. Runs on the Mac's Apple GPU when available.
FAKE DATA: good scores prove that the code works, never that the model works on real radar.
"""
import argparse
import datetime
import json
import re
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore", category=RuntimeWarning)

import numpy as np  # noqa: E402

from trnet import baseline_ridge as RB  # noqa: E402
from trnet import dataset as DS  # noqa: E402
from trnet import paths, synth  # noqa: E402
from trnet import training as TRN  # noqa: E402
from trnet.contract import default_contract  # noqa: E402
from trnet.network import count_params, HEADS, TrueRehabNet  # noqa: E402

CODE = re.compile(r"^(S|F)\d{2,3}$|^TEST$")
FEW_PEOPLE = 5          # below this, --val auto validates on sessions instead of a whole person


def to_codes(sessions):
    """Replace subject names with S01, S02 ... (sorted) unless they already are codes. Returns {name: code}."""
    names = sorted({s.subject for s in sessions})
    if all(CODE.match(n) for n in names):
        return {}
    codes = {n: f"S{i + 1:02d}" for i, n in enumerate(names)}
    for s in sessions:
        s.subject = codes[s.subject]
    return codes


def label_spread(sessions):
    """Per person and head: labelled reps, mean, std, min, max, and the mean spread inside one session."""
    out = {}
    for subj in sorted({s.subject for s in sessions}):
        ss = [s for s in sessions if s.subject == subj]
        for h in ("fatigue", "quality", "comp_rom"):
            k = HEADS.index(h)
            ys = [s.y[s.ymask[:, k], k] for s in ss]
            y = np.concatenate(ys)
            if not len(y):
                continue
            within = [float(v.std()) for v in ys if len(v) > 1]
            out.setdefault(subj, {})[h] = {"n": int(len(y)), "mean": float(y.mean()), "std": float(y.std()),
                                           "min": float(y.min()), "max": float(y.max()),
                                           "std_in_session": float(np.mean(within)) if within else None}
    return out


def fake_sessions(n_people, plan, root):
    root.mkdir(parents=True, exist_ok=True)
    have = sorted(p for p in root.iterdir() if (p / "meta.json").exists())
    if len({p.name.split("_")[2] for p in have}) >= n_people:
        return have
    print(f"making {n_people} fake people in {root} ...")
    return synth.make_dataset(root, n_people=n_people, plan=plan)


def write_report(out, results, summary, info):
    fake = info["fake"]
    lines = [f"# Training run {out.name}", ""]
    if fake:
        lines += ["> **FAKE DATA (trnet.synth).** These numbers show that the code runs end to end. They say nothing",
                  "> about how the model will do on real radar.", ""]
    lines += [f"- Data: {info['data']}", f"- People: {', '.join(info['dataset']['subjects'])}; "
              f"{info['dataset']['reps']} reps ({info['dataset']['cropped_reps']} cropped to "
              f"{info['frames_per_rep']} frames)", f"- Network: {info['params']:,} parameters, contract "
              f"{info['contract_version']} (key {info['contract_key']})", f"- Device: {info['device']}; "
              f"{info['epochs']} epochs max, patience {info['patience']}; {info['minutes']:.1f} min",
              f"- Validation (early stopping): {info['val_desc']}", "",
              "## Mean over the left-out people", "", "| Head | Model | Majority/mean baseline | Labelled reps |",
              "|---|---|---|---|"]
    for h, m in summary.items():
        if "mae" in m:
            lines.append(f"| {h} | MAE {m['mae']:.3f} | MAE {m['baseline_mae']:.3f} | {m['n']} |")
        elif m["macro_f1"] is None:
            lines.append(f"| {h} | - | - | {m['n']} ({m['positives']} positive: only one class, F1 not meaningful) |")
        else:
            lines.append(f"| {h} | macro-F1 {m['macro_f1']:.2f} | macro-F1 {m['baseline_macro_f1']:.2f} | "
                         f"{m['n']} ({m['positives']} positive) |")
    lines += ["", "Lower MAE is better; higher macro-F1 is better (0.5 = no better than guessing one class).", "",
              "## Per left-out person", "", "| Test | Val | Epochs | fatigue MAE | quality MAE |", "|---|---|---|---|---|"]
    for r in results:
        m = r["metrics"]
        f = f"{m['fatigue']['mae']:.3f}" if "fatigue" in m else "-"
        q = f"{m['quality']['mae']:.3f}" if "quality" in m else "-"
        lines.append(f"| {r['test']} | {r['val']} | {len(r['history'])} | {f} | {q} |")
    lines += ["", "## Labels: how much is there to learn", "",
              "Per person; `std in session` = mean spread of the label inside one session. A head whose labels barely",
              "vary can't beat the mean by much, whatever the model.", "",
              "| Person | Head | Reps | Mean | Std | Min | Max | Std in session |", "|---|---|---|---|---|---|---|---|"]
    for subj, heads in info["label_spread"].items():
        for h, v in heads.items():
            w = "-" if v["std_in_session"] is None else f"{v['std_in_session']:.3f}"
            lines.append(f"| {subj} | {h} | {v['n']} | {v['mean']:.3f} | {v['std']:.3f} | {v['min']:.3f} | "
                         f"{v['max']:.3f} | {w} |")
    lines += ["", "## Sanity model: ridge on a few hand-made numbers (same folds, same training sessions)", "",
              "`timing` = rep duration + rest (the duration comes from the IMU rep finder, not the radar); `radar` =",
              "3 range-Doppler motion numbers per rep; MAE on the left-out person, lower is better.", "",
              "| Test | Head | Mean baseline | Network | Ridge timing | Ridge radar | Ridge timing+radar |",
              "|---|---|---|---|---|---|---|"]
    for r in results:
        for h, v in r.get("ridge", {}).items():
            net = r["metrics"].get(h, {}).get("mae")
            net = "-" if net is None else f"{net:.3f}"
            lines.append(f"| {r['test']} | {h} | {v['baseline']:.3f} | {net} | {v['timing']:.3f} | "
                         f"{v['radar']:.3f} | {v['timing+radar']:.3f} |")
    lines += ["", f"With {len(results)} left-out people, differences of a few thousandths are not distinguishable",
              "from the baseline: read them as \"no better\", not as a gain."]
    (out / "report.md").write_text("\n".join(lines) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Train/test the radar-only network (leave one subject out).")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--fake", type=int, metavar="N", help="use N fake people (plumbing check only)")
    g.add_argument("--sessions", help="folder with real recorder sessions")
    ap.add_argument("--fake-sets", type=int, default=3)
    ap.add_argument("--fake-reps", type=int, default=8)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--patience", type=int, default=8)
    ap.add_argument("--device", default="auto", help="auto (Apple GPU if available), cpu or mps")
    ap.add_argument("--frames-per-rep", type=int, default=None, help="override T (quick runs only)")
    ap.add_argument("--no-points", action="store_true", help="leave out the point layers (to compare)")
    ap.add_argument("--angle-bins", type=int, choices=(16, 32, 64), help="angle grid (default: the contract's)")
    ap.add_argument("--max-folds", type=int, default=None)
    ap.add_argument("--val", choices=("auto", "person", "sessions"), default="auto",
                    help="early-stopping data: a whole other person, or each training person's last session; "
                         f"auto = sessions below {FEW_PEOPLE} people, else person")
    a = ap.parse_args(argv)

    over = {"frames_per_rep": a.frames_per_rep} if a.frames_per_rep else {}
    if a.no_points:
        over["use_points"] = False
    if a.angle_bins:
        over["angle_bins"] = a.angle_bins
    contract = default_contract(**over)
    if a.fake:
        plan = synth.Plan(sets=a.fake_sets, reps_per_set=a.fake_reps, set_rest_s=15.0)
        folders = fake_sessions(a.fake, plan, paths.FAKE)
        data_desc = f"{a.fake} fake people ({a.fake_sets} sets x {a.fake_reps} reps), model/data/{paths.FAKE.name}"
    else:
        root = Path(a.sessions)
        folders = sorted(p for p in root.iterdir() if (p / "meta.json").exists())
        data_desc = str(root)
    print(f"checking and loading {len(folders)} sessions ...")
    sessions = [DS.build(f, contract) for f in folders]
    usable = [s for s in sessions if s is not None]
    n_people = len({s.subject for s in usable})
    val = a.val if a.val != "auto" else ("sessions" if n_people < FEW_PEOPLE else "person")
    need = 3 if val == "person" else 2
    if n_people < need:
        raise SystemExit(f"need usable sessions from at least {need} people for --val {val}, have {n_people}")
    codes = to_codes(usable)
    if codes:
        print("subjects shown as codes (this list is not saved): "
              + ", ".join(f"{c} = {n}" for n, c in codes.items()))
    device = TRN.pick_device(a.device)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out = paths.RUNS / stamp
    out.mkdir(parents=True)
    info = {"data": data_desc, "fake": any(s.fake for s in usable), "dataset": DS.summary(usable),
            "frames_per_rep": contract.frames_per_rep, "params": count_params(TrueRehabNet(contract)),
            "contract_version": contract.version, "contract_key": contract.key(), "device": str(device),
            "epochs": a.epochs, "patience": a.patience, "val": val,
            "val_desc": ("a whole other person" if val == "person" else
                         "the last session of each training person (the test person is never used)"),
            "label_spread": label_spread(usable)}
    (out / "dataset.json").write_text(json.dumps(info["dataset"], indent=1))
    print(f"training on {device}: {info['dataset']['reps']} reps from {len(info['dataset']['subjects'])} people")
    t0 = time.time()
    results = TRN.run_loso(usable, contract, device, a.epochs, a.patience, out_dir=out, max_folds=a.max_folds,
                           val=val)
    folds = {f[0]: f for f in TRN.loso_folds(usable, val)}
    for r in results:
        _, _, tr_s, _, te_s = folds[r["test"]]
        r["ridge"] = RB.evaluate(tr_s, te_s, contract)
    info["minutes"] = (time.time() - t0) / 60
    summary = TRN.summarize(results)
    (out / "results.json").write_text(json.dumps({"info": info, "summary": summary, "folds": results}, indent=1))
    write_report(out, results, summary, info)
    print((out / "report.md").read_text())
    print(f"saved in {out}")


if __name__ == "__main__":
    main()
