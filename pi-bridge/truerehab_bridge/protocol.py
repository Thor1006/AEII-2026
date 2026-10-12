"""
Protocol 1.1, Python side. Must match frontend/src/sensor/protocol.ts and the spec
in frontend/README.md. check_bridge.py verifies a running bridge against it.

Providers create the small message objects below (Frame, Scores, Aux, Event).
The bridge adds the envelope (v, seq, t, src, kitId, sessionId) and encodes them:
text messages as JSON, frames as binary "TRF1".
"""
from __future__ import annotations

import json
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Union

import numpy as np

PROTOCOL_VERSION = 1
PROTOCOL_VERSION_STRING = "1.1"
MAGIC = b"TRF1"

Tone = Literal["good", "warn", "bad", "info"]
DeviceState = Literal["ok", "missing", "error", "off"]


def now_ms() -> float:
    return time.time() * 1000.0


def _clean(d: dict[str, Any]) -> dict[str, Any]:
    """Drop None values so optional fields are simply absent on the wire."""
    return {k: v for k, v in d.items() if v is not None}


# ---------- manifest (what the Pi announces in `hello`) ----------


@dataclass
class Axis:
    label: str
    min: float
    max: float
    unit: str | None = None

    def wire(self) -> dict[str, Any]:
        return _clean({"label": self.label, "unit": self.unit, "min": self.min, "max": self.max})


@dataclass
class FrameStream:
    view: str
    shape: tuple[int, int]
    fps: float
    label: str | None = None
    unit: str | None = None
    x: Axis | None = None
    y: Axis | None = None
    description: str | None = None

    def axes_wire(self) -> dict[str, Any] | None:
        axes = _clean({"x": self.x.wire() if self.x else None, "y": self.y.wire() if self.y else None})
        return axes or None

    def wire(self) -> dict[str, Any]:
        return _clean(
            {
                "view": self.view,
                "label": self.label,
                "shape": list(self.shape),
                "axes": self.axes_wire(),
                "unit": self.unit,
                "fps": self.fps,
                "description": self.description,
            }
        )


@dataclass
class ScoreInfo:
    key: str
    label: str
    higher_is_worse: bool
    thresholds: tuple[float, float] | None = None
    description: str | None = None
    rate_hz: float | None = None

    def wire(self) -> dict[str, Any]:
        return _clean(
            {
                "key": self.key,
                "label": self.label,
                "higherIsWorse": self.higher_is_worse,
                "thresholds": list(self.thresholds) if self.thresholds else None,
                "description": self.description,
                "rateHz": self.rate_hz,
            }
        )


@dataclass
class AuxChannel:
    key: str
    label: str
    unit: str | None = None
    rate_hz: float | None = None
    #: Key in status.devices that produces it, so the UI can say "Arduino not plugged in".
    device: str | None = None

    def wire(self) -> dict[str, Any]:
        return _clean({"key": self.key, "label": self.label, "unit": self.unit, "rateHz": self.rate_hz, "device": self.device})


@dataclass
class ActionInfo:
    key: str
    label: str
    tone: Tone
    hint: str | None = None

    def wire(self) -> dict[str, Any]:
        return _clean({"key": self.key, "label": self.label, "hint": self.hint, "tone": self.tone})


@dataclass
class ManifestPart:
    """What one provider contributes. The bridge merges all parts into the manifest."""

    frames: list[FrameStream] = field(default_factory=list)
    scores: list[ScoreInfo] = field(default_factory=list)
    aux: list[AuxChannel] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    actions: list[ActionInfo] = field(default_factory=list)


def manifest_wire(parts: list[ManifestPart], commands: list[str], status_interval_ms: int) -> dict[str, Any]:
    def unique(items: list[Any], key: str) -> list[Any]:
        seen: dict[str, Any] = {}
        for it in items:
            seen.setdefault(getattr(it, key), it)
        return list(seen.values())

    return {
        "frames": [f.wire() for f in unique([f for p in parts for f in p.frames], "view")],
        "scores": [s.wire() for s in unique([s for p in parts for s in p.scores], "key")],
        "aux": [a.wire() for a in unique([a for p in parts for a in p.aux], "key")],
        "events": sorted({e for p in parts for e in p.events}),
        "actions": [a.wire() for a in unique([a for p in parts for a in p.actions], "key")],
        "commands": commands,
        "statusIntervalMs": status_interval_ms,
    }


# ---------- status / session ----------


@dataclass
class DeviceHealth:
    state: DeviceState
    label: str | None = None
    message: str | None = None

    def wire(self) -> dict[str, Any]:
        return _clean({"state": self.state, "label": self.label, "message": self.message})


@dataclass
class Session:
    id: str
    state: Literal["running", "stopped"]
    exercise: str | None = None
    side: str | None = None
    target_reps: int | None = None
    user_id: str | None = None
    started_at: float | None = None
    ended_at: float | None = None

    def wire(self) -> dict[str, Any]:
        return _clean(
            {
                "id": self.id,
                "state": self.state,
                "exercise": self.exercise,
                "side": self.side,
                "targetReps": self.target_reps,
                "userId": self.user_id,
                "startedAt": self.started_at,
                "endedAt": self.ended_at,
            }
        )


# ---------- messages providers emit ----------


@dataclass
class Frame:
    view: str
    #: 2-D array [rows, cols], row-major. Converted to little-endian float32 on send.
    data: np.ndarray
    t: float | None = None
    frame_index: int | None = None
    unit: str | None = None
    x: Axis | None = None
    y: Axis | None = None


