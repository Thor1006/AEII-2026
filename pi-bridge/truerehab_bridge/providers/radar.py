"""
TEMPLATE for the real radar pipeline. Not implemented: no capture code exists yet.

While enabled, it announces its radar view in the manifest but sends nothing,
so the dashboard shows "Never arrived" and check_bridge.py fails. That is on
purpose: the stream is promised but not delivered yet.

What run() needs to do (see CLAUDE/plans/radar_ml_context.md):
  1. Receive DCA1000 UDP packets (raw ADC) in a thread; check sequence numbers.
  2. Rebuild each radar frame using the chirp config (radar_config.json).
  3. Range FFT → Doppler FFT → log magnitude: a [rows, cols] float32 array.
  4. emit(Frame(self.view, rd_map, t=capture_time_ms, x=..., y=...)) via
     loop.call_soon_threadsafe, at the configured fps.
  5. Later: feed frames to the model and emit Scores / Event("recommendation", ...),
     and add those to manifest() so the dashboard expects them.
Never flash firmware or change the radar configuration without asking the team.
"""
from __future__ import annotations

import asyncio
from typing import Any

from ..protocol import Axis, DeviceHealth, FrameStream, ManifestPart
from .base import Emit, Provider


class RadarProvider(Provider):
    name = "radar"

    def __init__(self, view: str = "range_doppler", rows: int = 64, cols: int = 64, fps: float = 20, range_max_m: float = 3.0, velocity_max_ms: float = 2.0, **options: Any) -> None:
        super().__init__(**options)
        self.view = view
        self.shape = (int(rows), int(cols))
        self.fps = float(fps)
        self.x = Axis("Velocity", -velocity_max_ms, velocity_max_ms, "m/s")
        self.y = Axis("Range", 0, range_max_m, "m")

    def manifest(self) -> ManifestPart:
        return ManifestPart(frames=[FrameStream(self.view, self.shape, self.fps, label="Range–Doppler", unit="dB", x=self.x, y=self.y)])

    def health(self) -> dict[str, DeviceHealth]:
        return {
            "radar": DeviceHealth("missing", "Radar (AWR1843)", "Capture code not written yet (pi-bridge/truerehab_bridge/providers/radar.py)"),
        }

    async def run(self, emit: Emit) -> None:
        # TODO: replace with real capture (see module docstring).
        while True:
            await asyncio.sleep(3600)
