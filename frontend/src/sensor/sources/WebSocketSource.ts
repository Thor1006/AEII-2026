import { decodeBinaryFrame, parseJsonMessage } from '../codec.ts';
import type { AckMessage, CommandName } from '../protocol.ts';
import { BaseSource, CommandError } from '../SensorSource.ts';

export interface WebSocketSourceOptions {
  /** e.g. ws://raspberrypi.local:8765 */
  url: string;
  reconnect?: boolean;
  maxBackoffMs?: number;
  /** Send a ping this often to measure round-trip time. 0 disables. */
  pingIntervalMs?: number;
  /** How long to wait for a command ack. */
  commandTimeoutMs?: number;
}

/**
 * Live data from the Raspberry Pi bridge (or the mock server) over WebSocket.
 * Binary messages are TRF1 radar frames; text messages are JSON.
 * Reconnects with exponential backoff, so a Wi-Fi drop doesn't need a page reload.
 */
export class WebSocketSource extends BaseSource {
  readonly kind = 'websocket';
  readonly label: string;
  private readonly opts: Required<WebSocketSourceOptions>;
  private ws: WebSocket | null = null;
  private closedByUser = false;
  private backoff = 500;
  private retryTimer: ReturnType<typeof setTimeout> | undefined;
  private pingTimer: ReturnType<typeof setInterval> | undefined;
  private pingId = 0;
  private commandId = 1;
  private pendingAcks = new Map<number, { resolve: (a: AckMessage) => void; reject: (e: Error) => void; timer: ReturnType<typeof setTimeout> }>();
  /** Reconnect attempts since the last successful open. */
  attempts = 0;
  /** True once any connection succeeded. Used to tell "never reached" from "lost". */
  everOpened = false;

  constructor(opts: WebSocketSourceOptions) {
    super();
    this.opts = { reconnect: true, maxBackoffMs: 8000, pingIntervalMs: 2000, commandTimeoutMs: 5000, ...opts };
    this.label = `WebSocket ${opts.url}`;
  }

  async connect(): Promise<void> {
    this.closedByUser = false;
    this.open();
  }

  get url(): string {
    return this.opts.url;
  }

  command(name: CommandName, args?: Record<string, unknown>): Promise<AckMessage> {
    if (this.ws?.readyState !== WebSocket.OPEN) return Promise.reject(new CommandError('Not connected'));
    const id = this.commandId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingAcks.delete(id);
        reject(new CommandError(`No reply to "${name}" within ${this.opts.commandTimeoutMs / 1000} s`));
      }, this.opts.commandTimeoutMs);
      this.pendingAcks.set(id, { resolve, reject, timer });
      this.ws!.send(JSON.stringify({ type: 'command', id, name, args }));
    });
  }

  disconnect(): void {
    this.closedByUser = true;
    this.failPending('Disconnected');
    clearTimeout(this.retryTimer);
    clearInterval(this.pingTimer);
    this.ws?.close();
    this.ws = null;
    this.setState('closed');
  }

  private open(): void {
    this.setState(this.state === 'idle' || this.state === 'closed' ? 'connecting' : 'reconnecting');
    let ws: WebSocket;
    try {
      ws = new WebSocket(this.opts.url);
    } catch (err) {
      this.setState('error', err instanceof Error ? err.message : String(err));
      return;
    }
    ws.binaryType = 'arraybuffer';
    this.ws = ws;

    this.error = undefined;
    ws.onopen = () => {
      this.backoff = 500;
      this.attempts = 0;
      this.everOpened = true;
      this.setState('open');
      if (this.opts.pingIntervalMs > 0) {
        clearInterval(this.pingTimer);
        this.pingTimer = setInterval(() => this.ping(), this.opts.pingIntervalMs);
      }
    };

    ws.onmessage = (ev: MessageEvent<string | ArrayBuffer>) => {
      try {
        if (typeof ev.data === 'string') {
          const msg = parseJsonMessage(ev.data);
          if (!msg) return;
          if (msg.type === 'pong') this.emitRtt(performance.now() - msg.clientT);
          else if (msg.type === 'ack') this.settleAck(msg);
          else this.emit(msg, ev.data.length);
        } else {
          this.emit(decodeBinaryFrame(ev.data), ev.data.byteLength);
        }
      } catch (err) {
        console.warn('[WebSocketSource] bad message', err);
      }
    };

    ws.onclose = () => {
      clearInterval(this.pingTimer);
      if (this.closedByUser || ws !== this.ws) return;
      this.failPending('Connection lost');
      this.attempts++;
      if (!this.opts.reconnect) {
        this.setState('closed');
        return;
      }
      const reason = this.error ?? 'Connection lost';
      this.setState('reconnecting', `${reason}. Retrying in ${(this.backoff / 1000).toFixed(1)} s`);
      this.retryTimer = setTimeout(() => this.open(), this.backoff);
      this.backoff = Math.min(this.opts.maxBackoffMs, this.backoff * 2);
    };

    // onclose always follows onerror; just record the reason.
    ws.onerror = () => {
      this.error = `Cannot reach ${this.opts.url}`;
    };
  }

  private settleAck(ack: AckMessage): void {
    const p = this.pendingAcks.get(ack.id);
    if (!p) return;
    clearTimeout(p.timer);
    this.pendingAcks.delete(ack.id);
    p.resolve(ack);
  }

  private failPending(reason: string): void {
    for (const p of this.pendingAcks.values()) {
      clearTimeout(p.timer);
      p.reject(new CommandError(reason));
    }
    this.pendingAcks.clear();
  }

  private ping(): void {
    if (this.ws?.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({ type: 'ping', id: this.pingId++, clientT: performance.now() }));
  }
}
