/**
 * SYNTHETIC data generator. Not a radar model. It only produces plausible-looking
 * messages so the UI and the transport can be tested without hardware.
 * Python twin: pi-bridge/truerehab_bridge/providers/synthetic.py.
 *
 * Scenario: seated elbow flexion, one rep every `repPeriodS`. Fatigue ramps up over
 * about two minutes, ROM shrinks, and compensation (trunk lean) appears late. Then it loops.
 * Starting a session resets fatigue and the rep count.
 *
 * Shared by MockSource (browser) and mock-server (Node): keep it DOM-free.
 */
import type {
  AckMessage,
  AuxMessage,
  EventMessage,
  FrameMessage,
  HelloMessage,
  Manifest,
  RecommendationAction,
  ScoresMessage,
  SensorMessage,
  SessionInfo,
  StatusMessage,
} from './protocol.ts';
import { PROTOCOL_VERSION, PROTOCOL_VERSION_STRING } from './protocol.ts';

export interface MockOptions {
  fps?: number;
  rows?: number;
  cols?: number;
  repPeriodS?: number;
  /** Length of one fatigue cycle before it resets, seconds. */
  cycleS?: number;
  src?: string;
  kitId?: string;
}

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const sigmoid = (x: number) => 1 / (1 + Math.exp(-x));
const noise = (s: number) => (Math.random() + Math.random() + Math.random() - 1.5) * s;
const newId = () => `S-${Date.now().toString(36)}-${Math.floor(Math.random() * 1e4).toString(36)}`;

/** The manifest the mock (and the Python synthetic provider) announce. */
export function mockManifest(fps: number, rows: number, cols: number): Manifest {
  return {
    frames: [
      {
        view: 'range_doppler',
        label: 'Range–Doppler',
        shape: [rows, cols],
        unit: 'dB',
        fps,
        axes: {
          x: { label: 'Velocity', unit: 'm/s', min: -2, max: 2 },
          y: { label: 'Range', unit: 'm', min: 0, max: 3 },
        },
        description:
          'Each bright spot is something reflecting the radar. Up/down = distance from the radar. Left/right = how fast it moves toward (right) or away (left). A moving arm makes a spot that swings sideways.',
      },
    ],
    scores: [
      { key: 'fatigue', label: 'Fatigue', higherIsWorse: true, thresholds: [0.4, 0.7], rateHz: 4, description: 'How tired the working muscle seems. Lower is better.' },
      { key: 'quality', label: 'Movement quality', higherIsWorse: false, thresholds: [0.4, 0.7], rateHz: 4, description: 'Smoothness and range of the movement. Higher is better.' },
      { key: 'compensation', label: 'Compensation', higherIsWorse: true, thresholds: [0.4, 0.7], rateHz: 4, description: 'How much other body parts (trunk, shoulder) are helping. Lower is better.' },
    ],
    aux: [
      { key: 'elbow_angle_deg', label: 'Elbow angle', unit: '°', rateHz: fps, device: 'camera' },
      { key: 'emg_rms', label: 'sEMG (biceps)', unit: 'RMS', rateHz: fps, device: 'arduino' },
      { key: 'force_n', label: 'Force', unit: 'N', rateHz: fps, device: 'arduino' },
    ],
    events: ['rep_start', 'rep_end', 'compensation', 'recommendation', 'session_start', 'session_end', 'marker'],
    actions: [
      { key: 'continue', label: 'Continue', hint: 'Form looks good. Keep going.', tone: 'good' },
      { key: 'correct_posture', label: 'Correct posture', hint: 'Sit upright and keep the shoulder down.', tone: 'warn' },
      { key: 'reduce_load', label: 'Reduce load or range', hint: 'Use a lighter weight or a smaller range.', tone: 'warn' },
      { key: 'rest', label: 'Rest', hint: 'Take a break before the next set.', tone: 'bad' },
      { key: 'see_physio', label: 'See your physiotherapist', hint: 'The pattern keeps coming back. Get it checked.', tone: 'bad' },
    ],
    commands: ['session.start', 'session.stop', 'marker'],
    statusIntervalMs: 1000,
  };
}

export class MockGenerator {
  readonly fps: number;
  readonly rows: number;
  readonly cols: number;
  readonly repPeriodS: number;
  readonly cycleS: number;
  readonly src: string;
  readonly kitId: string;

  private seq = 0;
  private frameIndex = 0;
  private start: number | null = null;
  private lastPhase = 0;
  private rep = 0;
  private repMinAngle = Infinity;
  private repMaxAngle = -Infinity;
  private lastScoresT = 0;
  private lastStatusT = 0;
  private compensating = false;
  private latest = { fatigue: 0, quality: 1, compensation: 0 };
  private session: SessionInfo | null = null;
  /** Messages produced by commands, flushed on the next tick. */
  private pending: SensorMessage[] = [];

