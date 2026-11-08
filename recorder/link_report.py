#!/usr/bin/env python3
"""
Wi-Fi link report for recorded sessions: how often the sensor data paused, for how long, and why.

  python link_report.py <session> [<session> ...]     session folders (recorder or Pi bridge); several = a comparison

For each sensor file (emg.csv, imu.csv) it reads when each chunk arrived and the board's own clock:
  pause      no data for 0.2 s or more.
  held       the board kept sampling and all of it arrived late: the network held it back. If the first chunk after
             the pause is tiny (<= 5 samples), the ESP32's TCP resend timer ended it (it waits 1-2 s after a short
             radio blackout; see CLAUDE/plans/2026-11-08-wifi-drop-fixes.md).
  not sent   the board's own clock jumps too: it froze, restarted, or dropped lines because its buffer was full.
Also: link drops, other programs taking the board's one link (link_clients), signal strength, how late chunks
arrive, a regular delay every 0.52 s (a Mac's AirDrop/Handoff radio on the receiving side), and the board's
link_stall_ms / link_buf_max (MyoWare firmware from 2026-11-08 on).
Pure Python, no packages: runs on the Pi too. Never changes the session folder.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import deque
from pathlib import Path

PAUSE_S = 0.2
TINY_CHUNK = 5                  # samples: a resend after the timer carries one small segment
LATE_SPIKE_S = 0.04
AWDL_PERIOD_S = 0.524288        # 512 Wi-Fi time units
PREFIX = {"emg.csv": "E", "imu.csv": "I"}

csv.field_size_limit(1 << 20)


def read_chunks(path: Path, prefix: str):
    """[(arrival s, [device µs of each sample], [comment lines])] in file order, one entry per arrival time."""
    chunks: list[tuple[float, list[int], list[str]]] = []
    with path.open(newline="") as f:
        rows = csv.reader(f)
        next(rows, None)                                    # t_ns,line
        for row in rows:
            if len(row) < 2:
                continue
            try:
                t = int(row[0]) / 1e9
            except ValueError:
                continue
            line = row[1]
            if not chunks or chunks[-1][0] != t:
                chunks.append((t, [], []))
            if line.startswith(prefix + ","):
                parts = line.split(",", 2)
                if len(parts) >= 2 and parts[1].isdigit():
                    chunks[-1][1].append(int(parts[1]))
            elif line.startswith("#"):
                chunks[-1][2].append(line)
    return chunks


def status_values(comments: list[str]) -> list[dict[str, str]]:
    out = []
    for c in comments:
        if c.startswith("# status"):
            out.append(dict(kv.split("=", 1) for kv in c[len("# status"):].split() if "=" in kv))
    return out


def ints(rows, key):
    vals = []
    for r in rows:
        try:
            vals.append(int(float(r[key])))
        except (KeyError, ValueError):
            pass
    return vals


def analyse(path: Path, prefix: str, link: str) -> dict | None:
    chunks = read_chunks(path, prefix)
    data = [(t, us) for t, us, _ in chunks if us]
    if len(data) < 10:
        return None
    # device time, unwrapped (micros() wraps every 71.6 min; a step back of half the range = the board restarted)
    steps = []
    prev = None
    for _, us in data:
        for u in us:
            if prev is not None:
                d = (u - prev) & 0xFFFFFFFF
                if 0 < d < 1 << 31:
                    steps.append(d)
            prev = u
    period_us = statistics.median(steps) if steps else 1000
    n_samples = sum(len(us) for _, us in data)
    span_s = data[-1][0] - data[0][0]

    # pauses: no data for PAUSE_S or more
    pauses = []
    for (t0, us0), (t1, us1) in zip(data, data[1:]):
        gap = t1 - t0
        if gap < PAUSE_S:
            continue
        d = (us1[0] - us0[-1]) & 0xFFFFFFFF
        held = 0 < d <= 1.5 * period_us
        pauses.append({"at_s": round(t0 - data[0][0], 1), "s": round(gap, 2), "held": held,
                       "first_chunk": len(us1), "not_sent": 0 if held or d >= 1 << 31 else round(d / period_us) - 1})

    # how late each chunk arrived: arrival - device time, against the least-delayed chunk of the surrounding 10 s
    dev_s, prev_last, acc = [], None, 0.0
    for _, us in data:
        if prev_last is not None:
            d = (us[-1] - prev_last) & 0xFFFFFFFF
            if d < 1 << 31:                                 # (a restart: the clock stands still for one chunk)
                acc += d / 1e6
        dev_s.append(acc)
        prev_last = us[-1]
    raw = [t - dv for (t, _), dv in zip(data, dev_s)]
    late = rolling_late(data, raw)
    spikes = spike_onsets([t for t, _ in data], late)
    periodic = None
    if len(spikes) >= 20:
        gaps = [b - a for a, b in zip(spikes, spikes[1:])]
        near = [g for g in gaps if g < 4 * AWDL_PERIOD_S + 0.05
                and abs(g / AWDL_PERIOD_S - round(g / AWDL_PERIOD_S)) * AWDL_PERIOD_S < 0.02 and round(g / AWDL_PERIOD_S) >= 1]
        periodic = len(near) / len(gaps)

    comments = [c for _, _, cs in chunks for c in cs]
    status = status_values(comments)
    notes = [c for c in comments if c.startswith(("# bridge:", "# recorder:"))]
    clients = ints(status, "link_clients")
    dropped = ints(status, "link_dropped")
    rssi = ints(status, "rssi_dbm")
    held = [p for p in pauses if p["held"]]
    wifi = link != "USB"                                    # a USB copy isn't affected by the board's Wi-Fi clients
    return {
        "file": path.name, "link": link, "minutes": span_s / 60, "samples": n_samples,
        "rate_hz": n_samples / span_s if span_s > 0 else 0.0,
        "pauses": pauses, "held": len(held), "not_sent": len(pauses) - len(held),
        "tiny_first": sum(p["first_chunk"] <= TINY_CHUNK for p in held),
        "longest_s": max((p["s"] for p in pauses), default=0.0),
        "late_ms": {q: 1000 * percentile(late, q) for q in (50, 95, 99)},
        "late_100ms_pct": 100 * sum(x > 0.1 for x in late) / len(late),
        "periodic": periodic, "spikes": len(spikes),
        "link_drops": sum("link lost" in n for n in notes),
        "taken": sum("taken by another program" in n for n in notes),
        "other_clients": max(0, clients[-1] - clients[0] - sum("link back" in n for n in notes))
        if wifi and len(clients) >= 2 else 0,
        "board_dropped": dropped[-1] - dropped[0] if wifi and len(dropped) >= 2 else 0,
        "rssi": (min(rssi), statistics.median(rssi), max(rssi)) if wifi and rssi else None,
        "stall_ms": max(ints(status, "link_stall_ms"), default=None),
        "buf_max": max(ints(status, "link_buf_max"), default=None),
    }


def rolling_late(data, raw, window_s=10.0):
    """Lateness of each chunk: its (arrival - device time) above the smallest one within ±5 s."""
    times = [t for t, _ in data]
    out = []
    q: deque[int] = deque()                                 # indexes, increasing raw (a sliding-window minimum)
    j = 0
    for i, t in enumerate(times):
        while j < len(times) and times[j] <= t + window_s / 2:
            while q and raw[q[-1]] >= raw[j]:
                q.pop()
            q.append(j)
            j += 1
        while q and times[q[0]] < t - window_s / 2:
            q.popleft()
        out.append(raw[i] - raw[q[0]])
    return out


def spike_onsets(times, late):
    onsets, inside = [], False
    for t, x in zip(times, late):
        if x > LATE_SPIKE_S and not inside:
            onsets.append(t)
        inside = x > LATE_SPIKE_S
    return onsets


def percentile(xs, q):
    s = sorted(xs)
    return s[min(len(s) - 1, int(q / 100 * len(s)))] if s else 0.0


def links_of(folder: Path) -> dict[str, str]:
    """emg/imu -> 'Wi-Fi' or 'USB', from meta.json's sources."""
    try:
        meta = json.loads((folder / "meta.json").read_text())
    except (OSError, ValueError):
        return {}
    out = {}
    for name, src in (meta.get("sources") or {}).items():
        port = str((src or {}).get("port", ""))
        out[name] = "Wi-Fi" if port.startswith("tcp://") else "USB" if port else "?"
    return out


