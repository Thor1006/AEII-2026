"""Session check: is a recording usable for training, and what's wrong with it if not?

Run it straight after every recording (model/check_session.py). It never changes the session folder.
Levels: ok, info, warn (usable, but look at it), fail (this part can't be used).
"""
import re

import numpy as np

from . import calibrate as CB
from . import pipeline as PL
from . import radar as R
from . import sync as SY
from . import truth as TR

CODE_RE = re.compile(r"^(S\d{2,3}|TEST)$")
FAKE_CODE_RE = re.compile(r"^F\d{2,3}$")
TEMP_WARN_C = 85.0
EXPECTED = {"emg": ("E", 1000.0), "imu": ("I", 200.0)}
STATUS_KEYS = ("skipped", "i2c_err", "saturated", "recoveries", "frozen", "link_dropped")


class Report:
    def __init__(self, name):
        self.name = name
        self.items = []
        self.numbers = {}

    def add(self, section, level, text):
        self.items.append({"section": section, "level": level, "text": text})

    def levels(self, level):
        return [i for i in self.items if i["level"] == level]


def _status_counts(comments):
    """Board counters from the last '# status ...' line."""
    last = [txt for _, txt in comments if txt.startswith("# status")]
    if not last:
        return {}
    kv = dict(p.split("=", 1) for p in last[-1][2:].split() if "=" in p)
    return {k: kv[k] for k in STATUS_KEYS if k in kv}


def _device_rate(dev_us):
    """-> (Hz, number of gaps, samples lost) from the device's own clock."""
    steps = np.diff(np.asarray(dev_us, np.int64))
    step = float(np.median(steps))
    gaps = steps[steps > 1.5 * step]
    return 1e6 / step, len(gaps), int(np.round((gaps - step) / step).sum())


def _gaps_text(n_gaps, lost, hz):
    if not n_gaps:
        return ", no gaps"
    return f", {n_gaps} gap{'s' if n_gaps > 1 else ''} ({lost} sample{'s' if lost != 1 else ''} = {lost / hz:.2f} s lost)"


def check_session(path, contract=None):
    """The check report (a dict) for one session folder."""
    return check_and_process(path, contract)[0]