  constructor(opts: MockOptions = {}) {
    this.fps = opts.fps ?? 20;
    this.rows = opts.rows ?? 64;
    this.cols = opts.cols ?? 64;
    this.repPeriodS = opts.repPeriodS ?? 3.2;
    this.cycleS = opts.cycleS ?? 150;
    this.src = opts.src ?? 'mock';
    this.kitId = opts.kitId ?? 'KIT-DEMO';
  }

  private env(t: number) {
    return { v: PROTOCOL_VERSION, seq: this.seq++, t, src: this.src, kitId: this.kitId, ...(this.session?.state === 'running' ? { sessionId: this.session.id } : {}) };
  }

  hello(now = Date.now()): HelloMessage {
    return {
      v: PROTOCOL_VERSION,
      seq: -1,
      t: now,
      src: this.src,
      kitId: this.kitId,
      type: 'hello',
      protocol: PROTOCOL_VERSION_STRING,
      device: { name: 'Demo kit (synthetic)', kitId: this.kitId, bridgeVersion: 'mock-0.2' },
      synthetic: true,
      manifest: mockManifest(this.fps, this.rows, this.cols),
      session: this.session,
    };
  }

  /** Handle a web → Pi command the way the real bridge does. */
  handleCommand(id: number, name: string, args: Record<string, unknown> = {}, now = Date.now()): AckMessage {
    if (name === 'session.start') {
      if (this.session?.state === 'running') return { type: 'ack', id, ok: false, error: 'A session is already running' };
      this.session = {
        id: typeof args.sessionId === 'string' ? args.sessionId : newId(),
        state: 'running',
        exercise: typeof args.exercise === 'string' ? args.exercise : 'elbow_flexion',
        side: typeof args.side === 'string' ? args.side : 'right',
        targetReps: typeof args.targetReps === 'number' ? args.targetReps : undefined,
        userId: typeof args.userId === 'string' ? args.userId : undefined,
        startedAt: now,
      };
      // Fresh start: fatigue and reps reset.
      this.start = now;
      this.rep = 0;
      this.lastPhase = 0;
      this.pending.push(this.event(now, 'session_start', { session: { ...this.session } }, 'Session started'));
      return { type: 'ack', id, ok: true, result: { session: this.session } };
    }
    if (name === 'session.stop') {
      if (this.session?.state !== 'running') return { type: 'ack', id, ok: false, error: 'No session is running' };
      const ended = { ...this.session, state: 'stopped' as const, endedAt: now };
      this.pending.push(this.event(now, 'session_end', { session: ended, reps: this.rep }, 'Session ended'));
      this.session = ended;
      return { type: 'ack', id, ok: true, result: { session: ended, reps: this.rep } };
    }
    if (name === 'marker') {
      const label = typeof args.label === 'string' && args.label ? args.label : 'Marker';
      this.pending.push(this.event(now, 'marker', { label }, label));
      return { type: 'ack', id, ok: true };
    }
    return { type: 'ack', id, ok: false, error: `Unknown command "${name}"` };
  }

  /** Call once per tick (1000 / fps ms) with the current time in ms. */
  next(now: number): SensorMessage[] {
    if (this.start === null) this.start = now;
    const out: SensorMessage[] = this.pending.splice(0);
    const elapsed = (now - this.start) / 1000;
    const cycleT = elapsed % this.cycleS;
    const fatigue = clamp01(cycleT / (this.cycleS * 0.8) + noise(0.02));
    const compensation = clamp01(sigmoid((fatigue - 0.62) * 12) * 0.92 + noise(0.04));
    const quality = clamp01(1 - 0.55 * compensation - 0.25 * fatigue + noise(0.03));
    this.latest = { fatigue, quality, compensation };

    // Elbow angle: 20° (extended) to ~130° (flexed). ROM shrinks with fatigue.
    const phase = (elapsed % this.repPeriodS) / this.repPeriodS;
    const rom = 110 * (1 - 0.35 * fatigue);
    const angle = 20 + rom * (0.5 - 0.5 * Math.cos(2 * Math.PI * phase));
    const angVel = (rom * Math.PI * Math.sin(2 * Math.PI * phase)) / this.repPeriodS; // deg/s
    this.repMinAngle = Math.min(this.repMinAngle, angle);
    this.repMaxAngle = Math.max(this.repMaxAngle, angle);

    // Rep boundaries: phase wraps.
    if (phase < this.lastPhase) {
      if (this.rep > 0) {
        out.push(this.event(now, 'rep_end', { rep: this.rep, romDeg: +(this.repMaxAngle - this.repMinAngle).toFixed(1) }));
        out.push(this.event(now, 'recommendation', this.recommend()));
      }
      this.rep += 1;
      this.repMinAngle = Infinity;
      this.repMaxAngle = -Infinity;
      out.push(this.event(now, 'rep_start', { rep: this.rep }));
    }
    this.lastPhase = phase;

    if (!this.compensating && compensation > 0.6) {
      this.compensating = true;
      out.push(this.event(now, 'compensation', { pattern: 'trunk_lean', severity: +compensation.toFixed(2) }, 'Trunk lean detected'));
    } else if (this.compensating && compensation < 0.45) {
      this.compensating = false;
    }

    out.push(this.frame(now, angle, angVel, compensation));

    const emg = clamp01(0.15 + 0.5 * Math.abs(Math.sin(2 * Math.PI * phase)) * (1 + fatigue) + noise(0.05));
    const aux: AuxMessage = {
      ...this.env(now),
      type: 'aux',
      channels: { elbow_angle_deg: +angle.toFixed(2), emg_rms: +emg.toFixed(3), force_n: +(20 + 4 * Math.sin(2 * Math.PI * phase) + noise(0.8)).toFixed(2) },
    };
    out.push(aux);

    if (now - this.lastScoresT >= 250) {
      this.lastScoresT = now;
      const scores: ScoresMessage = {
        ...this.env(now),
        type: 'scores',
        scores: {
          fatigue: { value: fatigue, confidence: clamp01(0.75 + noise(0.1)) },
          quality: { value: quality, confidence: clamp01(0.8 + noise(0.1)) },
          compensation: { value: compensation, confidence: clamp01(0.7 + noise(0.1)) },
        },
      };
      out.push(scores);
    }

    if (now - this.lastStatusT >= 1000) {
      this.lastStatusT = now;
      out.push(this.status(now));
    }
    return out;
  }

