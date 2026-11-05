"""Train and test the radar-only network with leave-one-subject-out (LOSO).

  python train.py --fake 6                fake people (made once in model/data/fake): tests the code only
  python train.py --sessions DIR          real recorder sessions (only those that pass the session check)

Writes model/runs/<date>_<time>/: report.md (per person and mean, against the majority baseline),
results.json, dataset.json and one model file per fold. Runs on the Mac's Apple GPU when available.
FAKE DATA: good scores prove that the code works, never that the model works on real radar.
"""
import argparse
import datetime
import json
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore", category=RuntimeWarning)

from trnet import dataset as DS  # noqa: E402
from trnet import paths, synth  # noqa: E402
from trnet import training as TRN  # noqa: E402
from trnet.contract import default_contract  # noqa: E402
from trnet.network import count_params, TrueRehabNet  # noqa: E402


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
              f"{info['epochs']} epochs max, patience {info['patience']}; {info['minutes']:.1f} min", "",
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
    ap.add_argument("--max-folds", type=int, default=None)
    a = ap.parse_args(argv)

    contract = default_contract(**({"frames_per_rep": a.frames_per_rep} if a.frames_per_rep else {}))
    if a.fake:
        plan = synth.Plan(sets=a.fake_sets, reps_per_set=a.fake_reps, set_rest_s=15.0)
        folders = fake_sessions(a.fake, plan, paths.DATA / "fake")
        data_desc = f"{a.fake} fake people ({a.fake_sets} sets x {a.fake_reps} reps), model/data/fake"
    else:
        root = Path(a.sessions)
        folders = sorted(p for p in root.iterdir() if (p / "meta.json").exists())
        data_desc = str(root)
    print(f"checking and loading {len(folders)} sessions ...")
    sessions = [DS.build(f, contract) for f in folders]
    usable = [s for s in sessions if s is not None]
    if len({s.subject for s in usable}) < 3:
        raise SystemExit(f"need usable sessions from at least 3 people, have {len({s.subject for s in usable})}")
    device = TRN.pick_device(a.device)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out = paths.RUNS / stamp
    out.mkdir(parents=True)
    info = {"data": data_desc, "fake": any(s.fake for s in usable), "dataset": DS.summary(usable),
            "frames_per_rep": contract.frames_per_rep, "params": count_params(TrueRehabNet(contract)),
            "contract_version": contract.version, "contract_key": contract.key(), "device": str(device),
            "epochs": a.epochs, "patience": a.patience}
    (out / "dataset.json").write_text(json.dumps(info["dataset"], indent=1))
    print(f"training on {device}: {info['dataset']['reps']} reps from {len(info['dataset']['subjects'])} people")
    t0 = time.time()
    results = TRN.run_loso(usable, contract, device, a.epochs, a.patience, out_dir=out, max_folds=a.max_folds)
    info["minutes"] = (time.time() - t0) / 60
    summary = TRN.summarize(results)
    (out / "results.json").write_text(json.dumps({"info": info, "summary": summary, "folds": results}, indent=1))
    write_report(out, results, summary, info)
    print((out / "report.md").read_text())
    print(f"saved in {out}")


if __name__ == "__main__":
    main()
