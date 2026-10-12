#!/usr/bin/env python3
"""
Check that a bridge sends everything the dashboard needs (protocol 1.1).

    python check_bridge.py                          # ws://localhost:8765, 10 s
    python check_bridge.py trh-kit-01.local --seconds 20
    python check_bridge.py ws://192.168.1.20:8765 --commands   # also test session start/stop

Runs from any computer on the same network (only needs `websockets`).
Exit code 0 = everything passed (warnings allowed), 1 = something failed, 2 = could not connect.
--commands starts and stops a short test session. Don't use it while a real session is running.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import struct
import sys
import time
from array import array
from collections import defaultdict
from typing import Any

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidURI

MAGIC = b"TRF1"
DTYPE_BYTES = {"f32": 4, "u16": 2, "u8": 1}
KNOWN_TYPES = {"frame", "scores", "event", "aux", "status", "hello"}
USE_COLOR = sys.stdout.isatty()


def paint(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if USE_COLOR else s


class Report:
    def __init__(self) -> None:
        self.counts = {"pass": 0, "warn": 0, "fail": 0}

    def ok(self, msg: str) -> None:
        self.counts["pass"] += 1
        print(f"  {paint('32', '✓')} {msg}")

    def warn(self, msg: str) -> None:
        self.counts["warn"] += 1
        print(f"  {paint('33', '⚠')} {msg}")

    def fail(self, msg: str) -> None:
        self.counts["fail"] += 1
        print(f"  {paint('31', '✗')} {msg}")

    def section(self, title: str) -> None:
        print(f"\n{paint('1', title)}")


def normalize_url(addr: str) -> str:
    if addr.startswith(("ws://", "wss://")):
        return addr
    return f"ws://{addr}" if ":" in addr.split("]")[-1] else f"ws://{addr}:8765"


def check_envelope(m: dict[str, Any]) -> str | None:
    if m.get("v") != 1:
        return f"v is {m.get('v')!r}, expected 1"
    if not isinstance(m.get("seq"), int):
        return "seq missing or not an integer"
    if not isinstance(m.get("t"), (int, float)):
        return "t missing or not a number"
    return None


def parse_frame(buf: bytes) -> tuple[dict[str, Any] | None, str | None]:
    """Returns (header, problem)."""
    if len(buf) < 8 or buf[:4] != MAGIC:
        return None, "binary message without the TRF1 magic"
    (n,) = struct.unpack_from("<I", buf, 4)
    if 8 + n > len(buf):
        return None, f"header length {n} runs past the end of the message"
    try:
        header = json.loads(buf[8 : 8 + n])
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, "frame header is not valid JSON"
    shape = header.get("shape")
    if not (isinstance(shape, list) and len(shape) == 2 and all(isinstance(x, int) and x > 0 for x in shape)):
        return header, f"bad shape {shape!r}"
    dtype = header.get("dtype", "f32")
    if dtype not in DTYPE_BYTES:
        return header, f"unknown dtype {dtype!r}"
    off = (8 + n + 3) & ~3
    need = shape[0] * shape[1] * DTYPE_BYTES[dtype]
    have = len(buf) - off
    if have < need:
        return header, f"payload is {have} bytes, header promises {need} ({shape[0]}×{shape[1]} {dtype})"
    if have > need:
        return header, f"payload has {have - need} extra bytes"
    if dtype != "f32" and not (isinstance(header.get("scale"), list) and len(header["scale"]) == 2):
        return header, f"{dtype} frame without scale [min, max]"
    if dtype == "f32":
        vals = array("f")
        vals.frombytes(buf[off : off + need])
        if sys.byteorder == "big":
            vals.byteswap()
        if not all(math.isfinite(v) for v in vals):
            return header, "frame contains NaN or infinity"
    return header, None


async def run(url: str, seconds: float, test_commands: bool) -> int:
    rep = Report()
    print(f"TrueRehab bridge check → {url}  ({seconds:.0f} s)")
    rep.section("Connection")
    t0 = time.perf_counter()
    try:
        ws_cm = connect(url, open_timeout=5, max_size=None, ping_interval=None)
        ws = await ws_cm.__aenter__()
    except (OSError, asyncio.TimeoutError, InvalidURI) as exc:
        rep.fail(f"Can't connect: {exc}")
        print("\n  Is the bridge running, and is this computer on the same network? Try: ping <pi address>")
        return 2
    rep.ok(f"Connected in {(time.perf_counter() - t0) * 1000:.0f} ms")

    try:
        return await _check(ws, rep, seconds, test_commands)
    finally:
        await ws_cm.__aexit__(None, None, None)


async def _check(ws: Any, rep: Report, seconds: float, test_commands: bool) -> int:
    # ---- hello ----
    rep.section("Self-description (hello)")
    hello: dict[str, Any] | None = None
    first: Any = None
    try:
        first = await asyncio.wait_for(ws.recv(), 3)
    except asyncio.TimeoutError:
        rep.fail("Nothing received within 3 s of connecting")
    if isinstance(first, str):
        try:
            m = json.loads(first)
            if m.get("type") == "hello":
                hello = m
        except json.JSONDecodeError:
            pass
    manifest: dict[str, Any] = {}
    if hello is None:
        rep.fail("First message is not `hello`. The dashboard can't label itself or check streams (protocol 1.0 sender?)")
    else:
        dev = hello.get("device") or {}
        proto = str(hello.get("protocol", ""))
        if proto.split(".")[0] != "1":
            rep.fail(f"protocol is {proto!r}; the dashboard understands 1.x")
        elif not isinstance(dev.get("name"), str):
            rep.fail("hello.device.name missing")
        else:
            rep.ok(f'hello first: "{dev["name"]}", protocol {proto}, kit {dev.get("kitId") or hello.get("kitId") or "?"}')
        manifest = hello.get("manifest") or {}
        problems = []
        for key in ("frames", "scores", "aux", "events", "actions", "commands"):
            if not isinstance(manifest.get(key), list):
                problems.append(f"manifest.{key} missing or not a list")
        for f in manifest.get("frames", []):
            if not isinstance(f.get("view"), str) or not (isinstance(f.get("shape"), list) and len(f["shape"]) == 2) or not isinstance(f.get("fps"), (int, float)):
                problems.append(f"frame stream {f.get('view')!r} needs view, shape [rows, cols] and fps")
        for s in manifest.get("scores", []):
            if not isinstance(s.get("key"), str) or not isinstance(s.get("label"), str) or not isinstance(s.get("higherIsWorse"), bool):
                problems.append(f"score {s.get('key')!r} needs key, label and higherIsWorse")
        for a in manifest.get("aux", []):
            if not isinstance(a.get("key"), str) or not isinstance(a.get("label"), str):
                problems.append(f"aux channel {a.get('key')!r} needs key and label")
        for a in manifest.get("actions", []):
            if a.get("tone") not in ("good", "warn", "bad", "info"):
                problems.append(f"action {a.get('key')!r} tone must be good/warn/bad/info")
        if problems:
            for p in problems:
                rep.fail(p)
        else:
            rep.ok(
                f"Manifest: {len(manifest['frames'])} radar view(s), {len(manifest['scores'])} score(s), "
                f"{len(manifest['aux'])} signal(s), commands: {', '.join(manifest['commands']) or 'none'}"
            )
        if hello.get("synthetic"):
            rep.warn("The bridge says its data is synthetic (demo data)")

    # ---- collect ----
    rep.section(f"Live data (collecting for {seconds:.0f} s)")
    counts: dict[str, int] = defaultdict(int)
    first_seen: dict[str, float] = {}
    statuses: list[dict[str, Any]] = []
    status_times: list[float] = []
    frame_problems: dict[str, int] = defaultdict(int)
    frame_shapes: dict[str, set[tuple[int, int]]] = defaultdict(set)
    bad_envelopes: dict[str, int] = defaultdict(int)
    unknown_types: dict[str, int] = defaultdict(int)
    score_out_of_range: dict[str, int] = defaultdict(int)
    unknown_events: set[str] = set()
    unknown_actions: set[str] = set()
    last_seq: dict[str, int] = {}
    gaps = 0
    reorders = 0
    sequenced = 0
    skews: list[float] = []

    announced_events = set(manifest.get("events", []))
    announced_actions = {a.get("key") for a in manifest.get("actions", [])}

    def seen(stream: str) -> None:
        counts[stream] += 1
        first_seen.setdefault(stream, time.monotonic())

    def track(m: dict[str, Any]) -> None:
        nonlocal gaps, reorders, sequenced
        seq = m.get("seq")
        if isinstance(seq, int) and seq >= 0:
            sequenced += 1
            src = str(m.get("src", ""))
            last = last_seq.get(src)
            if last is not None:
                if seq > last + 1:
                    gaps += seq - last - 1
                elif seq <= last:
                    reorders += 1
            last_seq[src] = seq
        if isinstance(m.get("t"), (int, float)):
            skews.append(time.time() * 1000 - m["t"])

    deadline = time.monotonic() + seconds
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            raw = await asyncio.wait_for(ws.recv(), remaining)
        except asyncio.TimeoutError:
            break
        except ConnectionClosed:
            rep.fail("The bridge closed the connection")
            break
        if isinstance(raw, bytes):
            header, problem = parse_frame(raw)
            view = str((header or {}).get("view", "?"))
            if problem:
                frame_problems[f"{view}: {problem}"] += 1
                continue
            assert header is not None
            if (err := check_envelope(header)) is not None:
                bad_envelopes[f"frame: {err}"] += 1
            if header.get("type") != "frame":
                bad_envelopes["binary message whose header type isn't 'frame'"] += 1
            frame_shapes[view].add(tuple(header["shape"]))
            seen(f"frame:{view}")
            track(header)
            continue
        try:
            m = json.loads(raw)
        except json.JSONDecodeError:
            bad_envelopes["text message that isn't JSON"] += 1
            continue
        mtype = m.get("type")
        if mtype in ("pong", "ack"):
            continue
        if mtype not in KNOWN_TYPES:
            unknown_types[str(mtype)] += 1
            continue
        if (err := check_envelope(m)) is not None:
            bad_envelopes[f"{mtype}: {err}"] += 1
        track(m)
        if mtype == "scores":
            for k, v in (m.get("scores") or {}).items():
                val = v.get("value") if isinstance(v, dict) else v
                if not isinstance(val, (int, float)) or not 0 <= val <= 1:
                    score_out_of_range[k] += 1
                seen(f"score:{k}")
        elif mtype == "aux":
            for k, v in (m.get("channels") or {}).items():
                if isinstance(v, (int, float)):
                    seen(f"aux:{k}")
                else:
                    bad_envelopes[f"aux channel {k} is not a number"] += 1
        elif mtype == "event":
            kind = m.get("kind")
            seen(f"event:{kind}")
            if announced_events and kind not in announced_events:
                unknown_events.add(str(kind))
            if kind == "recommendation":
                action = (m.get("data") or {}).get("action")
                if announced_actions and action not in announced_actions:
                    unknown_actions.add(str(action))
        elif mtype == "status":
            statuses.append(m)
            status_times.append(time.monotonic())
            seen("status")

    elapsed = seconds

    # ---- frames ----
    for f in manifest.get("frames", []):
        view = f["view"]
        n = counts.get(f"frame:{view}", 0)
        if not n:
            rep.fail(f'Radar view "{view}": announced but never arrived')
            continue
        rate = n / elapsed
        shapes = frame_shapes[view]
        msg = f'Radar view "{view}": {n} frames, {rate:.1f}/s (announced {f["fps"]})'
        if shapes != {tuple(f["shape"])}:
            rep.fail(f"{msg}, but shape {sorted(shapes)} ≠ announced {tuple(f['shape'])}")
        elif rate < 0.7 * f["fps"]:
            rep.warn(f"{msg}: slower than announced")
        else:
            rep.ok(msg)
    for view in frame_shapes:
        if manifest and view not in {f["view"] for f in manifest.get("frames", [])}:
            rep.warn(f'Radar view "{view}" arrives but isn\'t in the manifest')
    for problem, n in frame_problems.items():
        rep.fail(f"Broken radar frame ({n}×): {problem}")

    # ---- scores & aux ----
    device_states = (statuses[-1].get("devices") or {}) if statuses else {}
    for s in manifest.get("scores", []):
        n = counts.get(f"score:{s['key']}", 0)
        if n:
            rep.ok(f'Score "{s["label"]}": {n} updates')
        else:
            rep.fail(f'Score "{s["label"]}" ({s["key"]}): announced but never arrived')
    for k, n in score_out_of_range.items():
        rep.warn(f'Score "{k}": {n} values outside 0–1')
    for a in manifest.get("aux", []):
        n = counts.get(f"aux:{a['key']}", 0)
        dev = device_states.get(a.get("device") or "", {})
        if n:
            rep.ok(f'Signal "{a["label"]}": {n} samples')
        elif dev and dev.get("state") != "ok":
            rep.warn(f'Signal "{a["label"]}": not arriving, and the bridge says why: {dev.get("label", a.get("device"))} — {dev.get("message", dev.get("state"))}')
        else:
            rep.fail(f'Signal "{a["label"]}" ({a["key"]}): announced but never arrived')
    announced = {f"score:{x['key']}" for x in manifest.get("scores", [])} | {f"aux:{x['key']}" for x in manifest.get("aux", [])}
    extra = sorted(k for k in counts if k.startswith(("score:", "aux:")) and manifest and k not in announced)
    for k in extra:
        rep.warn(f"{k} arrives but isn't in the manifest (the dashboard will label it generically)")
    if unknown_events:
        rep.warn(f"Event kinds not in the manifest: {', '.join(sorted(unknown_events))}")
    if unknown_actions:
        rep.warn(f"Recommendation actions not in the manifest: {', '.join(sorted(unknown_actions))}")

    # ---- status ----
    rep.section("Heartbeat and link")
    interval = (manifest.get("statusIntervalMs") or 1000) / 1000
    if not statuses:
        rep.fail("No status heartbeat received")
    else:
        gaps_s = [b - a for a, b in zip(status_times, status_times[1:])]
        avg = statistics.mean(gaps_s) if gaps_s else None
        devices = statuses[-1].get("devices") or {}
        dev_txt = ", ".join(f"{k} {v.get('state')}" for k, v in devices.items()) or "none listed"
        if avg is not None and avg > interval * 2:
            rep.warn(f"Status every {avg:.1f} s (announced {interval:.1f} s)")
        else:
            rep.ok(f"Status: {len(statuses)} received" + (f", every {avg:.1f} s" if avg else ""))
        if not devices:
            rep.warn("Status lists no devices, so the dashboard can't show what is plugged in")
        else:
            rep.ok(f"Devices: {dev_txt}")
        for k, v in devices.items():
            if v.get("state") not in ("ok", "missing", "error", "off"):
                rep.fail(f"Device {k}: state {v.get('state')!r} must be ok/missing/error/off")
            elif v.get("state") != "ok":
                rep.warn(f"Device {k} is {v.get('state')}: {v.get('message', '')}")

    for problem, n in bad_envelopes.items():
        rep.fail(f"{problem} ({n}×)")
    for t, n in unknown_types.items():
        rep.warn(f'Unknown message type "{t}" ({n}×): the dashboard ignores it')

    if sequenced:
        if gaps or reorders:
            rep.fail(f"Sequence: {gaps} missing and {reorders} out of order in {sequenced} messages")
        else:
            rep.ok(f"Sequence: no gaps in {sequenced} messages")
    if skews:
        skew = statistics.median(skews)
        if abs(skew) > 1000:
            rep.warn(f"Clock: the bridge's time is {abs(skew) / 1000:.1f} s {'behind' if skew > 0 else 'ahead of'} this computer. Install chrony on the Pi.")
        else:
            rep.ok(f"Clock: within {abs(skew):.0f} ms of this computer (includes network delay)")

    try:
        t0 = time.perf_counter()
        await ws.send(json.dumps({"type": "ping", "id": 999, "clientT": 1}))
        rtt = await _await_reply(ws, lambda m: m.get("type") == "pong" and m.get("id") == 999, 3)
        if rtt is None:
            rep.warn("No pong for a ping: the dashboard can't show connection delay")
        else:
            rep.ok(f"Ping → pong in {(time.perf_counter() - t0) * 1000:.0f} ms")
    except ConnectionClosed:
        rep.fail("Connection closed during ping")

    # ---- commands ----
    if test_commands:
        await _check_commands(ws, rep, manifest, hello)

    c = rep.counts
    summary = f"{c['pass']} passed, {c['warn']} warning(s), {c['fail']} failed"
    print(f"\n{paint('1;31' if c['fail'] else '1;32', 'FAIL' if c['fail'] else 'PASS')}  {summary}")
    return 1 if c["fail"] else 0


async def _await_reply(ws: Any, match: Any, timeout: float) -> dict[str, Any] | None:
    deadline = time.monotonic() + timeout
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            raw = await asyncio.wait_for(ws.recv(), remaining)
        except asyncio.TimeoutError:
            return None
        if isinstance(raw, str):
            try:
                m = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if match(m):
                return m
    return None


async def _check_commands(ws: Any, rep: Report, manifest: dict[str, Any], hello: dict[str, Any] | None) -> None:
    rep.section("Commands")
    cmds = manifest.get("commands", [])
    if "session.start" not in cmds:
        rep.warn("Bridge doesn't announce session.start; skipping command tests")
        return
    if hello and (hello.get("session") or {}).get("state") == "running":
        rep.warn("A session is already running; not touching it")
        return

    async def command(cid: int, name: str, args: dict[str, Any], also: Any = None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Send a command; wait for its ack and (optionally) a second message matching `also`.
        Both are collected together because the bridge may send the side effect before the ack."""
        await ws.send(json.dumps({"type": "command", "id": cid, "name": name, "args": args}))
        ack: dict[str, Any] | None = None
        extra: dict[str, Any] | None = None
        deadline = time.monotonic() + 5
        while (ack is None or (also and extra is None)) and (remaining := deadline - time.monotonic()) > 0:
            m = await _await_reply(ws, lambda m: (m.get("type") == "ack" and m.get("id") == cid) or bool(also and also(m)), remaining)
            if m is None:
                break
            if m.get("type") == "ack":
                ack = m
            else:
                extra = m
        return ack, extra

    def is_session_status(m: dict[str, Any]) -> bool:
        return m.get("type") == "status" and (m.get("session") or {}).get("state") == "running" and (m.get("session") or {}).get("exercise") == "check_bridge"

    ack, st = await command(9001, "session.start", {"exercise": "check_bridge", "side": "right", "targetReps": 3}, is_session_status)
    session_id = ((ack or {}).get("result") or {}).get("session", {}).get("id")
    if not ack:
        rep.fail("session.start: no ack within 5 s")
        return
    if not ack.get("ok") or not session_id:
        rep.fail(f"session.start: refused ({ack.get('error')})")
        return
    rep.ok(f"session.start → ack with session {session_id}")
    if st:
        rep.ok("Status shows the running session")
    else:
        rep.fail("Status never showed the new session")

    if "marker" in cmds:
        ack, ev = await command(9002, "marker", {"label": "check_bridge marker"}, lambda m: m.get("type") == "event" and m.get("kind") == "marker")
        if ack and ack.get("ok") and ev:
            rep.ok("marker → ack and marker event")
        else:
            rep.fail("marker: no ack or no marker event")

    ack, _ = await command(9003, "no.such.command", {})
    if ack and not ack.get("ok") and ack.get("error"):
        rep.ok("Unknown command → refused with an error message")
    else:
        rep.fail("Unknown command wasn't refused with an error")

    ack, _ = await command(9004, "session.stop", {})
    if ack and ack.get("ok"):
        rep.ok("session.stop → ack")
    else:
        rep.fail(f"session.stop failed: {(ack or {}).get('error', 'no ack')}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Check a TrueRehab bridge against protocol 1.1.")
    ap.add_argument("address", nargs="?", default="localhost", help="Pi address or ws:// URL (default localhost)")
    ap.add_argument("--seconds", "-s", type=float, default=10, help="How long to collect data (default 10)")
    ap.add_argument("--commands", action="store_true", help="Also start/stop a short test session")
    args = ap.parse_args()
    try:
        return asyncio.run(run(normalize_url(args.address), args.seconds, args.commands))
    except KeyboardInterrupt:
        return 1


if __name__ == "__main__":
    sys.exit(main())
