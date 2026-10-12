/**
 * TrueRehab-RF wire protocol, version 1.1.
 *
 * Every input (Pi bridge, Web Serial, replay file, mock) produces these messages,
 * so the UI never depends on where data comes from.
 * Full spec with byte layout: frontend/README.md. Python twin: pi-bridge/truerehab_bridge/protocol.py.
 *
 * v1.1 adds (all optional, v1 senders still work):
 * - `hello`: the sender describes itself and lists every stream it will send (the manifest)
 * - commands web → Pi (`command`) with `ack` replies
 * - device health and session info in `status`; `kitId` / `sessionId` on every message
 *
 * This file is shared with the Node mock server, so it must stay DOM-free and
 * use erasable TypeScript only (no enums).
 */

/** Envelope `v`: the major version. Breaking changes bump it. */
export const PROTOCOL_VERSION = 1;
/** Full version announced in `hello`. */
export const PROTOCOL_VERSION_STRING = '1.1';

/** Fields every sensor message carries. */
export interface Envelope {
  /** Protocol major version. */
  v: number;
  /** Sender sequence number, +1 per broadcast message. Gaps mean dropped messages. -1 = not sequenced (hello, replies). */
  seq: number;
  /** Sensor-side timestamp in ms since Unix epoch (the Pi's clock). Plots use this, not arrival time. */
  t: number;
  /** Sender id, e.g. "pi5-radar" or "arduino". Sequence gaps are tracked per sender. */
  src?: string;
  /** Which kit sent this (see the multi-kit plan), e.g. "KIT-01". */
  kitId?: string;
  /** Active session, if one is running. */
  sessionId?: string;
  /** Set by the receiver (host clock, ms). Never sent on the wire. */
  recvT?: number;
}

/** Radar map views. Open-ended: any string is accepted. */
export type FrameView =
  | 'range_doppler'
  | 'micro_doppler'
  | 'range_time'
  | 'range_azimuth'
  | (string & {});

export interface AxisInfo {
  label: string;
  unit?: string;
  min: number;
  max: number;
}

/** One processed radar map, row-major, `shape = [rows, cols]`. */
export interface FrameMessage extends Envelope {
  type: 'frame';
  view: FrameView;
  shape: [number, number];
  data: Float32Array;
  frameIndex?: number;
  /** x = columns, y = rows. */
  axes?: { x?: AxisInfo; y?: AxisInfo };
  /** Unit of the values, e.g. "dB". */
  unit?: string;
}

export interface ScoreValue {
  /** Normally 0–1. */
  value: number;
  /** Optional model confidence, 0–1. Not automatically calibrated. */
  confidence?: number;
}

/** Model outputs. Keys are open (fatigue, quality, compensation, ...). */
export interface ScoresMessage extends Envelope {
  type: 'scores';
  scores: Record<string, ScoreValue>;
}

export type RecommendationAction =
  | 'continue'
  | 'correct_posture'
  | 'reduce_load'
  | 'rest'
  | 'see_physio'
  | (string & {});

export type EventKind =
  | 'rep_start'
  | 'rep_end'
  | 'compensation'
  | 'recommendation'
  | 'session_start'
  | 'session_end'
  | 'marker'
  | (string & {});

/**
 * Discrete events. Conventions for `data`:
 * - rep_start / rep_end: `{ rep: number, romDeg?: number }`
 * - compensation: `{ pattern: string, severity?: number }`
 * - recommendation: `{ action: RecommendationAction, reason?: string }`
 * - session_start / session_end: `{ session: SessionInfo }`
 * - marker: `{ label: string }`
 */
export interface EventMessage extends Envelope {
  type: 'event';
  kind: EventKind;
  label?: string;
  data?: Record<string, unknown>;
}

/** Ground-truth / auxiliary channels (sEMG, force, joint angle, ...), one sample each. */
export interface AuxMessage extends Envelope {
  type: 'aux';
  channels: Record<string, number>;
}

export type DeviceState = 'ok' | 'missing' | 'error' | 'off';

export interface DeviceHealth {
  state: DeviceState;
  /** Display name, e.g. "Radar (AWR1843)". */
  label?: string;
  /** Plain-language detail, e.g. "Not plugged in". */
  message?: string;
}

