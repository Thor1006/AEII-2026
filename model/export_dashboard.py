"""Write a recording the dashboard (frontend/) can play: the network's radar input, scores, reps and advice.

  python export_dashboard.py                         fake person F06 (left out of training), newest model
  python export_dashboard.py --session <folder>      any recorder session that passes the session check
  python export_dashboard.py --session <folder> --radar-arm
                                                     reps counted by the radar alone (trnet.armtrack), with the radar's
                                                     arm signal and the IMU's elbow angle (the answer key) as charts;
                                                     the network's scores and advice are left out (not validated)

Writes model/runs/dashboard/<session>.ndjson (protocol 1.2, one message per line) and a copy in
frontend/public/replays/ so the dashboard can open it from a link:
  http://localhost:5173/?replay=/replays/<session>.ndjson     (after `npm run dev` in frontend/)
or with "Open a recording" on the dashboard's start screen. Fake sessions are marked synthetic, so the dashboard
shows its "Demo data" banner.
"""
import argparse
import base64
import json
import shutil
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

import re  # noqa: E402

import numpy as np  # noqa: E402

from trnet import armtrack as AT  # noqa: E402
from trnet import paths  # noqa: E402
from trnet import truth as TR  # noqa: E402
from trnet import radar as R  # noqa: E402
from trnet.inference import latest_weights, run_session  # noqa: E402

FPS = 15
MAX_RANGE_M = 2.4           # the maps stop at 2.4 m (the person stands at 1.0-1.6 m)
SCORES = [  # key, label (as in the dashboard's translation catalog), higher is worse, [warn, bad]
    ("fatigue", "Fatigue", True, [0.7, 0.85], "How tired the working muscle seems, learned from sEMG during training. Lower is better."),
    ("quality", "Movement quality", False, [0.2, 0.4], "Range, speed and smoothness compared with the first reps. Higher is better."),
    ("comp_shrug", "Shoulder shrug", True, [0.5, 0.75], "Chance that the shoulder is lifting to help. Lower is better."),
    ("comp_lean", "Trunk lean", True, [0.5, 0.75], "Chance that the trunk is leaning to help. Lower is better."),
    ("comp_rom", "Reduced range", True, [0.5, 0.75], "Chance that the range of motion has shrunk below 80 % of the first reps. Lower is better."),
    ("risk", "Risk in next reps", True, [0.6, 0.8], "Chance of compensation in the next 3 reps. Lower is better."),
]
ACTIONS = {"continue": "continue", "correct posture": "correct_posture", "reduce load or ROM": "reduce_load",
           "rest": "rest", "see physio": "see_physio"}
ACTION_INFO = [
    {"key": "continue", "label": "Continue", "hint": "Form looks good. Keep going.", "tone": "good"},
    {"key": "correct_posture", "label": "Correct posture", "hint": "Sit upright and keep the shoulder down.", "tone": "warn"},
    {"key": "reduce_load", "label": "Reduce load or range", "hint": "Use a lighter weight or a smaller range.", "tone": "warn"},
    {"key": "rest", "label": "Rest", "hint": "Take a break before the next set.", "tone": "bad"},
    {"key": "see_physio", "label": "See your physiotherapist", "hint": "The pattern keeps coming back. Get it checked.", "tone": "bad"},
]
COMP_PATTERN = {"comp_shrug": "shoulder_shrug", "comp_lean": "trunk_lean", "comp_rom": "reduced_rom"}


POINTS_HELP = ("What the network sees, part 3: the radar's own detected points of the last 0.25 s, by distance and "
               "direction, coloured by how high they are (metres above or below the radar). Empty cells stay 0.")


def b64(a):
    return base64.b64encode(np.ascontiguousarray(a, "<f4").tobytes()).decode()


def public_name(name, subject):
    """A session name safe to show: a subject that isn't a code (S01, F06, TEST) is replaced by 'anon'."""
    if not subject or re.match(r"^(S|F)\d{2,3}$|^TEST$", subject):
        return name
    return name.replace(f"_{subject}_", "_anon_")


