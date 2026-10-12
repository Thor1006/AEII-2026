import type {
  DeviceHealth,
  EventMessage,
  FrameMessage,
  HelloMessage,
  SensorMessage,
  SessionInfo,
  StatusMessage,
} from '../sensor/protocol.ts';
import { RingBuffer } from './RingBuffer.ts';

export interface TimedValue {
  /** Sensor time, ms. */
  t: number;
  v: number;
  /** Optional confidence, 0–1. */
  c?: number;
}

export interface LinkStats {
  received: number;
  dropped: number;
  /** Radar frames per second, measured on arrival. */
  fps: number;
  bytesPerSec: number;
  rttMs: number | null;
  /** Host time of the last message, ms. */
  lastRecvT: number | null;
  /** Host time of the first message, ms. */
  firstRecvT: number | null;
}

export interface SensorStoreOptions {
  /** Samples kept per score / aux channel. */
  historyLength?: number;
  eventLength?: number;
}

/** Stream ids: "frame:<view>", "score:<key>", "aux:<key>", "status". */
export type StreamId = string;

/**
 * Everything the dashboard shows, in bounded buffers. Not React-specific:
 * widgets read it directly and re-render on `subscribe` (throttled by useSensorStore).
 */
export class SensorStore {
  readonly frames = new Map<string, FrameMessage>();
  readonly scores = new Map<string, RingBuffer<TimedValue>>();
  readonly aux = new Map<string, RingBuffer<TimedValue>>();
  readonly events: RingBuffer<EventMessage>;
  /** The sender's self-description (protocol 1.1+). Null for v1 senders. */
  hello: HelloMessage | null = null;
  status: StatusMessage | null = null;
  session: SessionInfo | null = null;
  stats: LinkStats = emptyStats();
  /** Host time each stream was last seen. */
  readonly lastSeen = new Map<StreamId, number>();

  private readonly historyLength: number;
  private readonly lastSeq = new Map<string, number>();
  private readonly frameTimes = new RingBuffer<number>(30);
  private readonly byteLog = new RingBuffer<{ t: number; b: number }>(200);
  private readonly listeners = new Set<() => void>();
  private readonly rawListeners = new Set<(msg: SensorMessage) => void>();

  constructor(opts: SensorStoreOptions = {}) {
    this.historyLength = opts.historyLength ?? 3000;
    this.events = new RingBuffer(opts.eventLength ?? 300);
  }

  get devices(): Record<string, DeviceHealth> {
    return this.status?.devices ?? {};
  }

  /** True if the sender (hello or status) says the data is synthetic. */
  get synthetic(): boolean {
    return !!(this.hello?.synthetic || this.status?.synthetic);
  }

  ingest(msg: SensorMessage, bytes = 0): void {
    const now = msg.recvT ?? Date.now();
    this.trackSequence(msg);
    this.stats.received++;
    this.stats.lastRecvT = now;
    this.stats.firstRecvT ??= now;
    this.byteLog.push({ t: now, b: bytes });

    switch (msg.type) {
      case 'hello':
        this.hello = msg;
        if (msg.session !== undefined) this.session = msg.session;
        break;
      case 'frame':
        this.frames.set(msg.view, msg);
        this.frameTimes.push(now);
        this.lastSeen.set(`frame:${msg.view}`, now);
        break;
      case 'scores':
        for (const [key, s] of Object.entries(msg.scores)) {
          this.series(this.scores, key).push({ t: msg.t, v: s.value, c: s.confidence });
          this.lastSeen.set(`score:${key}`, now);
        }
        break;
      case 'aux':
        for (const [key, v] of Object.entries(msg.channels)) {
          this.series(this.aux, key).push({ t: msg.t, v });
          this.lastSeen.set(`aux:${key}`, now);
        }
        break;
      case 'event':
        this.events.push(msg);
        this.lastSeen.set(`event:${msg.kind}`, now);
        if ((msg.kind === 'session_start' || msg.kind === 'session_end') && isSession(msg.data?.session)) {
          this.session = msg.data.session;
        }
        break;
      case 'status':
        this.status = msg;
        if (msg.session !== undefined) this.session = msg.session;
        this.lastSeen.set('status', now);
        break;
    }

    this.updateRates(now);
    for (const fn of this.rawListeners) fn(msg);
    this.notify();
  }

  /** Update the session from a command reply without waiting for the next status. */
  setSession(session: SessionInfo | null): void {
    this.session = session;
    this.notify();
  }

  setRtt(ms: number): void {
    this.stats.rttMs = ms;
    this.notify();
  }

  reset(): void {
    this.frames.clear();
    this.scores.clear();
    this.aux.clear();
    this.events.clear();
    this.hello = null;
    this.status = null;
    this.session = null;
    this.stats = emptyStats();
    this.lastSeen.clear();
    this.lastSeq.clear();
    this.frameTimes.clear();
    this.byteLog.clear();
    this.notify();
  }

  /** Change notification. Fires per message; throttle in the UI. */
  subscribe(fn: () => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  /** Every incoming message, unthrottled (used by the recorder). */
  subscribeRaw(fn: (msg: SensorMessage) => void): () => void {
    this.rawListeners.add(fn);
    return () => this.rawListeners.delete(fn);
  }

  /** Events of one kind, newest last. */
  eventsOfKind(kind: string): EventMessage[] {
    return this.events.toArray().filter((e) => e.kind === kind);
  }

  /** Events since the current session started (all events if no session). */
  sessionEvents(kind?: string): EventMessage[] {
    const since = this.session?.startedAt ?? -Infinity;
    return this.events.toArray().filter((e) => e.t >= since && (!kind || e.kind === kind));
  }

  private series(map: Map<string, RingBuffer<TimedValue>>, key: string): RingBuffer<TimedValue> {
    let buf = map.get(key);
    if (!buf) {
      buf = new RingBuffer(this.historyLength);
      map.set(key, buf);
    }
    return buf;
  }

  private trackSequence(msg: SensorMessage): void {
    if (msg.seq < 0) return; // not sequenced (hello, or a sender that doesn't number messages)
    const key = msg.src ?? '';
    const last = this.lastSeq.get(key);
    if (last !== undefined && msg.seq > last + 1) this.stats.dropped += msg.seq - last - 1;
    // seq <= last means the sender restarted; just resync.
    this.lastSeq.set(key, msg.seq);
  }

  private updateRates(now: number): void {
    const n = this.frameTimes.size;
    if (n >= 2) {
      const span = (this.frameTimes.last()! - this.frameTimes.at(0)!) / 1000;
      this.stats.fps = span > 0 ? (n - 1) / span : 0;
    }
    let bytes = 0;
    for (const { t, b } of this.byteLog.toArray()) if (now - t <= 1000) bytes += b;
    this.stats.bytesPerSec = bytes;
  }

  private notify(): void {
    for (const fn of this.listeners) fn();
  }
}

function isSession(x: unknown): x is SessionInfo {
  return !!x && typeof x === 'object' && typeof (x as SessionInfo).id === 'string';
}

function emptyStats(): LinkStats {
  return { received: 0, dropped: 0, fps: 0, bytesPerSec: 0, rttMs: null, lastRecvT: null, firstRecvT: null };
}
