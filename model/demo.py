"""Watch the network work on one fake person it never saw during training (FAKE DATA: plumbing only).

  python demo.py                 person F06, latest training run
  python demo.py --person F02    another left-out person (the fold where F02 was the test person)

Writes runs/demo/index.html (open it in a browser): the radar input frames as the network sees them,
the elbow angle, and after every rep the network's scores, the true labels and the recommendation.
"""
import argparse
import base64
import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import torch  # noqa: E402

from trnet import dataset as DS  # noqa: E402
from trnet import paths  # noqa: E402
from trnet import radar as R  # noqa: E402
from trnet.check import check_and_process  # noqa: E402
from trnet.network import HEADS, TrueRehabNet  # noqa: E402
from trnet.recommend import Advisor  # noqa: E402

FPS_OUT = 15          # frames per second in the page
MAX_RANGE = 40        # range bins shown (2.4 m)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--person", default="F06")
    ap.add_argument("--run", default=None, help="runs/<name> (default: newest with fold files)")
    a = ap.parse_args(argv)
    runs = sorted(p for p in paths.RUNS.iterdir() if list(p.glob("fold_*.pt")))
    run = paths.RUNS / a.run if a.run else runs[-1]
    weights = run / f"fold_{a.person}.pt"
    folder = next(p for p in sorted((paths.DATA / "fake").iterdir()) if f"_{a.person}_" in p.name)
    net = TrueRehabNet.load(weights).eval()
    c = net.contract
    report, p = check_and_process(folder, c)
    data = DS.build(folder, c)
    ds = DS.SetDataset([data], c)

    # network scores per rep (the GRU only looks back, so this is what it would say live after each rep)
    scores = [None] * len(p.reps)
    for n, (k, idx) in enumerate(ds.items):
        out = net.predict(DS.collate([ds[n]]))
        for j, r in enumerate(idx):
            scores[r] = {h: float(out[h][0, j]) for h in HEADS}
    adv, actions = Advisor(), []
    last_set = None
    for r, sc in zip(p.reps, scores):
        if r.set_id != last_set:
            adv.new_set()
            last_set = r.set_id
        actions.append(adv.feed(sc))

    # radar frames as the network sees them, thinned to FPS_OUT
    H, D, valid = R.to_inputs(p.radar)
    step = max(1, int(round(c.fps / FPS_OUT)))
    sel = np.arange(0, len(valid), step)
    mag = (H[sel, 0, :MAX_RANGE] * 255).astype(np.uint8)
    ph = ((H[sel, 1, :MAX_RANGE] + 1) * 127.5).astype(np.uint8)
    rd = (D[sel, 0, :MAX_RANGE] * 255).astype(np.uint8)
    t = p.radar.t_s[sel]

    truth = {h: [float(x) if m else None for x, m in zip(p.targets[h], p.masks[h])] for h in HEADS}
    payload = {
        "person": a.person, "run": run.name, "session": folder.name,
        "frames": len(sel), "range_bins": MAX_RANGE, "range_res": c.range_res_m, "t": np.round(t, 3).tolist(),
        "mag": base64.b64encode(mag.tobytes()).decode(), "phase": base64.b64encode(ph.tobytes()).decode(),
        "rd": base64.b64encode(rd.tobytes()).decode(),
        "angle_t": np.round(p.pose.t_s[::2], 3).tolist(),
        "angle": np.round(np.nan_to_num(p.pose.flexion_deg[::2]), 1).tolist(),
        "reps": [{"start": r.start_s, "end": r.end_s, "set": r.set_id, "rom": round(r.rom_deg)} for r in p.reps],
        "scores": scores, "truth": truth, "actions": [list(x) for x in actions],
        "params": sum(q.numel() for q in net.parameters()),
    }
    out_dir = paths.RUNS / "demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    html = (Path(__file__).parent / "demo_page.html").read_text().replace("__DATA__", json.dumps(payload))
    (out_dir / "index.html").write_text(html)
    print(f"wrote {out_dir / 'index.html'} ({(out_dir / 'index.html').stat().st_size // 1024} KB): "
          f"{len(p.reps)} reps, {len(sel)} frames, model {weights.relative_to(paths.MODEL_DIR)}")


if __name__ == "__main__":
    main()