export interface SessionInfo {
  id: string;
  state: 'running' | 'stopped';
  exercise?: string;
  side?: 'left' | 'right' | (string & {});
  targetReps?: number;
  /** ms since epoch. */
  startedAt?: number;
  endedAt?: number;
  /** Pseudonymous user id, never a name. */
  userId?: string;
}

/** Sender health. Send about once per second. */
export interface StatusMessage extends Envelope {
  type: 'status';
  fps?: number;
  /** True when the data is synthetic. The UI shows a banner. */
  synthetic?: boolean;
  message?: string;
  /** Keyed by device id, e.g. radar, dca1000, arduino, model. */
  devices?: Record<string, DeviceHealth>;
  session?: SessionInfo | null;
  cpuTempC?: number;
  clients?: number;
  info?: Record<string, unknown>;
}

// ---------- v1.1: self-description ----------

export interface FrameStreamInfo {
  view: FrameView;
  label?: string;
  shape: [number, number];
  axes?: { x?: AxisInfo; y?: AxisInfo };
  unit?: string;
  fps: number;
  /** Plain-language explanation for the ⓘ button. */
  description?: string;
}

export interface ScoreInfo {
  key: string;
  label: string;
  /** Fatigue/compensation: true. Quality: false. */
  higherIsWorse: boolean;
  /** [warn, bad] on the badness scale, 0–1. */
  thresholds?: [number, number];
  description?: string;
  /** Updates per second. */
  rateHz?: number;
}

export interface AuxChannelInfo {
  key: string;
  label: string;
  unit?: string;
  rateHz?: number;
  /** Which device produces it (matches a key in status.devices). */
  device?: string;
}

export interface ActionInfo {
  key: RecommendationAction;
  label: string;
  hint?: string;
  tone: 'good' | 'warn' | 'bad' | 'info';
}

/** Everything the sender will send and accept. The UI labels itself from this. */
export interface Manifest {
  frames: FrameStreamInfo[];
  scores: ScoreInfo[];
  aux: AuxChannelInfo[];
  events: EventKind[];
  actions: ActionInfo[];
  commands: CommandName[];
  /** How often `status` arrives. Default 1000. */
  statusIntervalMs?: number;
}

/** First message after connect. Not sequenced (seq = -1). */
export interface HelloMessage extends Envelope {
  type: 'hello';
  /** "major.minor", e.g. "1.1". */
  protocol: string;
  device: {
    name: string;
    kitId?: string;
    bridgeVersion?: string;
    firmware?: Record<string, string>;
  };
  synthetic: boolean;
  manifest: Manifest;
  session?: SessionInfo | null;
}

export type SensorMessage =
  | FrameMessage
  | ScoresMessage
  | EventMessage
  | AuxMessage
  | StatusMessage
  | HelloMessage;

export type SensorMessageType = SensorMessage['type'];

// ---------- link control (WebSocket only) ----------

export type CommandName = 'session.start' | 'session.stop' | 'marker' | (string & {});

/** Args for `session.start`. All optional; the Pi fills defaults. */
export interface SessionStartArgs {
  exercise?: string;
  side?: string;
  targetReps?: number;
  sessionId?: string;
  userId?: string;
}

/** Web → Pi. The Pi answers with an `ack` carrying the same id. */
export interface CommandMessage {
  type: 'command';
  id: number;
  name: CommandName;
  args?: Record<string, unknown>;
}

export interface AckMessage {
  type: 'ack';
  id: number;
  ok: boolean;
  error?: string;
  result?: Record<string, unknown>;
}

/** Client sends ping, server echoes pong for round-trip time. */
export interface PingMessage {
  type: 'ping';
  id: number;
  clientT: number;
}

export interface PongMessage {
  type: 'pong';
  id: number;
  clientT: number;
  t?: number;
}

export type ControlMessage = AckMessage | PongMessage;

/** Binary frame element types. Integer types are rescaled with `scale = [min, max]`. */
export type FrameDType = 'f32' | 'u8' | 'u16';

/** Parse "1.1" → [1, 1]. */
export function parseProtocolVersion(s: string | undefined): [number, number] {
  const [major, minor] = String(s ?? '1.0').split('.').map((n) => Number(n) || 0);
  return [major, minor ?? 0];
}
