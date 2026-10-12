"""Deterministic radar-motion simulator, peak counter, and session recording."""

import asyncio
import csv
from collections import deque
from datetime import datetime, timezone
from io import StringIO
from math import exp, sin
from pathlib import Path
from time import monotonic, perf_counter, time
from uuid import uuid4

from .adapters import (
    AIModel, RadarFeatures, RadarSource, SignalProcessor,
    SimulationAIModel, SimulationRadarSource, SimulationSignalProcessor,
    demo_indices,
)
from .schemas import (
    DebugTelemetry, MovementTelemetry, RadarTelemetry, RecommendationTelemetry,
    SignalPoint, SystemTelemetry, TelemetryFrame, TrendPoint,
)

MAX_REPS = 10
EXPORT_FIELDS = [
    "timestamp", "rep_count", "movement_signal", "movement_quality",
    "fatigue_estimate", "compensation_level", "compensation_risk", "recommendation",
]


class PeakCounter:
    """Count complete curl peaks in a sampled movement waveform."""

    def __init__(self, refractory_s: float = 2.0) -> None:
        self.previous_signal: float | None = None
        self.previous_slope = 0.0
        self.last_peak_s = -100.0
        self.refractory_s = refractory_s

    def observe(self, elapsed_s: float, signal: float) -> bool:
        if self.previous_signal is None:
            self.previous_signal = signal
            return False
        slope = signal - self.previous_signal
        peaked = (
            self.previous_slope > 0
            and slope <= 0
            and self.previous_signal >= 0.78
            and elapsed_s - self.last_peak_s >= self.refractory_s
        )
        if peaked:
            self.last_peak_s = elapsed_s
        self.previous_signal = signal
        self.previous_slope = slope
        return peaked


def recommendation_for(rep: int) -> RecommendationTelemetry:
    if rep >= 9:
        return RecommendationTelemetry(
            status="rest", title="REST / CORRECT FORM",
            message="High simulated fatigue and compensation are present. Consider reducing resistance or taking a short rest.",
        )
    if rep >= 7:
        return RecommendationTelemetry(
            status="correct_form", title="CORRECT FORM",
            message="Simulated future compensation risk is increasing. Slow the curl and keep the elbow close to the torso.",
        )
    if rep >= 4:
        return RecommendationTelemetry(
            status="monitor", title="MONITOR FATIGUE",
            message="The estimated fatigue trend is rising. Maintain controlled movement and watch shoulder position.",
        )
    return RecommendationTelemetry(
        status="continue", title="CONTINUE",
        message="The simulated movement remains stable. Maintain the current controlled form.",
    )


def simulated_range_doppler(features: RadarFeatures) -> list[list[float]]:
    """A display-only heatmap; it is not a measured range-Doppler FFT."""
    rows, columns = 18, 28
    range_center = (features.range_m - 0.6) / 1.5 * (columns - 1)
    velocity_center = (features.velocity_mps + 0.3) / 0.6 * (rows - 1)
    values: list[list[float]] = []
    for row in range(rows):
        cells = []
        for column in range(columns):
            target = exp(-(((column - range_center) / 2.2) ** 2 + ((row - velocity_center) / 2.0) ** 2) / 2)
            side_lobe = 0.25 * exp(-(((column - range_center - 4) / 3.8) ** 2 + ((row - velocity_center + 2) / 2.6) ** 2) / 2)
            texture = 0.045 + 0.02 * sin(column * 1.9 + row * 2.7 + features.elapsed_s * 0.8)
            cells.append(round(max(0.0, min(1.0, target + side_lobe + texture)), 3))
        values.append(cells)
    return values


