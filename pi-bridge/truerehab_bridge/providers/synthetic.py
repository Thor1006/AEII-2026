"""
SYNTHETIC data. Not a radar model: plausible-looking numbers so the bridge, the
network and the dashboard can be tested without hardware. Port of
frontend/src/sensor/mockData.ts; keep the two in step.

Scenario: seated elbow flexion, one rep every rep_period_s. Fatigue ramps up over
~2 minutes, range of motion shrinks, compensation (trunk lean) appears late.
Starting a session resets fatigue and the rep count.
"""
from __future__ import annotations

import asyncio
import math
import random
import time
from typing import Any

import numpy as np

from ..protocol import ActionInfo, Aux, AuxChannel, Axis, DeviceHealth, Event, Frame, FrameStream, ManifestPart, Scores, ScoreInfo, Session
from .base import Emit, Provider

RANGE_AXIS = Axis("Range", 0, 3, "m")
VELOCITY_AXIS = Axis("Velocity", -2, 2, "m/s")

ACTIONS = [
    ActionInfo("continue", "Continue", "good", "Form looks good. Keep going."),
    ActionInfo("correct_posture", "Correct posture", "warn", "Sit upright and keep the shoulder down."),
    ActionInfo("reduce_load", "Reduce load or range", "warn", "Use a lighter weight or a smaller range."),
    ActionInfo("rest", "Rest", "bad", "Take a break before the next set."),
    ActionInfo("see_physio", "See your physiotherapist", "bad", "The pattern keeps coming back. Get it checked."),
]


def _noise(s: float) -> float:
    return (random.random() + random.random() + random.random() - 1.5) * s


def _clamp01(x: float) -> float:
    return min(1.0, max(0.0, x))