def check_and_process(path, contract=None):
    """(report, Processed or None): the dataset reuses the processed session instead of loading it twice."""
    from rec import session as S
    try:
        s = S.load(path)
    except (ValueError, FileNotFoundError, KeyError) as e:
        rep = Report(getattr(path, "name", str(path)))
        rep.add("session", "fail", f"not a recorder session: {e}")
        return _finish(rep, None), None
    rep = Report(s.dir.name)
    meta, src = s.meta, s.meta.get("sources", {})
    fake = "fake" in meta
    try:
        stats = CB.load_stats()
    except (FileNotFoundError, ValueError):
        stats = {}

    # ---------------------------------------------------------- session, privacy, safety
    rep.add("session", "info", f"subject {meta.get('subject')}, exercise {meta.get('exercise')}, "
                               f"{meta.get('duration_s', 0):.0f} s, sensors: {', '.join(src) or 'none'}"
                               + (f'; notes: "{meta["notes"]}"' if meta.get("notes") else ""))
    if fake:
        rep.add("session", "warn", "FAKE data from trnet.synth: tests the code only, never the model")
    subj = str(meta.get("subject", ""))
    if CODE_RE.match(subj) or (fake and FAKE_CODE_RE.match(subj)):
        rep.add("privacy", "ok", f"subject is a code ({subj})")
    else:
        rep.add("privacy", "warn", f'subject "{subj}" does not look like a code (S01, S02 ...): never use names')
    if (src.get("pose") or {}).get("raw_video") or (s.dir / "video.mp4").exists():
        rep.add("privacy", "warn", "raw video was saved: only with the person's written consent")
    elif "pose" in src:
        rep.add("privacy", "ok", "no raw video saved")
    port = str((src.get("emg") or {}).get("port", ""))
    if port and not port.startswith("tcp://") and "TrueRehab" not in port and subj != "TEST":
        rep.add("safety", "warn", f"sEMG came over a cable ({port}) with subject {subj}: SparkFun says the MyoWare "
                                  "shield must not be on a person while USB is plugged in (use battery + Bluetooth)")

    # ---------------------------------------------------------- files and line formats
    for name in src:
        if name == "radar":
            missing = [f for f in ("radar.bin", "radar_index.csv") if not (s.dir / f).exists()]
        else:
            missing = [f"{name}.csv"] if not (s.dir / f"{name}.csv").exists() else []
        if missing:
            rep.add("files", "fail", f"{name}: missing {', '.join(missing)}")
    for name, (tag, _) in EXPECTED.items():
        if name not in src:
            continue
        tags = TR.line_tags(s, name)
        if tags is None:
            continue
        other = "I" if tag == "E" else "E"
        if tags[tag] == 0 and tags[other] > 0:
            rep.add("files", "fail", f"{name}.csv holds {other}, lines (an {'IMU' if other == 'I' else 'sEMG'}), "
                                     f"not {tag}, lines: it can't be used as {name}")
        elif tags[tag] == 0:
            rep.add("files", "fail", f"{name}.csv has no {tag}, data lines")
        else:
            rep.add("files", "ok", f"{name}.csv: {tags[tag]} {tag}, lines" +
                    (f", {tags['other']} unreadable" if tags["other"] else ""))
    from .calibrate import is_simulated
    for name in src:
        if is_simulated(s, name):
            rep.add("files", "warn", f"{name}: simulated data (firmware or recorder test mode), not a real sensor")

    # ---------------------------------------------------------- the pipeline (radar, ground truth, sync, reps)
    p = PL.process(s.dir, contract)

    rec = p.radar
    if "radar" in src and rec is None:
        rep.add("radar", "fail", "radar listed but no frames could be read")
    if rec is not None:
        n, miss = int(rec.valid.sum()), int((~rec.valid).sum())
        longest = 0
        run = 0
        for v in rec.valid:
            run = 0 if v else run + 1
            longest = max(longest, run)
        rep.numbers["radar"] = {"frames": n, "fps": round(rec.fps, 2), "missing": miss}
        lvl = "ok" if miss == 0 else "warn"
        rep.add("radar", lvl, f"{n} frames, {rec.fps:.2f} fps, {miss} missing"
                + (f" (longest gap {longest / rec.contract.fps:.2f} s; masked, never filled in)" if miss else ""))
        for prob in rec.problems[:3]:
            rep.add("radar", "warn", prob)
        t_max = np.nanmax(rec.temp_c) if np.isfinite(rec.temp_c).any() else np.nan
        if np.isfinite(t_max):
            rep.add("radar", "warn" if t_max >= TEMP_WARN_C else "ok", f"hottest sensor {t_max:.0f} C"
                    + (" (the browser viewer stops at 85 C)" if t_max >= TEMP_WARN_C else ""))
        e = R.motion_energy(rec)
        thr = (stats.get("radar") or {}).get("motion_energy_db_p50_p99", [None, 25.0])[1]
        share = float(np.nanmean(e > thr))
        rep.numbers["radar"]["moving_share"] = round(share, 3)
        if share > 0.05:
            rep.add("radar", "ok", f"movement in front in {share:.0%} of frames")
        else:
            rep.add("radar", "warn", f"no movement seen in front ({share:.1%} of frames above the empty-room level)"
                                     " - was anybody there?")
        jit = (rec.arrival_s - rec.t_s)[rec.valid] * 1000
        rep.add("radar", "info", f"delivery after the fitted frame clock: median {np.median(jit):.1f} ms, "
                                 f"p99 {np.percentile(jit, 99):.1f} ms")

    applied = {k: (v["offset_ms"] / 1000 if v.get("applied") else 0.0) for k, v in p.sync.items() if k != "radar"}
    if p.imu is not None:
        imu = p.imu
        hz, n_gaps, lost = _device_rate(imu.dev_us)
        status = _status_counts(TR.comment_lines(s, "imu"))
        bad = {k: v for k, v in status.items() if v not in ("0", "")}
        rep.add("imu", "ok" if abs(hz - 200) < 2 and lost <= 2 else "warn",
                f"{len(imu.t_s)} samples at {hz:.1f} Hz" + _gaps_text(n_gaps, lost, hz))
        rep.add("imu", "warn" if bad else "ok", "board counters: " + (", ".join(f"{k}={v}" for k, v in status.items())
                                                                     if status else "no status lines"))
        raw = np.round(np.hstack([imu.acc_g * TR.ACC_PER_G, imu.gyro_dps * TR.GYRO_PER_DPS]))
        # The IMU sketch's wide range (default) sends 2x the register value, so counts reach +-65534 (4 g, 500 deg/s);
        # the narrow range stops at the int16 limit. Values past 32768 mean the wide range is in use.
        limit = 65534 if np.abs(raw).max() > 32768 else 32767
        stuck = int((np.abs(raw) >= limit).any(1).sum())
        if stuck:
            rng = "+-4 g / +-500 deg/s" if limit == 65534 else "+-2 g / +-250 deg/s"
            rep.add("imu", "warn", f"{stuck} samples at the sensor's limit ({rng}): the movement was faster than it can measure")
        drops = (meta.get("summary", {}).get("imu") or {}).get("link_drops")
        if drops:
            rep.add("imu", "warn", f"Wi-Fi link dropped {drops} time(s); the recorder reconnected")
        dl = (imu.t_host_s - (imu.t_s - applied.get("imu", 0.0))) * 1000
        rep.add("imu", "info", f"delivery after the device clock: median {np.median(dl):.1f} ms, p99 {np.percentile(dl, 99):.1f} ms")
        stills = CB._still_windows(imu)
        if stills:
            noise = float(np.median([imu.acc_g[w].std(0).mean() for w in stills]))
            if noise < 0.0005:
                rep.add("imu", "warn", f"still noise {noise:.5f} g is far below a real MPU-6050 (~0.001 g): simulated?")
    elif "imu" in src:
        rep.add("imu", "fail", "no usable IMU data")

    if p.emg is not None:
        emg = p.emg
        hz, n_gaps, lost = _device_rate(emg.dev_us)
        rep.add("emg", "ok" if abs(hz - 1000) < 10 and lost <= 10 else "warn",
                f"{len(emg.t_s)} samples at {hz:.0f} Hz" + _gaps_text(n_gaps, lost, hz))
        k = int(emg.fs)
        flat = np.mean([emg.raw[i:i + k].std() < 2 for i in range(0, len(emg.raw) - k, k)])
        clip = float(np.mean((emg.raw <= 0) | (emg.raw >= 4095)))
        if flat > 0.5:
            rep.add("emg", "warn", f"signal flat in {flat:.0%} of seconds: electrodes or cable?")
        if clip > 0.001:
            rep.add("emg", "warn", f"{clip:.1%} of samples clipped at 0/4095: lower the gain")
    elif "emg" in src and not any(i["section"] == "files" and i["text"].startswith("emg.csv") and i["level"] == "fail"
                                  for i in rep.items):
        rep.add("emg", "fail", "no usable sEMG (E,) data")

    if p.pose is not None:
        po = p.pose
        fps = 1 / np.median(np.diff(po.t_s))
        vis = float(np.mean(po.visible >= 0.75))
        rep.add("pose", "ok" if vis > 0.8 else "warn",
                f"{len(po.t_s)} frames at {fps:.0f} fps, person in {po.person.mean():.0%}, key joints visible in "
                f"{vis:.0%}, moving arm: {'left' if po.side == 'l' else 'right'}")
    elif "pose" in src:
        rep.add("pose", "fail", "pose file has too few frames with a person")

    # ---------------------------------------------------------- timing (shrug sync)
    if p.sync and len(p.sync) > 1:                      # only meaningful with a ground-truth sensor next to the radar
        if not any(k == "s" for _, k, _ in s.markers):
            rep.add("timing", "warn", "no 's' (sync shrugs) marker: searched the first 30 s")
        r0 = p.sync["radar"]
        rep.add("timing", "ok" if r0["shrugs_found"] == 3 else "warn",
                f"radar: {r0['shrugs_found']} shrugs found in {max(0.0, r0['window_s'][0]):.1f}-{r0['window_s'][1]:.1f} s")
        for name in ("pose", "imu", "emg"):
            v = p.sync.get(name)
            if not v:
                continue
            if v["applied"]:
                lvl = "warn" if abs(v["offset_ms"]) > SY.WARN_MS else "ok"
                rep.add("timing", lvl, f"{name}: {v['shrugs_found']} shrugs, {v['offset_ms']:+.0f} ms vs radar "
                                       f"(corrected{'; more than one radar frame' if lvl == 'warn' else ''})")
            elif name == "emg":
                rep.add("timing", "info", f"emg: {v['note']}")
            else:
                rep.add("timing", "warn", f"{name}: {v['note']} (corr {v['corr']:.2f}); times not corrected")
    rep.numbers["sync"] = p.sync

    # ---------------------------------------------------------- reps and labels
    if p.rep_source is None:
        rep.add("reps", "fail", "no pose, IMU or sEMG: reps can't be found (no ground truth)")
    else:
        n_rep = len(p.reps)
        n_mark = sum(1 for _, k, _ in s.markers if k == "space")
        sets = len({r.set_id for r in p.reps})
        lvl = "ok" if n_rep and (n_mark == 0 or abs(n_rep - n_mark) <= 1) else "warn"
        source = "the sEMG envelope (fallback)" if p.rep_source == "emg" else f"the {p.rep_source} elbow angle"
        rep.add("reps", lvl, f"{n_rep} reps in {sets} set(s) from {source}; {n_mark} space markers")
        for note in p.notes:
            if note.startswith("no reps in the"):
                rep.add("reps", "warn", note)
        if p.rep_source == "emg":
            rep.add("reps", "info", "sEMG has no joint angle: quality and compensation can't be labelled from this "
                                    "session; curls without a pause between them can merge into one burst")
        if p.reps:
            T = (rec.contract.frames_per_rep / rec.contract.fps) if rec is not None else 128 / 60
            long_ = [i + 1 for i, r in enumerate(p.reps) if r.duration_s > T]
            durs = [r.duration_s for r in p.reps]
            rep.add("reps", "warn" if long_ else "ok",
                    f"durations {min(durs):.1f}-{max(durs):.1f} s" +
                    (f"; rep(s) {long_} longer than {T:.2f} s get cropped around their peak" if long_ else ""))
        rep.numbers["reps"] = [r.to_dict() for r in p.reps]

    heads = {"fatigue": ["fatigue"], "quality": ["quality", "comp_rom"], "compensation": ["comp_shrug", "comp_lean"]}
    need = {"fatigue": "sEMG (E, lines)", "quality": "pose or IMU", "compensation": "pose"}
    can = {}
    for k, hs in heads.items():
        ok = bool(p.masks) and all(p.masks[h].any() for h in hs) and rec is not None
        if ok:
            why = ""
        elif rec is None:
            why = "no radar"
        elif p.rep_source is None:
            why = "no pose, IMU or sEMG (no ground truth)"
        elif not p.reps:
            why = "no reps found"
        else:
            why = f"needs {need[k]}"
        can[k] = {"ok": ok, "why": why}
    return _finish(rep, can), p


def _finish(rep, can):
    can = can or {k: {"ok": False, "why": "not a session"} for k in ("fatigue", "quality", "compensation")}
    usable = any(v["ok"] for v in can.values()) and not any(i["section"] in ("radar", "files", "reps")
                                                           and i["level"] == "fail" for i in rep.items)
    return {"session": rep.name, "usable": usable, "can_train": can, "items": rep.items, "numbers": rep.numbers}


SYMBOL = {"ok": "✓", "info": "·", "warn": "!", "fail": "✗"}


def format_report(r):
    lines = [f"== {r['session']}"]
    section = None
    for i in r["items"]:
        if i["section"] != section:
            section = i["section"]
            lines.append(f"  {section}")
        lines.append(f"    {SYMBOL[i['level']]} {i['text']}")
    parts = [f"{k} {'✓' if v['ok'] else '✗'}" + ("" if v["ok"] else f" ({v['why']})") for k, v in r["can_train"].items()]
    lines.append("  can train: " + ", ".join(parts))
    lines.append("  verdict: " + ("USABLE" if r["usable"] else "NOT USABLE for training"))
    return "\n".join(lines)