@dataclass
class Scores:
    #: key -> value (0–1), or (value, confidence)
    values: dict[str, float | tuple[float, float]]
    t: float | None = None


@dataclass
class Aux:
    channels: dict[str, float]
    t: float | None = None


@dataclass
class Event:
    kind: str
    data: dict[str, Any] | None = None
    label: str | None = None
    t: float | None = None


Message = Union[Frame, Scores, Aux, Event]


# ---------- encoding ----------


def encode_frame(header: dict[str, Any], data: np.ndarray, dtype: str = "f32") -> bytes:
    """TRF1 binary frame: magic, uint32 LE header length, JSON header, pad to 4 bytes, values LE row-major."""
    if data.ndim != 2:
        raise ValueError(f"frame data must be 2-D, got shape {data.shape}")
    header = {**header, "shape": [int(data.shape[0]), int(data.shape[1])], "dtype": dtype}
    if dtype == "f32":
        payload = np.ascontiguousarray(data, dtype="<f4").tobytes()
    elif dtype in ("u8", "u16"):
        lo, hi = float(np.nanmin(data)), float(np.nanmax(data))
        if hi == lo:
            hi = lo + 1.0
        max_raw = 255 if dtype == "u8" else 65535
        raw = np.round((np.nan_to_num(data, nan=lo) - lo) / (hi - lo) * max_raw)
        payload = raw.astype("<u1" if dtype == "u8" else "<u2").tobytes()
        header["scale"] = [lo, hi]
    else:
        raise ValueError(f"unknown dtype {dtype}")
    head = json.dumps(header, separators=(",", ":")).encode()
    pad = (-(8 + len(head))) % 4
    return MAGIC + struct.pack("<I", len(head)) + head + b"\0" * pad + payload


def decode_frame(buf: bytes) -> tuple[dict[str, Any], np.ndarray]:
    """Inverse of encode_frame (used by tests)."""
    if buf[:4] != MAGIC:
        raise ValueError("not a TRF1 frame")
    (n,) = struct.unpack_from("<I", buf, 4)
    header = json.loads(buf[8 : 8 + n])
    off = (8 + n + 3) & ~3
    rows, cols = header["shape"]
    dtype = header.get("dtype", "f32")
    np_dtype = {"f32": "<f4", "u8": "<u1", "u16": "<u2"}[dtype]
    arr = np.frombuffer(buf, dtype=np_dtype, count=rows * cols, offset=off).reshape(rows, cols)
    if dtype != "f32":
        lo, hi = header["scale"]
        arr = lo + arr.astype(np.float32) * ((hi - lo) / (255 if dtype == "u8" else 65535))
    return header, arr.astype(np.float32)


def encode(msg: Message, envelope: dict[str, Any], frame_dtype: str = "f32") -> str | bytes:
    """Wire form of a provider message. `envelope` holds v/seq/t/src/kitId/sessionId."""
    env = {**envelope, "t": msg.t if msg.t is not None else envelope["t"]}
    if isinstance(msg, Frame):
        axes = _clean({"x": msg.x.wire() if msg.x else None, "y": msg.y.wire() if msg.y else None})
        header = _clean({**env, "type": "frame", "view": msg.view, "frameIndex": msg.frame_index, "unit": msg.unit, "axes": axes or None})
        return encode_frame(header, msg.data, frame_dtype)
    if isinstance(msg, Scores):
        scores = {}
        for k, v in msg.values.items():
            if isinstance(v, tuple):
                scores[k] = {"value": float(v[0]), "confidence": float(v[1])}
            else:
                scores[k] = {"value": float(v)}
        return dumps({**env, "type": "scores", "scores": scores})
    if isinstance(msg, Aux):
        return dumps({**env, "type": "aux", "channels": {k: float(v) for k, v in msg.channels.items()}})
    if isinstance(msg, Event):
        return dumps(_clean({**env, "type": "event", "kind": msg.kind, "label": msg.label, "data": msg.data}))
    raise TypeError(f"unknown message {type(msg).__name__}")


def dumps(obj: dict[str, Any]) -> str:
    return json.dumps(obj, separators=(",", ":"), allow_nan=False)


# ---------- serial lines (Arduino) ----------


def parse_serial_line(line: str, columns: list[str] | None = None) -> dict[str, float] | None:
    """
    Same formats as the browser's Web Serial input:
      {"emg": 512, "force": 20.3}   emg:512,force:20.3   512,20.3 (named by `columns`)
    Returns aux channels, or None if the line has no numbers.
    """
    line = line.strip()
    if not line:
        return None
    if line.startswith("{"):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return None
        if isinstance(obj, dict) and obj.get("type") == "aux" and isinstance(obj.get("channels"), dict):
            obj = obj["channels"]
        out = {k: float(v) for k, v in obj.items() if isinstance(v, (int, float)) and not isinstance(v, bool)} if isinstance(obj, dict) else {}
        return out or None
    columns = columns or []
    out: dict[str, float] = {}
    for i, part in enumerate(p.strip() for p in line.replace("\t", ",").replace(";", ",").split(",")):
        key, _, val = part.partition(":") if ":" in part else (columns[i] if i < len(columns) else f"ch{i}", "", part)
        try:
            num = float(val)
        except ValueError:
            continue
        if np.isfinite(num) and key:
            out[key.strip()] = num
    return out or None
