"""Run a trained network over one session the way it would run live: after every rep it scores that rep using only
the reps before it (the GRU only looks back), and the rules turn the scores into advice. Used by demo.py and
export_dashboard.py."""
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import dataset as DS
from . import paths
from .check import check_and_process
from .network import HEADS, TrueRehabNet
from .recommend import Advisor


@dataclass
class SessionRun:
    folder: Path
    weights: Path
    net: TrueRehabNet
    processed: object                       # pipeline.Processed
    scores: list = field(default_factory=list)    # per rep: {head: 0..1}
    actions: list = field(default_factory=list)   # per rep: (action, reason)
    report: dict = field(default_factory=dict)    # the session check

    @property
    def reps(self):
        return self.processed.reps

    @property
    def fake(self):
        return "fake" in self.processed.session.meta


def latest_weights(person=None, run=None):
    """The fold model that was trained WITHOUT `person` (newest run with fold files), or the run's first fold."""
    runs = sorted(p for p in paths.RUNS.iterdir() if list(p.glob("fold_*.pt")))
    if not runs:
        raise FileNotFoundError("no trained model yet: run `python train.py --fake 6` first")
    folder = paths.RUNS / run if run else runs[-1]
    if person and (folder / f"fold_{person}.pt").exists():
        return folder / f"fold_{person}.pt"
    return sorted(folder.glob("fold_*.pt"))[0]


def run_session(folder, weights):
    net = TrueRehabNet.load(weights).eval()
    report, p = check_and_process(folder, net.contract)
    out = SessionRun(Path(folder), Path(weights), net, p, report=report)
    if not report["usable"]:
        return out
    data = DS.build(folder, net.contract)
    ds = DS.SetDataset([data], net.contract)
    out.scores = [None] * len(p.reps)
    for n, (_, idx) in enumerate(ds.items):
        pred = net.predict(DS.collate([ds[n]]))
        for j, r in enumerate(idx):
            out.scores[r] = {h: float(pred[h][0, j]) for h in HEADS}
    adv, last_set = Advisor(), None
    for r, sc in zip(p.reps, out.scores):
        if sc is None:            # reps that weren't in any sample (too few reps in the session)
            out.actions.append(("continue", "no score"))
            continue
        if r.set_id != last_set:
            adv.new_set()
            last_set = r.set_id
        out.actions.append(adv.feed(sc))
    return out