def export(run, out_path, arm=None):
    """arm: a trnet.armtrack.ArmTrack -> reps from the radar, arm signal + IMU angle charts, no network scores."""
    p = run.processed
    rec = p.radar
    c = rec.contract
    H, D, valid = R.to_inputs(rec)
    step = max(1, int(round(c.fps / FPS)))
    sel = np.arange(0, len(valid), step)
    t0_s = float(rec.t_s[0])
    base_ms = int(time.time() * 1000) - int((rec.t_s[-1] - t0_s) * 1000) - 60_000
    T = lambda t: base_ms + int(round((t - t0_s) * 1000))  # noqa: E731
    rows = max(4, min(c.range_bins, int(round(MAX_RANGE_M / c.range_res_m))))
    span_m = rows * c.range_res_m
    vres = c.vel_res_ms
    half = c.angle_bins // 2
    ang = {"label": "Angle bin", "min": -half, "max": half - 1}
    rng_axis = {"label": "Range", "unit": "m", "min": 0, "max": round(span_m, 2)}
    meta = p.session.meta
    subject = str(meta.get("subject", ""))
    sid = public_name(p.name, subject)
    subject = subject if sid == p.name else "anon"
    session_info = {"id": sid, "state": "running", "exercise": meta.get("exercise", "elbow_flexion"),
                    "side": {"l": "left", "r": "right"}.get(getattr(p.pose, "side", ""), None),
                    "startedAt": T(t0_s), "userId": subject}
    A = c.angle_bins
    frames = [
        {"view": "range_azimuth", "label": "Where things are", "shape": [rows, A], "unit": "",
         "axes": {"x": ang, "y": rng_axis}, "layer": ("H", 0),
         "fps": FPS, "description": "What the network sees, part 1: everything reflecting the radar, by distance and direction. 0 = 40 dB below the strongest echo, 1 = the strongest."},
        {"view": "phase_change", "label": "Tiny motion", "shape": [rows, A], "unit": "×π rad",
         "axes": {"x": ang, "y": rng_axis}, "layer": ("H", 1),
         "fps": FPS, "description": "What the network sees, part 2: how far each spot moved since the last frame, down to a fraction of a millimetre. 0 = still or too faint to tell."},
        {"view": "range_doppler", "label": "Movement speed", "shape": [rows, c.doppler_bins], "unit": "",
         "axes": {"x": {"label": "Radial speed", "unit": "m/s", "min": round(-(c.doppler_bins // 2) * vres, 2),
                        "max": round((c.doppler_bins // 2 - 1) * vres, 2)}, "y": rng_axis}, "layer": ("D", 0),
         "fps": FPS, "description": f"What the network sees, part {3 + int(c.use_points)}: how fast things move toward or away from the radar. The middle column is still."},
    ]
    if c.use_points:
        frames.insert(2, {"view": "point_height", "label": "Points (height)", "shape": [rows, A], "unit": "m",
                          "axes": {"x": ang, "y": rng_axis}, "layer": ("H", 1 + int(c.use_phase)), "range": [-0.6, 0.6],
                          "fps": FPS, "description": POINTS_HELP})
    aux = ([{"key": "elbow_angle_deg", "label": "Elbow angle (°)", "unit": "°", "rateHz": FPS, "device": "pose"}]
           if p.pose is not None else [])
    if arm is not None:
        aux = [{"key": "radar_arm", "label": "Radar: arm movement (no unit)", "unit": "", "rateHz": FPS,
                "device": "radar"}]
        if p.imu is not None:
            aux.append({"key": "imu_elbow_deg", "label": "IMU elbow angle, answer key", "unit": "°", "rateHz": FPS,
                        "device": "imu"})
    manifest = {
        "frames": [{k: v for k, v in f.items() if k != "layer"} for f in frames],
        "scores": ([] if arm is not None else
                   [{"key": k, "label": lbl, "higherIsWorse": hiw, "thresholds": th, "description": d, "rateHz": 1}
                    for k, lbl, hiw, th, d in SCORES]),
        "aux": aux,
        "events": ["rep_start", "rep_end", "compensation", "recommendation", "session_start", "session_end"],
        "actions": ACTION_INFO, "commands": [], "statusIntervalMs": 1000,
    }
    msgs = []
    seq = [0]

    def add(t_s, msg):
        msg = {"v": 1, "seq": seq[0], "t": T(t_s), "src": "trnet-replay", "sessionId": sid, **msg}
        seq[0] += 1
        msgs.append(msg)

    hello = {"type": "hello", "v": 1, "seq": -1, "t": T(t0_s) - 1, "src": "trnet-replay", "protocol": "1.2",
             "device": {"name": "TrueRehab model replay", "kitId": "MODEL-REPLAY", "bridgeVersion": "trnet 0.1.0",
                        "firmware": {"model": run.weights.parent.name + "/" + run.weights.name, "contract": c.version}},
             "synthetic": run.fake, "auth": "none", "manifest": manifest, "session": session_info}
    add(t0_s, {"type": "event", "kind": "session_start", "data": {"session": session_info}})
    for k, i in enumerate(sel):
        t = float(rec.t_s[i])
        for f in frames:
            src, ch = f["layer"]
            data = (H if src == "H" else D)[i, ch, :rows]
            if f["view"] == "point_height":
                data = data * c.height_scale_m                      # metres above (+) or below (-) the radar
            add(t, {"type": "frame", "view": f["view"], "shape": f["shape"], "unit": f["unit"], "axes": f["axes"],
                    "frameIndex": int(rec.frame_no[i]), "data": b64(data), "encoding": "base64-f32"})
    if p.pose is not None:
        tt = np.arange(p.pose.t_s[0], p.pose.t_s[-1], 1 / FPS)
        ang = np.interp(tt, p.pose.t_s, np.nan_to_num(p.pose.flexion_deg))
        for t, a in zip(tt, ang):
            add(float(t), {"type": "aux", "channels": {"elbow_angle_deg": round(float(a), 1)}})
    if arm is not None:
        tt = np.arange(float(rec.t_s[0]), float(rec.t_s[-1]), 1 / FPS)
        ok = np.isfinite(arm.proxy)
        sig = np.interp(tt, rec.t_s[ok], arm.proxy[ok])
        imu = None
        if p.imu is not None:
            flex, _ = TR.forearm_flexion(p.imu)
            imu = np.interp(tt, p.imu.t_s, flex)
        for k, t in enumerate(tt):
            ch = {"radar_arm": round(float(sig[k]), 1)}
            if imu is not None:
                ch["imu_elbow_deg"] = round(float(imu[k]), 1)
            add(float(t), {"type": "aux", "channels": ch})
        for n, rep in enumerate(arm.reps):
            add(rep.start_s, {"type": "event", "kind": "rep_start", "data": {"rep": n + 1}})
            add(rep.end_s, {"type": "event", "kind": "rep_end", "data": {"rep": n + 1}})
    latest = None
    for n, (rep, sc, (action, why)) in enumerate(zip(run.reps, run.scores, run.actions)):
        if arm is not None:
            break
        add(rep.start_s, {"type": "event", "kind": "rep_start", "data": {"rep": n + 1}})
        end = {"rep": n + 1}
        if np.isfinite(rep.rom_deg):                  # reps found from the sEMG envelope have no angle
            end["romDeg"] = round(rep.rom_deg, 1)
        add(rep.end_s, {"type": "event", "kind": "rep_end", "data": end})
        if sc is None:
            continue
        latest = (rep.end_s, sc)
        for key, pattern in COMP_PATTERN.items():
            if sc[key] >= 0.5:
                add(rep.end_s, {"type": "event", "kind": "compensation", "label": pattern,
                                "data": {"pattern": pattern, "severity": round(sc[key], 3)}})
        add(rep.end_s, {"type": "event", "kind": "recommendation", "label": ACTIONS[action],
                        "data": {"action": ACTIONS[action], "reason": why}})
    # scores once per second: the latest rep's values (a live system publishes its latest result the same way)
    ends = [] if arm is not None else [(r.end_s, s) for r, s in zip(run.reps, run.scores) if s is not None]
    for t in np.arange(t0_s, float(rec.t_s[-1]), 1.0):
        done = [s for e, s in ends if e <= t]
        if done:
            add(float(t), {"type": "scores", "scores": {k: {"value": round(done[-1][k], 4)} for k, *_ in SCORES}})
        devices = {"radar": {"state": "ok", "label": "Fake radar (trnet.synth)" if run.fake else "Radar (AWR2944PEVM)"},
                   "model": {"state": "ok", "label": f"Network ({c.version})"}}
        if p.pose is not None:
            devices["pose"] = {"state": "ok", "label": "Camera pose (training only)"}
        if arm is not None:
            devices["model"] = {"state": "ok", "label": f"Radar rep counter (arm at {arm.range_m:.2f} m)"}
            if p.imu is not None:
                devices["imu"] = {"state": "ok", "label": "IMU (answer key only)"}
        msg = "Fake data replay" if run.fake else "Recorded session replay"
        if arm is not None:
            msg += ": reps counted by the radar alone"
        add(float(t), {"type": "status", "fps": FPS, "synthetic": run.fake, "devices": devices,
                       "session": session_info, "message": msg})
    end_info = {**session_info, "state": "stopped", "endedAt": T(float(rec.t_s[-1]))}
    add(float(rec.t_s[-1]), {"type": "event", "kind": "session_end", "data": {"session": end_info}})
    msgs.sort(key=lambda m: (m["t"], m["seq"]))
    for i, m in enumerate(msgs):          # numbered in time order, as a live sender would (gaps = lost messages)
        m["seq"] = i
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(json.dumps(hello, separators=(",", ":"), allow_nan=False) + "\n")
        for m in msgs:
            f.write(json.dumps(m, separators=(",", ":"), allow_nan=False) + "\n")   # NaN would break the browser
    return len(msgs) + 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Export a dashboard recording of the network running on a session.")
    ap.add_argument("--session", help="session folder (default: fake person --person)")
    ap.add_argument("--person", default="F06", help="fake person to use when no --session is given")
    ap.add_argument("--weights", help="model file (default: the newest fold trained without that person)")
    ap.add_argument("--radar-arm", action="store_true", help="reps counted by the radar alone; no network scores")
    a = ap.parse_args(argv)
    if a.session:
        folder = Path(a.session)
        person = None
    else:
        folder = next(p for p in sorted(paths.FAKE.iterdir()) if f"_{a.person}_" in p.name)
        person = a.person
    weights = Path(a.weights) if a.weights else latest_weights(person)
    run = run_session(folder, weights)
    if not run.report["usable"]:
        raise SystemExit(f"{folder.name} can't be used (see check_session.py): no export")
    arm = None
    if a.radar_arm:
        arm = AT.track(run.processed.radar)
        if arm is None:
            raise SystemExit(f"{folder.name}: too few radar frames to count reps")
    name = public_name(folder.name, str(run.processed.session.meta.get("subject", "")))
    out = paths.RUNS / "dashboard" / (f"{name}_radar-arm.ndjson" if arm is not None else f"{name}.ndjson")
    n = export(run, out, arm)
    pub = paths.REPO / "frontend" / "public" / "replays"
    pub.mkdir(parents=True, exist_ok=True)
    shutil.copy(out, pub / out.name)
    print(f"wrote {out} ({out.stat().st_size // 1024} KB, {n} messages; model {weights.parent.name}/{weights.name})")
    print(f"open: http://localhost:5173/?replay=/replays/{out.name}   (npm run dev in frontend/)")


if __name__ == "__main__":
    main()
