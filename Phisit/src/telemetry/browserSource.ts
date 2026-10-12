import { demoIndices, recommendationFor, syntheticHeatmap, syntheticRadar, trendPoint } from './demoModel';
import { EXPORT_FIELDS, type SignalPoint, type TelemetryFrame, type TelemetrySource, type TrendPoint } from './types';

const round = (value: number, digits = 3) => Number(value.toFixed(digits));

/** Same telemetry contract as the Python backend for private static-site demos. */
export class BrowserDemoSource implements TelemetrySource {
  readonly kind = 'browser';
  initial: TelemetryFrame;
  private listeners = new Set<(frame: TelemetryFrame) => void>();
  private interval: number | undefined;
  private lastClock = performance.now();
  private elapsed = 21;
  private rep = 7;
  private running = false;
  private hasStarted = false;
  private sessionId = 'demo-preview';
  private framesReceived = 0;
  private previousSignal: number | null = null;
  private previousSlope = 0;
  private lastPeak = -100;
  private signalHistory: SignalPoint[] = [];
  private trendHistory: TrendPoint[] = [];
  private records: string[][] = [];

  constructor() {
    for (let index = 0; index < 120; index += 1) {
      const time = 15 + index * .05;
      this.signalHistory.push({ time_s: round(time, 2), value: round(syntheticRadar(time).signal) });
    }
    this.trendHistory = Array.from({ length: 7 }, (_, index) => trendPoint(index + 1));
    this.initial = this.makeFrame();
  }

  subscribe(listener: (frame: TelemetryFrame) => void): () => void {
    this.listeners.add(listener);
    listener(this.initial);
    return () => this.listeners.delete(listener);
  }

  private emit(): void {
    this.initial = this.makeFrame();
    this.listeners.forEach(listener => listener(this.initial));
  }

  private clear(): void {
    this.elapsed = 0;
    this.rep = 0;
    this.running = false;
    this.hasStarted = true;
    this.framesReceived = 0;
    this.previousSignal = null;
    this.previousSlope = 0;
    this.lastPeak = -100;
    this.signalHistory = [];
    this.trendHistory = [];
    this.records = [];
    this.sessionId = `demo-${new Date().toISOString().replace(/[:.]/g, '-')}`;
  }

  private tick = (): void => {
    const now = performance.now();
    const delta = Math.min(Math.max((now - this.lastClock) / 1000, 0), .25);
    this.lastClock = now;
    if (!this.running) return;
    this.elapsed += delta;
    this.framesReceived += 1;
    const radar = syntheticRadar(this.elapsed);
    this.signalHistory.push({ time_s: round(this.elapsed, 2), value: round(radar.signal) });
    if (this.signalHistory.length > 160) this.signalHistory.shift();
    if (this.previousSignal !== null) {
      const slope = radar.signal - this.previousSignal;
      if (this.previousSlope > 0 && slope <= 0 && this.previousSignal >= .78 && this.elapsed - this.lastPeak >= 2) {
        this.lastPeak = this.elapsed;
        this.rep = Math.min(10, this.rep + 1);
        this.trendHistory.push(trendPoint(this.rep));
        if (this.rep >= 10) this.running = false;
      }
      this.previousSlope = slope;
    }
    this.previousSignal = radar.signal;
    const frame = this.makeFrame();
    this.records.push([
      new Date(frame.timestamp * 1000).toISOString(), String(frame.movement.rep_count),
      String(frame.movement.normalized_signal), String(frame.movement.movement_quality),
      String(frame.ai.fatigue_estimate), String(frame.ai.compensation_level),
      String(frame.ai.compensation_risk), frame.recommendation.status,
    ]);
    this.emit();
  };

  private makeFrame(): TelemetryFrame {
    const radar = syntheticRadar(this.elapsed);
    const [quality, fatigueBase, compensationBase, riskBase] = demoIndices(this.rep);
    const variation = .004 * Math.sin(this.elapsed * 1.7);
    const fatigue = round(Math.max(0, Math.min(1, fatigueBase + variation)));
    const compensation = round(Math.max(0, Math.min(1, compensationBase + variation * .4)));
    const risk = round(Math.max(0, Math.min(1, riskBase + variation * .6)));
    return {
      timestamp: Date.now() / 1000,
      session_id: this.sessionId,
      mode: 'simulation',
      data_source: 'BROWSER SIMULATION',
      exercise: 'biceps_curl',
      running: this.running,
      session_seconds: round(this.elapsed, 2),
      subject_id: 'DEMO SUBJECT',
      radar: {
        connected: true, capture_connected: true, range_m: round(radar.range),
        velocity_mps: round(radar.velocity), doppler_hz: round(2 * radar.velocity / (299_792_458 / 77_000_000_000), 2),
        signal_strength: round(radar.strength),
      },
      movement: { normalized_signal: round(radar.signal), rep_count: this.rep, movement_quality: quality, phase: this.running ? radar.phase : 'Idle' },
      ai: { fatigue_estimate: fatigue, compensation_level: compensation, compensation_risk: risk, predicted_reps_to_compensation: this.rep >= 9 ? null : risk >= .7 ? 2 : risk >= .45 ? 3 : null },
      recommendation: recommendationFor(this.rep),
      system: {
        radar: 'SIMULATED / CONNECTED', capture: 'SIMULATED / CONNECTED', radar_stream: this.running ? 'ACTIVE' : 'READY',
        ai_engine: 'DEMO MODEL', imu: 'NOT CONNECTED', semg: 'NOT CONNECTED', calibration: 'NOT CALIBRATED',
      },
      debug: {
        frame_rate_hz: 20, radar_frames_received: this.framesReceived, processing_latency_ms: .3,
        ai_inference_latency_ms: .1, packet_status: 'SIMULATED / OK',
      },
      signal_history: [...this.signalHistory], trend_history: [...this.trendHistory],
      range_doppler: syntheticHeatmap(this.elapsed, radar.range, radar.velocity),
    };
  }

  async start(): Promise<void> {
    if (!this.hasStarted || this.rep >= 10) this.clear();
    this.running = true;
    this.lastClock = performance.now();
    if (this.interval === undefined) this.interval = window.setInterval(this.tick, 50);
    this.emit();
  }

  async stop(): Promise<void> { this.running = false; this.emit(); }
  async reset(): Promise<void> { this.clear(); this.emit(); }

  async exportCsv(): Promise<void> {
    const body = [EXPORT_FIELDS.join(','), ...this.records.map(row => row.join(','))].join('\n') + '\n';
    const url = URL.createObjectURL(new Blob([body], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `${this.sessionId}.csv`;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async saveSession(): Promise<string> {
    localStorage.setItem(`truerehab-session-${this.sessionId}`, JSON.stringify({
      session_id: this.sessionId, mode: 'simulation', exercise: 'biceps_curl',
      rows: this.records, saved_at: new Date().toISOString(),
    }));
    return 'Session saved in this browser';
  }

  dispose(): void {
    if (this.interval !== undefined) window.clearInterval(this.interval);
    this.listeners.clear();
  }
}
