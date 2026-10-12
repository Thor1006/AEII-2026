/** Contract mirrored by backend/app/schemas.py. UI components consume this shape only. */
export interface SignalPoint { time_s: number; value: number }
export interface TrendPoint {
  rep: number;
  movement_quality: number;
  fatigue_estimate: number;
  compensation_level: number;
  compensation_risk: number;
}
export type RecommendationStatus = 'continue' | 'monitor' | 'correct_form' | 'rest';
export interface TelemetryFrame {
  timestamp: number;
  session_id: string;
  mode: 'simulation' | 'hardware';
  data_source: string;
  exercise: 'biceps_curl';
  running: boolean;
  session_seconds: number;
  subject_id: string;
  radar: {
    connected: boolean;
    capture_connected: boolean;
    range_m: number;
    velocity_mps: number;
    doppler_hz: number;
    signal_strength: number;
  };
  movement: {
    normalized_signal: number;
    rep_count: number;
    movement_quality: number;
    phase: 'Concentric' | 'Eccentric' | 'Idle';
  };
  ai: {
    fatigue_estimate: number;
    compensation_level: number;
    compensation_risk: number;
    predicted_reps_to_compensation: number | null;
  };
  recommendation: {
    status: RecommendationStatus;
    title: string;
    message: string;
  };
  system: {
    radar: string;
    capture: string;
    radar_stream: string;
    ai_engine: string;
    imu: string;
    semg: string;
    calibration: string;
  };
  debug: {
    frame_rate_hz: number;
    radar_frames_received: number;
    processing_latency_ms: number;
    ai_inference_latency_ms: number;
    packet_status: string;
  };
  signal_history: SignalPoint[];
  trend_history: TrendPoint[];
  range_doppler: number[][];
}

export interface TelemetrySource {
  readonly kind: 'backend' | 'browser';
  readonly initial: TelemetryFrame;
  subscribe(listener: (frame: TelemetryFrame) => void): () => void;
  start(): Promise<void>;
  stop(): Promise<void>;
  reset(): Promise<void>;
  exportCsv(): Promise<void>;
  saveSession(): Promise<string>;
  dispose(): void;
}

export const EXPORT_FIELDS = [
  'timestamp', 'rep_count', 'movement_signal', 'movement_quality',
  'fatigue_estimate', 'compensation_level', 'compensation_risk', 'recommendation',
] as const;
