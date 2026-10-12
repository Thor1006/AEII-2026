import { fromHex, hmacHex, hmacSha256, timingSafeEqual, toHex, utf8 } from '../../lib/hmac.ts';
import { decodeBinaryFrame, parseJsonMessage } from '../codec.ts';
import type { AckMessage, AuthErrMessage, AuthMode, ChallengeMessage, CommandName } from '../protocol.ts';
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
  /** The kit key (64 hex characters) from the sticker. Needed only for protected kits. */
  key?: string;
}

/** Why the key handshake failed. The start screen uses it to ask for the key again. */
export type AuthProblem = 'needs-key' | 'wrong-key' | 'wrong-kit' | 'no-key-on-kit' | 'locked';

const AUTH_MESSAGES: Record<AuthProblem, string> = {
  'needs-key': 'This kit is protected. Enter the key from its sticker.',
  'wrong-key': 'That key doesn’t match this kit. Check the sticker and try again.',
  'wrong-kit': 'This device couldn’t prove it has your key, so it may not be your kit. Check the address.',
  'no-key-on-kit': 'You have a key saved for this address, but the kit isn’t asking for one. It may not be your kit. Check the address.',
  locked: 'Too many wrong keys. This kit is locked for a few minutes.',
};

interface PendingAuth {
  key: Uint8Array;
  nonce: string;
  cnonce: string;
  kitId: string;
}

/**
 * Live data from the Raspberry Pi bridge (or the mock server) over WebSocket.
 * Binary messages are TRF1 radar frames; text messages are JSON.
 * Reconnects with exponential backoff, so a Wi-Fi drop doesn't need a page reload.
 */
export class WebSocketSource extends BaseSource {
  readonly kind = 'websocket';
  readonly label: string;
  private readonly opts: Required<Omit<WebSocketSourceOptions, 'key'>> & { key?: string };
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
  /** Set when the key handshake failed. Reconnecting won't help, so we stop and let the user fix the key. */
  authProblem?: AuthProblem;
  /** What the kit said about itself: 'hmac-sha256' (protected, handshake passed) or 'none' (open kit). */
  authMode?: AuthMode;
  private pendingAuth: PendingAuth | null = null;
  private sessionKey: Uint8Array | null = null;
  private ctr = 0;
  private authed = false;

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
    if (this.opts.key && !this.authed) return Promise.reject(new CommandError('Not connected'));
    const id = this.commandId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingAcks.delete(id);
        reject(new CommandError(`No reply to "${name}" within ${this.opts.commandTimeoutMs / 1000} s`));
      }, this.opts.commandTimeoutMs);
      this.pendingAcks.set(id, { resolve, reject, timer });
      if (this.sessionKey) {
        // Kit with a key: sign the exact text we send, with a counter so a copy can't be replayed.
        const ctr = ++this.ctr;
        const payload = JSON.stringify({ name, args });
        this.ws!.send(JSON.stringify({ type: 'command', id, ctr, payload, mac: hmacHex(this.sessionKey, ctr, payload) }));
      } else {
        this.ws!.send(JSON.stringify({ type: 'command', id, name, args }));
      }
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
    this.authProblem = undefined;
    this.pendingAuth = null;
    this.sessionKey = null;
    this.ctr = 0;
    this.authed = false;
    this.authMode = undefined;
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
          else if (msg.type === 'challenge') this.onChallenge(ws, msg);
          else if (msg.type === 'authok') this.onAuthOk(ws, msg.proof);
          else if (msg.type === 'autherr') this.failAuth(ws, (msg as AuthErrMessage).error === 'locked' ? 'locked' : 'wrong-key');
          else {
            // We hold a key for this address, so the kit must prove it knows it. A device that skips
            // the handshake and just starts sending data could be an impostor.
            if (this.opts.key && !this.authed) return this.failAuth(ws, 'no-key-on-kit');
            if (msg.type === 'hello') this.authMode = msg.auth ?? 'none';
            this.emit(msg, ev.data.length);
          }
        } else {
          if (this.opts.key && !this.authed) return this.failAuth(ws, 'no-key-on-kit');
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
      if (this.authProblem) {
        // Wrong or missing key: retrying only fills the kit's failure counter.
        this.setState('closed', AUTH_MESSAGES[this.authProblem]);
        return;
      }
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

  private onChallenge(ws: WebSocket, msg: ChallengeMessage): void {
    if (!this.opts.key) return this.failAuth(ws, 'needs-key');
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    const cnonce = toHex(bytes);
    const key = fromHex(this.opts.key);
    const kitId = msg.kitId ?? '';
    this.pendingAuth = { key, nonce: msg.nonce, cnonce, kitId };
    ws.send(JSON.stringify({ type: 'auth', cnonce, proof: hmacHex(key, 'trf-client', msg.nonce, cnonce, kitId) }));
  }

  private onAuthOk(ws: WebSocket, proof: string): void {
    const p = this.pendingAuth;
    if (!p) return this.failAuth(ws, 'wrong-kit');
    // The kit proves it knows the key too, so a fake Pi on the same Wi-Fi is caught here.
    if (!timingSafeEqual(proof, hmacHex(p.key, 'trf-server', p.nonce, p.cnonce, p.kitId))) return this.failAuth(ws, 'wrong-kit');
    this.sessionKey = hmacSha256(p.key, utf8(['trf-session', p.nonce, p.cnonce].join('|')));
    this.pendingAuth = null;
    this.authed = true;
    this.authMode = 'hmac-sha256';
  }

  private failAuth(ws: WebSocket, problem: AuthProblem): void {
    this.authProblem = problem;
    this.error = AUTH_MESSAGES[problem];
    ws.close();
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
