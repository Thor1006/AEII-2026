"""Count elbow curls from the radar alone and score them against the IMU (the answer key).

  python armtrack.py --sessions /Volumes/PortableSSD/truerehab-sessions

No learning: nothing is trained, so no person is "left out"; the few fixed numbers in trnet/armtrack.py were chosen
on these same recordings (say so when you quote the result). Writes model/runs/arm_<date>_<time>/report.md and
results.json. People are shown as S01, S02 ... (the names are printed once on screen, never saved).
"""
import argparse
import datetime
import json
import re
import sys
import warnings
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore", category=RuntimeWarning)

from trnet import armtrack as AT  # noqa: E402
from trnet import paths  # noqa: E402
from trnet import pipeline as P  # noqa: E402
from trnet import truth as TR  # noqa: E402

CODE = re.compile(r"^(S|F)\d{2,3}$|^TEST$")


def session_result(folder):
    """(subject, row dict) or (subject, None, why) for one session folder."""
    p = P.process(folder)
    subj = str(p.session.meta.get("subject"))
    if p.radar is None:
        return subj, None, "no radar"
    if p.rep_source not in ("imu", "pose") or not p.reps:
        return subj, None, "no IMU/pose reps to score against"
    if p.radar.valid.mean() < 0.5:
        return subj, None, (f"only {p.radar.valid.mean():.0%} of radar frames arrived "
                            "(frame numbers jump; the session's radar can't be lined up)")
    tr = AT.track(p.radar)
    if tr is None:
        return subj, None, "under 10 s of radar frames"
    row = AT.score_reps(tr.reps, p.reps)
    v = p.radar.valid
    if p.rep_source == "imu":
        _, w = TR.forearm_flexion(p.imu)
        w = np.interp(p.radar.t_s, p.imu.t_s, w)
        row["velocity_corr"] = float(abs(np.corrcoef(tr.velocity[v], w[v])[0, 1]))
    row.update(range_m=round(tr.range_m, 2), frames_ok=float(v.mean()), rep_source=p.rep_source,
               imu_sync=(p.sync.get("imu") or {}).get("applied", False))
    return subj, row, None


def write_report(out, rows, skipped, total, data):
    f = lambda x, n=2: "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{n}f}"  # noqa: E731
    L = [f"# Radar arm tracking {out.name}", "",
         "Elbow curls counted from the radar alone (no learning, no wearable), scored against the IMU's reps.", "",
         f"- Data: {data}", "- A radar rep is **found** when its turning point is within "
         f"{AT.MATCH_S:.2f} s of an IMU turning point (top or bottom: Doppler can't tell which is the top).",
         "- **Chance** = the same radar reps moved by a random 1-10 s: what that rule gives with the rhythm kept but the "
         "timing lost.",
         "- The method's few fixed numbers were chosen on these same sessions; nothing was trained.", "",
         "## All sessions together", "",
         f"- IMU reps: {total['imu']}; radar reps: {total['radar']}; found: **{total['found']} "
         f"({total['found'] / total['imu']:.0%})**; extra radar reps: {total['radar'] - total['found']}",
         f"- Chance would find {total['chance'] / total['imu']:.0%}.",
         f"- Rep count within ±1 of the IMU in {total['within1']} of {total['n']} sessions.", "",
         "## Per person", "", "| Person | Sessions | IMU reps | Radar reps | Found | Chance |", "|---|---|---|---|---|---|"]
    for subj in sorted({r["subject"] for r in rows}):
        rs = [r for r in rows if r["subject"] == subj]
        imu = sum(r["imu_reps"] for r in rs)
        L.append(f"| {subj} | {len(rs)} | {imu} | {sum(r['radar_reps'] for r in rs)} | "
                 f"{sum(r['found'] for r in rs) / imu:.0%} | {sum(r['chance_share'] * r['imu_reps'] for r in rs) / imu:.0%} |")
    L += ["", "## Per session", "",
          "| Session | Person | Range (m) | Velocity vs IMU (abs corr) | IMU reps | Radar reps | Found | Chance (p95) "
          "| Rep interval radar / IMU (s) |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        iv = r["median_rep_interval_s"]
        L.append(f"| {r['session'][:17]} | {r['subject']} | {r['range_m']:.2f} | {f(r.get('velocity_corr'))} | "
                 f"{r['imu_reps']} | {r['radar_reps']} | {r['found_share']:.0%} | {r['chance_share']:.0%} "
                 f"({r['chance_p95_share']:.0%}) | {f(iv['radar'])} / {f(iv['imu'])} |")
    if skipped:
        L += ["", "## Left out", ""] + [f"- {name} ({subj}): {why}" for name, subj, why in skipped]
    L += ["", "## What this does not show", "",
          "- The elbow angle in degrees: Doppler measures speed toward the radar, so the arm signal has no unit.",
          "- Which turning point is the top of the curl (the sign); so no range of motion per rep either.",
          f"- Anything beyond these {len({r['subject'] for r in rows})} people, this room and this radar position "
          "(~1.7-2.0 m, facing the radar)."]
    (out / "report.md").write_text("\n".join(L) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sessions", required=True, help="folder with recorder sessions")
    a = ap.parse_args(argv)
    root = Path(a.sessions)
    folders = sorted(p for p in root.iterdir() if (p / "meta.json").exists())
    rows, skipped = [], []
    for folder in folders:
        subj, row, *why = session_result(folder)
        if row is None:
            skipped.append([folder.name, subj, why[0]])
        else:
            rows.append({"session": folder.name, "subject": subj, **row})
    scored = sorted({r["subject"] for r in rows})
    extra = sorted({s for _, s, _ in skipped} - set(scored))     # people with no scored session get later codes
    names = scored + extra
    codes = {} if all(CODE.match(n) for n in names) else {n: f"S{i + 1:02d}" for i, n in enumerate(names)}
    if codes:
        print("subjects shown as codes (this list is not saved): " + ", ".join(f"{c} = {n}" for n, c in codes.items()))
        for r in rows:
            r["session"] = r["session"].replace(f"_{r['subject']}_", f"_{codes[r['subject']]}_")
            r["subject"] = codes[r["subject"]]
        for s in skipped:
            s[0], s[1] = s[0].replace(f"_{s[1]}_", f"_{codes[s[1]]}_"), codes[s[1]]
    if not rows:
        raise SystemExit("no session could be scored")
    total = {"n": len(rows), "imu": sum(r["imu_reps"] for r in rows), "radar": sum(r["radar_reps"] for r in rows),
             "found": sum(r["found"] for r in rows), "chance": sum(r["chance_share"] * r["imu_reps"] for r in rows),
             "within1": sum(abs(r["count_error"]) <= 1 for r in rows)}
    out = paths.RUNS / ("arm_" + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    out.mkdir(parents=True)
    (out / "results.json").write_text(json.dumps({"total": total, "sessions": rows, "skipped": skipped}, indent=1))
    write_report(out, rows, skipped, total, str(root))
    print((out / "report.md").read_text())
    print(f"saved in {out}")


if __name__ == "__main__":
    main()
