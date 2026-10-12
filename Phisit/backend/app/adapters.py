"""Replaceable input and inference interfaces.

The simulation intentionally does not claim to transform radar reflections into
physiological measurements. Real signal processing and trained inference can
implement these interfaces after collection and validation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from math import cos, pi, sin

from .schemas import AITelemetry


@dataclass(frozen=True)
class RadarSample:
    elapsed_s: float
    normalized_movement: float
    range_m: float
    velocity_mps: float
    signal_strength: float
    phase: str


@dataclass(frozen=True)
class RadarFeatures:
    elapsed_s: float
    normalized_movement: float
    range_m: float
    velocity_mps: float
    doppler_hz: float
    signal_strength: float
    phase: str


class RadarSource(ABC):
    @abstractmethod
    def read_frame(self, elapsed_s: float) -> RadarSample:
        """Return one input sample from the selected source."""


class SimulationRadarSource(RadarSource):
    period_s = 3.0

    def read_frame(self, elapsed_s: float) -> RadarSample:
        phase = 2 * pi * elapsed_s / self.period_s
        movement = 0.5 - 0.5 * cos(phase) + 0.012 * sin(phase * 2.1)
        velocity = 0.16 * pi / self.period_s * sin(phase)
        return RadarSample(
            elapsed_s=elapsed_s,
            normalized_movement=max(0.0, min(1.0, movement)),
            range_m=1.35 + 0.16 * (movement - 0.5),
            velocity_mps=velocity,
            signal_strength=0.78 + 0.05 * sin(phase * 0.4),
            phase="Concentric" if velocity >= 0 else "Eccentric",
        )


class DCA1000RadarSource(RadarSource):
    def read_frame(self, elapsed_s: float) -> RadarSample:
        raise NotImplementedError(
            "DCA1000 acquisition requires hardware drivers and a validated signal pipeline."
        )


class SignalProcessor(ABC):
    @abstractmethod
    def extract_features(self, sample: RadarSample) -> RadarFeatures:
        """Convert a source sample into model-ready features."""


class SimulationSignalProcessor(SignalProcessor):
    def extract_features(self, sample: RadarSample) -> RadarFeatures:
        # This is an illustrative synthetic feature stream, not an ADC FFT.
        return RadarFeatures(
            elapsed_s=sample.elapsed_s,
            normalized_movement=sample.normalized_movement,
            range_m=sample.range_m,
            velocity_mps=sample.velocity_mps,
            doppler_hz=2 * sample.velocity_mps / (299_792_458 / 77_000_000_000),
            signal_strength=sample.signal_strength,
            phase=sample.phase,
        )


class AIModel(ABC):
    @abstractmethod
    def predict(self, features: RadarFeatures, repetition: int) -> tuple[int, AITelemetry]:
        """Return movement quality and model outputs from features."""


# Hand-designed exhibition story points. They are not fitted to human data.
DEMO_ANCHORS = {
    0: (95, 0.08, 0.03, 0.08),
    1: (94, 0.12, 0.05, 0.10),
    3: (92, 0.24, 0.08, 0.19),
    5: (86, 0.42, 0.12, 0.38),
    6: (83, 0.52, 0.17, 0.54),
    7: (78, 0.61, 0.23, 0.75),
    8: (72, 0.70, 0.34, 0.82),
    9: (63, 0.79, 0.52, 0.91),
    10: (58, 0.86, 0.64, 0.96),
}


def demo_indices(repetition: int) -> tuple[int, float, float, float]:
    rep = max(0, min(10, repetition))
    if rep in DEMO_ANCHORS:
        return DEMO_ANCHORS[rep]
    lower = max(key for key in DEMO_ANCHORS if key < rep)
    upper = min(key for key in DEMO_ANCHORS if key > rep)
    share = (rep - lower) / (upper - lower)
    a, b = DEMO_ANCHORS[lower], DEMO_ANCHORS[upper]
    values = tuple(a[i] + (b[i] - a[i]) * share for i in range(4))
    return round(values[0]), values[1], values[2], values[3]


class SimulationAIModel(AIModel):
    def predict(self, features: RadarFeatures, repetition: int) -> tuple[int, AITelemetry]:
        quality, fatigue, compensation, risk = demo_indices(repetition)
        # Small deterministic variation keeps streaming values organic and testable.
        motion_variation = 0.004 * sin(features.elapsed_s * 1.7)
        fatigue = max(0.0, min(1.0, fatigue + motion_variation))
        compensation = max(0.0, min(1.0, compensation + motion_variation * 0.4))
        risk = max(0.0, min(1.0, risk + motion_variation * 0.6))
        prediction = None if repetition >= 9 else (2 if risk >= 0.7 else 3 if risk >= 0.45 else None)
        return quality, AITelemetry(
            fatigue_estimate=round(fatigue, 3),
            compensation_level=round(compensation, 3),
            compensation_risk=round(risk, 3),
            predicted_reps_to_compensation=prediction,
        )


class PyTorchAIModel(AIModel):
    def predict(self, features: RadarFeatures, repetition: int) -> tuple[int, AITelemetry]:
        raise NotImplementedError(
            "A trained, validated model must be supplied before hardware inference is enabled."
        )