def report(folder: Path) -> list[dict]:
    links = links_of(folder)
    results = []
    for fname, prefix in PREFIX.items():
        path = folder / fname
        if not path.exists():
            continue
        r = analyse(path, prefix, links.get(fname[:-4], "?"))
        if r is None and prefix == "E":                     # the IMU's USB copy recorded in the emg slot
            r = analyse(path, "I", links.get(fname[:-4], "?"))
        if r:
            results.append(r)
    return results


def describe(folder: Path, results: list[dict]) -> str:
    out = [f"== {folder.name}"]
    if not results:
        out.append("   no sensor data found (emg.csv / imu.csv)")
    for r in results:
        out.append(f"-- {r['file']} ({r['link']}): {r['minutes']:.1f} min, {r['rate_hz']:.0f} samples/s")
        if not r["pauses"]:
            out.append("   no pauses of 0.2 s or more")
        else:
            out.append(f"   pauses >= 0.2 s: {len(r['pauses'])} ({len(r['pauses']) / max(r['minutes'], 1e-9):.1f}/min), "
                       f"longest {r['longest_s']:.2f} s")
            if r["held"]:
                out.append(f"   held by the network (nothing lost): {r['held']}; of these {r['tiny_first']} ended with a tiny "
                           "chunk = the ESP32's TCP resend timer")
            if r["not_sent"]:
                out.append(f"   not sent by the board (its own clock jumps: froze, restarted or buffer full): {r['not_sent']}")
            worst = sorted(r["pauses"], key=lambda p: -p["s"])[:5]
            out.append("   longest: " + ", ".join(
                f"{p['s']:.2f} s at {p['at_s']:.0f} s ({'held' if p['held'] else 'not sent'}, first chunk {p['first_chunk']})"
                for p in worst))
        lm = r["late_ms"]
        out.append(f"   arrival delay over the best: median {lm[50]:.0f} ms, 95% {lm[95]:.0f} ms, 99% {lm[99]:.0f} ms; "
                   f"{r['late_100ms_pct']:.1f}% of chunks > 100 ms late")
        if r["periodic"] is not None and r["periodic"] >= 0.5:
            out.append(f"   regular delays every 0.52 s ({r['spikes']} spikes, {100 * r['periodic']:.0f}% on the beat): "
                       "a Mac's AirDrop/Handoff radio (AWDL) on the receiving side")
        if r["link_drops"]:
            out.append(f"   link drops (reconnects): {r['link_drops']}")
        if r["taken"] or r["other_clients"]:
            out.append(f"   ANOTHER PROGRAM read the board too ({max(r['taken'], r['other_clients'])}x): it serves one reader "
                       "at a time, so both lose data. Run one reader per board.")
        if r["board_dropped"]:
            out.append(f"   the board dropped {r['board_dropped']} lines (its buffer was full)")
        if r["rssi"]:
            lo, med, hi = r["rssi"]
            out.append(f"   signal: {lo} to {hi} dBm (median {med:.0f}); below -70 is weak")
        if r["stall_ms"] is not None:
            out.append(f"   board: longest send stall {r['stall_ms']} ms, fullest buffer {r['buf_max']} of 65536 bytes")
    return "\n".join(out)