class SimulationEngine:
    def __init__(
        self,
        radar_source: RadarSource | None = None,
        signal_processor: SignalProcessor | None = None,
        ai_model: AIModel | None = None,
    ) -> None:
        self.radar_source = radar_source or SimulationRadarSource()
        self.signal_processor = signal_processor or SimulationSignalProcessor()
        self.ai_model = ai_model or SimulationAIModel()
        self.subject_id = "DEMO SUBJECT"
        self.session_id = "demo-preview"
        self.running = False
        self.has_started = False
        self.elapsed_s = 21.0
        self.rep_count = 7
        self.frames_received = 0
        self.processing_latency_ms = 0.0
        self.ai_latency_ms = 0.0
        self.peak_counter = PeakCounter()
        self.signal_history: deque[SignalPoint] = deque(maxlen=160)
        self.trend_history: list[TrendPoint] = []
        self.records: list[dict[str, str | int | float]] = []
        self._last_clock = monotonic()
        for sample_index in range(120):
            sample_time = 15.0 + sample_index * 0.05
            sample = self.radar_source.read_frame(sample_time)
            self.signal_history.append(SignalPoint(time_s=round(sample_time, 2), value=round(sample.normalized_movement, 3)))
        for rep in range(1, 8):
            self.trend_history.append(self._trend_point(rep))
        self.latest = self._make_frame()

    def _trend_point(self, rep: int) -> TrendPoint:
        quality, fatigue, level, risk = demo_indices(rep)
        return TrendPoint(
            rep=rep, movement_quality=quality, fatigue_estimate=fatigue,
            compensation_level=level, compensation_risk=risk,
        )

    def _make_frame(self) -> TelemetryFrame:
        started = perf_counter()
        sample = self.radar_source.read_frame(self.elapsed_s)
        features = self.signal_processor.extract_features(sample)
        processing_ms = (perf_counter() - started) * 1000
        inference_started = perf_counter()
        quality, ai = self.ai_model.predict(features, self.rep_count)
        inference_ms = (perf_counter() - inference_started) * 1000
        self.processing_latency_ms = round(processing_ms, 3)
        self.ai_latency_ms = round(inference_ms, 3)
        return TelemetryFrame(
            timestamp=time(),
            session_id=self.session_id,
            mode="simulation",
            data_source="PYTHON SIMULATION",
            exercise="biceps_curl",
            running=self.running,
            session_seconds=round(self.elapsed_s, 2),
            subject_id=self.subject_id,
            radar=RadarTelemetry(
                connected=True,
                capture_connected=True,
                range_m=round(features.range_m, 3),
                velocity_mps=round(features.velocity_mps, 3),
                doppler_hz=round(features.doppler_hz, 2),
                signal_strength=round(features.signal_strength, 3),
            ),
            movement=MovementTelemetry(
                normalized_signal=round(features.normalized_movement, 3),
                rep_count=self.rep_count,
                movement_quality=quality,
                phase=features.phase if self.running else "Idle",
            ),
            ai=ai,
            recommendation=recommendation_for(self.rep_count),
            system=SystemTelemetry(
                radar="SIMULATED / CONNECTED", capture="SIMULATED / CONNECTED",
                radar_stream="ACTIVE" if self.running else "READY",
                ai_engine="DEMO MODEL", imu="NOT CONNECTED", semg="NOT CONNECTED",
                calibration="NOT CALIBRATED",
            ),
            debug=DebugTelemetry(
                frame_rate_hz=20.0,
                radar_frames_received=self.frames_received,
                processing_latency_ms=self.processing_latency_ms,
                ai_inference_latency_ms=self.ai_latency_ms,
                packet_status="SIMULATED / OK",
            ),
            signal_history=list(self.signal_history),
            trend_history=list(self.trend_history),
            range_doppler=simulated_range_doppler(features),
        )

    def snapshot(self) -> TelemetryFrame:
        return self.latest

    def _clear(self) -> None:
        self.running = False
        self.has_started = True
        self.elapsed_s = 0.0
        self.rep_count = 0
        self.frames_received = 0
        self.peak_counter = PeakCounter()
        self.signal_history.clear()
        self.trend_history.clear()
        self.records.clear()
        self.session_id = "demo-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:6]
        self.latest = self._make_frame()

    def start(self) -> TelemetryFrame:
        if not self.has_started or self.rep_count >= MAX_REPS:
            self._clear()
        self.running = True
        self._last_clock = monotonic()
        self.latest = self._make_frame()
        return self.latest

    def stop(self) -> TelemetryFrame:
        self.running = False
        self.latest = self._make_frame()
        return self.latest

    def reset(self) -> TelemetryFrame:
        self._clear()
        return self.latest

    def advance(self, delta_s: float) -> TelemetryFrame:
        """Advance by elapsed time; a peak in the waveform decides rep counting."""
        if not self.running:
            return self.latest
        self.elapsed_s += max(0.0, min(delta_s, 0.25))
        sample = self.radar_source.read_frame(self.elapsed_s)
        self.frames_received += 1
        self.signal_history.append(SignalPoint(time_s=round(self.elapsed_s, 2), value=round(sample.normalized_movement, 3)))
        if self.peak_counter.observe(self.elapsed_s, sample.normalized_movement):
            self.rep_count = min(MAX_REPS, self.rep_count + 1)
            self.trend_history.append(self._trend_point(self.rep_count))
            if self.rep_count >= MAX_REPS:
                self.running = False
        self.latest = self._make_frame()
        self.records.append(self._export_record(self.latest))
        return self.latest

    async def run(self) -> None:
        while True:
            now = monotonic()
            if self.running:
                self.advance(now - self._last_clock)
            self._last_clock = now
            await asyncio.sleep(0.05)

    @staticmethod
    def _export_record(frame: TelemetryFrame) -> dict[str, str | int | float]:
        return {
            "timestamp": datetime.fromtimestamp(frame.timestamp, timezone.utc).isoformat(),
            "rep_count": frame.movement.rep_count,
            "movement_signal": frame.movement.normalized_signal,
            "movement_quality": frame.movement.movement_quality,
            "fatigue_estimate": frame.ai.fatigue_estimate,
            "compensation_level": frame.ai.compensation_level,
            "compensation_risk": frame.ai.compensation_risk,
            "recommendation": frame.recommendation.status,
        }

    def export_csv(self) -> str:
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(self.records)
        return output.getvalue()

    def save_session(self, data_root: Path) -> Path:
        destination = data_root / "sessions" / self.session_id
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "radar").mkdir(exist_ok=True)
        (destination / "telemetry.csv").write_text(self.export_csv(), encoding="utf-8")
        metadata = {
            "session_id": self.session_id,
            "subject_id": self.subject_id,
            "mode": "simulation",
            "exercise": "biceps_curl",
            "repetitions": self.rep_count,
            "duration_s": round(self.elapsed_s, 2),
            "note": "Demo data only. No raw hardware ADC was acquired.",
        }
        import json

        (destination / "session.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        return destination