class SyntheticProvider(Provider):
    name = "synthetic"
    synthetic = True

    def __init__(self, fps: float = 20, rows: int = 64, cols: int = 64, rep_period_s: float = 3.2, cycle_s: float = 150, **options: Any) -> None:
        super().__init__(**options)
        self.fps = float(fps)
        self.rows = int(rows)
        self.cols = int(cols)
        self.rep_period_s = float(rep_period_s)
        self.cycle_s = float(cycle_s)
        self._reset(time.time())
        self._frame_index = 0
        self._last_scores = 0.0
        self._compensating = False
        rr, cc = np.mgrid[0:self.rows, 0:self.cols]
        self._rr = rr.astype(np.float32)
        self._cc = cc.astype(np.float32)

    def _reset(self, now_s: float) -> None:
        self._start = now_s
        self._rep = 0
        self._last_phase = 0.0
        self._rep_min = math.inf
        self._rep_max = -math.inf
        self._latest = (0.0, 1.0, 0.0)

    # ----- Provider API -----

    def manifest(self) -> ManifestPart:
        return ManifestPart(
            frames=[
                FrameStream(
                    "range_doppler",
                    (self.rows, self.cols),
                    self.fps,
                    label="Range–Doppler",
                    unit="dB",
                    x=VELOCITY_AXIS,
                    y=RANGE_AXIS,
                    description="Each bright spot is something reflecting the radar. Up/down = distance from the radar. "
                    "Left/right = how fast it moves toward (right) or away (left). A moving arm makes a spot that swings sideways.",
                )
            ],
            scores=[
                ScoreInfo("fatigue", "Fatigue", True, (0.4, 0.7), "How tired the working muscle seems. Lower is better.", 4),
                ScoreInfo("quality", "Movement quality", False, (0.4, 0.7), "Smoothness and range of the movement. Higher is better.", 4),
                ScoreInfo("compensation", "Compensation", True, (0.4, 0.7), "How much other body parts (trunk, shoulder) are helping. Lower is better.", 4),
            ],
            aux=[
                AuxChannel("elbow_angle_deg", "Elbow angle", "°", self.fps, "camera"),
                AuxChannel("emg_rms", "sEMG (biceps)", "RMS", self.fps, "arduino"),
                AuxChannel("force_n", "Force", "N", self.fps, "arduino"),
            ],
            events=["rep_start", "rep_end", "compensation", "recommendation"],
            actions=ACTIONS,
        )

    def health(self) -> dict[str, DeviceHealth]:
        return {
            "radar": DeviceHealth("ok", "Radar", "Simulated"),
            "arduino": DeviceHealth("ok", "Arduino (sEMG / force)", "Simulated"),
            "model": DeviceHealth("ok", "AI model", "Simulated scores"),
        }

    def on_session_start(self, session: Session) -> None:
        self._reset(time.time())

    async def run(self, emit: Emit) -> None:
        period = 1.0 / self.fps
        loop = asyncio.get_running_loop()
        next_t = loop.time()
        while True:
            for msg in self._tick(time.time()):
                emit(msg)
            next_t += period
            await asyncio.sleep(max(0.0, next_t - loop.time()))

    # ----- simulation -----

    def _tick(self, now_s: float) -> list[Any]:
        out: list[Any] = []
        t = now_s * 1000
        elapsed = now_s - self._start
        fatigue = _clamp01((elapsed % self.cycle_s) / (self.cycle_s * 0.8) + _noise(0.02))
        compensation = _clamp01(1 / (1 + math.exp(-(fatigue - 0.62) * 12)) * 0.92 + _noise(0.04))
        quality = _clamp01(1 - 0.55 * compensation - 0.25 * fatigue + _noise(0.03))
        self._latest = (fatigue, quality, compensation)

        phase = (elapsed % self.rep_period_s) / self.rep_period_s
        rom = 110 * (1 - 0.35 * fatigue)
        angle = 20 + rom * (0.5 - 0.5 * math.cos(2 * math.pi * phase))
        ang_vel = rom * math.pi * math.sin(2 * math.pi * phase) / self.rep_period_s
        self._rep_min = min(self._rep_min, angle)
        self._rep_max = max(self._rep_max, angle)

        if phase < self._last_phase:
            if self._rep > 0:
                out.append(Event("rep_end", {"rep": self._rep, "romDeg": round(self._rep_max - self._rep_min, 1)}, t=t))
                out.append(Event("recommendation", self._recommend(), t=t))
            self._rep += 1
            self._rep_min, self._rep_max = math.inf, -math.inf
            out.append(Event("rep_start", {"rep": self._rep}, t=t))
        self._last_phase = phase

        if not self._compensating and compensation > 0.6:
            self._compensating = True
            out.append(Event("compensation", {"pattern": "trunk_lean", "severity": round(compensation, 2)}, "Trunk lean detected", t=t))
        elif self._compensating and compensation < 0.45:
            self._compensating = False

        out.append(self._frame(t, angle, ang_vel, compensation))

        emg = _clamp01(0.15 + 0.5 * abs(math.sin(2 * math.pi * phase)) * (1 + fatigue) + _noise(0.05))
        force = 20 + 4 * math.sin(2 * math.pi * phase) + _noise(0.8)
        out.append(Aux({"elbow_angle_deg": round(angle, 2), "emg_rms": round(emg, 3), "force_n": round(force, 2)}, t=t))

        if t - self._last_scores >= 250:
            self._last_scores = t
            out.append(
                Scores(
                    {
                        "fatigue": (fatigue, _clamp01(0.75 + _noise(0.1))),
                        "quality": (quality, _clamp01(0.8 + _noise(0.1))),
                        "compensation": (compensation, _clamp01(0.7 + _noise(0.1))),
                    },
                    t=t,
                )
            )
        return out

    def _recommend(self) -> dict[str, str]:
        fatigue, _, compensation = self._latest
        if compensation > 0.85 and fatigue > 0.9:
            return {"action": "see_physio", "reason": "Persistent compensation at high fatigue"}
        if fatigue > 0.85:
            return {"action": "rest", "reason": "High fatigue"}
        if compensation > 0.6:
            return {"action": "correct_posture", "reason": "Trunk lean during the rep"}
        if fatigue > 0.65:
            return {"action": "reduce_load", "reason": "Fatigue rising, range of motion shrinking"}
        return {"action": "continue", "reason": "Form and fatigue within range"}

    def _frame(self, t: float, angle: float, ang_vel: float, comp: float) -> Frame:
        rows, cols = self.rows, self.cols
        c0 = cols / 2
        blobs = [
            (rows * 0.2, c0, 1.0, 0.8, 0.6),  # static clutter (chair / wall)
            (rows * 0.34 + 3 * math.sin(math.radians(angle)), c0 + ang_vel * 0.09, 0.6, 1.2, 1.6),  # forearm
            (rows * 0.3, c0 + comp * 3 * math.sin(t / 400), 0.4, 1.5, 0.8 + comp * 2),  # torso
        ]
        noise = np.abs(np.random.default_rng().normal(0, 0.35, (rows, cols))).astype(np.float32)
        lin = 0.01 * (1 + noise)
        for r, c, a, sr, sc in blobs:
            lin += a * np.exp(-0.5 * (((self._rr - r) / sr) ** 2 + ((self._cc - c) / sc) ** 2))
        self._frame_index += 1
        return Frame("range_doppler", (20 * np.log10(lin)).astype(np.float32), t=t, frame_index=self._frame_index, unit="dB", x=VELOCITY_AXIS, y=RANGE_AXIS)