def table(rows: list[tuple[str, dict]]) -> str:
    head = "| Session | File | Min | Pauses/min | Longest | Held | Timer | Late>100ms | Drops | Others | RSSI min |"
    out = [head, "|" + "---|" * 11]
    for name, r in rows:
        out.append(f"| {name} | {r['file']} ({r['link']}) | {r['minutes']:.1f} | "
                   f"{len(r['pauses']) / max(r['minutes'], 1e-9):.2f} | {r['longest_s']:.2f} s | {r['held']} | "
                   f"{r['tiny_first']} | {r['late_100ms_pct']:.1f}% | {r['link_drops']} | "
                   f"{max(r['taken'], r['other_clients'])} | {r['rssi'][0] if r['rssi'] else '-'} |")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="How often the sensor data paused over Wi-Fi, and why.")
    ap.add_argument("sessions", nargs="+", help="session folder(s)")
    a = ap.parse_args(argv)
    rows = []
    for s in a.sessions:
        folder = Path(s).expanduser()
        if not folder.is_dir():
            print(f"not a folder: {folder}", file=sys.stderr)
            return 2
        results = report(folder)
        print(describe(folder, results))
        print()
        rows += [(folder.name, r) for r in results]
    if len(a.sessions) > 1 and rows:
        print(table(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
