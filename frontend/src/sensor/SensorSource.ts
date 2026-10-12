import type { AckMessage, CommandName, SensorMessage } from './protocol.ts';

export type SourceState = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'closed' | 'error';

export interface MessageMeta {
  /** Size on the wire, for throughput stats. */
  bytes: number;
}

export type MessageHandler = (msg: SensorMessage, meta: MessageMeta) => void;
export type StateHandler = (state: SourceState, error?: string) => void;
export type Unsubscribe = () => void;

/**
 * Anything that produces protocol messages. To add an input, implement this
 * (usually by extending BaseSource) and register it in sources/index.ts.
 */
export interface SensorSource {
  readonly kind: string;
  readonly label: string;
  readonly state: SourceState;
  readonly error?: string;
  /** May need a user gesture (Web Serial), so call it straight from a click handler. */
  connect(): Promise<void>;
  disconnect(): void;
  onMessage(handler: MessageHandler): Unsubscribe;
  onState(handler: StateHandler): Unsubscribe;
  /** Round-trip time in ms, if the transport can measure it. */
  onRtt?(handler: (ms: number) => void): Unsubscribe;
  /** Fired when time jumps backwards (e.g. replay restart); the store clears history. */
  onReset?(handler: () => void): Unsubscribe;
  /** Send a command (session.start, ...) and wait for the ack. Only sources that talk back implement it. */
  command?(name: CommandName, args?: Record<string, unknown>): Promise<AckMessage>;
}

export class CommandError extends Error {}

/** Optional playback controls (replay). Detect with `isPlayback`. */
export interface Playback {
  readonly playing: boolean;
  readonly speed: number;
  /** 0–1 */
  readonly progress: number;
  play(): void;
  pause(): void;
  setSpeed(speed: number): void;
  restart(): void;
}

export function isPlayback(source: SensorSource | null): source is SensorSource & Playback {
  return !!source && typeof (source as Partial<Playback>).play === 'function';
}

/** Handler bookkeeping shared by all sources. */
export abstract class BaseSource implements SensorSource {
  abstract readonly kind: string;
  abstract readonly label: string;
  state: SourceState = 'idle';
  error?: string;

  private messageHandlers = new Set<MessageHandler>();
  private stateHandlers = new Set<StateHandler>();
  private rttHandlers = new Set<(ms: number) => void>();
  private resetHandlers = new Set<() => void>();

  abstract connect(): Promise<void>;
  abstract disconnect(): void;

  onMessage(handler: MessageHandler): Unsubscribe {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  onState(handler: StateHandler): Unsubscribe {
    this.stateHandlers.add(handler);
    return () => this.stateHandlers.delete(handler);
  }

  onRtt(handler: (ms: number) => void): Unsubscribe {
    this.rttHandlers.add(handler);
    return () => this.rttHandlers.delete(handler);
  }

  onReset(handler: () => void): Unsubscribe {
    this.resetHandlers.add(handler);
    return () => this.resetHandlers.delete(handler);
  }

  protected emit(msg: SensorMessage, bytes = 0): void {
    msg.recvT = Date.now();
    for (const h of this.messageHandlers) h(msg, { bytes });
  }

  protected setState(state: SourceState, error?: string): void {
    this.state = state;
    this.error = error;
    for (const h of this.stateHandlers) h(state, error);
  }

  protected emitRtt(ms: number): void {
    for (const h of this.rttHandlers) h(ms);
  }

  protected emitReset(): void {
    for (const h of this.resetHandlers) h();
  }
}
