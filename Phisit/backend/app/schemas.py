"""Public telemetry contract shared with the React application."""

from typing import Literal

from pydantic import BaseModel


class RadarTelemetry(BaseModel):
    connected: bool
    capture_connected: bool
    range_m: float
    velocity_mps: float
    doppler_hz: float
    signal_strength: float


class MovementTelemetry(BaseModel):
    normalized_signal: float
    rep_count: int
    movement_quality: int
    phase: Literal["Concentric", "Eccentric", "Idle"]


class AITelemetry(BaseModel):
    fatigue_estimate: float
    compensation_level: float
    compensation_risk: float
    predicted_reps_to_compensation: int | None


class RecommendationTelemetry(BaseModel):
    status: Literal["continue", "monitor", "correct_form", "rest"]
    title: str
    message: str


class SystemTelemetry(BaseModel):
    radar: str
    capture: str
    radar_stream: str
    ai_engine: str
    imu: str
    semg: str
    calibration: str


class DebugTelemetry(BaseModel):
    frame_rate_hz: float
    radar_frames_received: int
    processing_latency_ms: float
    ai_inference_latency_ms: float
    packet_status: str


class SignalPoint(BaseModel):
    time_s: float
    value: float


class TrendPoint(BaseModel):
    rep: int
    movement_quality: int
    fatigue_estimate: float
    compensation_level: float
    compensation_risk: float


class TelemetryFrame(BaseModel):
    timestamp: float
    session_id: str
    mode: Literal["simulation", "hardware"]
    data_source: str
    exercise: Literal["biceps_curl"]
    running: bool
    session_seconds: float
    subject_id: str
    radar: RadarTelemetry
    movement: MovementTelemetry
    ai: AITelemetry
    recommendation: RecommendationTelemetry
    system: SystemTelemetry
    debug: DebugTelemetry
    signal_history: list[SignalPoint]
    trend_history: list[TrendPoint]
    range_doppler: list[list[float]]