  /**
   * Messages a command produced, plus a fresh status, in sequence order.
   * Send these right after the ack so every viewer sees the change at once.
   */
  drain(now = Date.now()): SensorMessage[] {
    return [...this.pending.splice(0), this.status(now)];
  }

  status(now = Date.now()): StatusMessage {
    return {
      ...this.env(now),
      type: 'status',
      fps: this.fps,
      synthetic: true,
      message: 'Synthetic demo data, not a measurement',
      devices: {
        radar: { state: 'ok', label: 'Radar', message: 'Simulated' },
        arduino: { state: 'ok', label: 'Arduino (sEMG / force)', message: 'Simulated' },
        model: { state: 'ok', label: 'AI model', message: 'Simulated scores' },
      },
      session: this.session,
    };
  }

  private recommend(): Record<string, unknown> {
    const { fatigue, compensation } = this.latest;
    let action: RecommendationAction = 'continue';
    let reason = 'Form and fatigue within range';
    if (compensation > 0.85 && fatigue > 0.9) {
      action = 'see_physio';
      reason = 'Persistent compensation at high fatigue';
    } else if (fatigue > 0.85) {
      action = 'rest';
      reason = 'High fatigue';
    } else if (compensation > 0.6) {
      action = 'correct_posture';
      reason = 'Trunk lean during the rep';
    } else if (fatigue > 0.65) {
      action = 'reduce_load';
      reason = 'Fatigue rising, range of motion shrinking';
    }
    return { action, reason };
  }

  private event(t: number, kind: string, data?: Record<string, unknown>, label?: string): EventMessage {
    return { ...this.env(t), type: 'event', kind, data, label };
  }

  /** Range–Doppler-like map in dB: static clutter, a moving forearm, a torso that sways when compensating. */
  private frame(t: number, angle: number, angVel: number, comp: number): FrameMessage {
    const { rows, cols } = this;
    const data = new Float32Array(rows * cols);
    const c0 = cols / 2;
    const armRow = rows * 0.34 + 3 * Math.sin((angle * Math.PI) / 180);
    const armCol = c0 + angVel * 0.09;
    const torsoCol = c0 + comp * 3 * Math.sin(t / 400);
    const blobs = [
      { r: rows * 0.2, c: c0, a: 1.0, sr: 0.8, sc: 0.6 }, // static clutter (chair / wall)
      { r: armRow, c: armCol, a: 0.6, sr: 1.2, sc: 1.6 }, // forearm, micro-Doppler spread
      { r: rows * 0.3, c: torsoCol, a: 0.4, sr: 1.5, sc: 0.8 + comp * 2 }, // torso
    ];
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        let lin = 0.01 * (1 + Math.abs(noise(0.6)));
        for (const b of blobs) {
          const dr = (r - b.r) / b.sr;
          const dc = (c - b.c) / b.sc;
          lin += b.a * Math.exp(-0.5 * (dr * dr + dc * dc));
        }
        data[r * cols + c] = 20 * Math.log10(lin);
      }
    }
    return {
      ...this.env(t),
      type: 'frame',
      view: 'range_doppler',
      shape: [rows, cols],
      data,
      frameIndex: this.frameIndex++,
      unit: 'dB',
      axes: {
        x: { label: 'Velocity', unit: 'm/s', min: -2, max: 2 },
        y: { label: 'Range', unit: 'm', min: 0, max: 3 },
      },
    };
  }
}
