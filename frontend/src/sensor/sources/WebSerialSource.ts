import { isControlMessage, normalizeMessage } from '../codec.ts';
import type { SensorMessage } from '../protocol.ts';
import { PROTOCOL_VERSION } from '../protocol.ts';
import { BaseSource } from '../SensorSource.ts';

export interface WebSerialSourceOptions {
  baudRate: number;
  /** Channel names for plain CSV lines like "512,20.3". */
  columns?: string[];
}

export const isWebSerialSupported = () => typeof navigator !== 'undefined' && !!navigator.serial;

/**
 * Arduino (sEMG / force / IMU) plugged into THIS computer over USB. Chrome and Edge only.
 * If the Arduino is plugged into the Pi instead, the Pi forwards it as `aux` over WebSocket.
 *
 * Accepted line formats (one sample per line):
 *   {"type":"aux","channels":{"emg":512}}   full protocol message
 *   {"emg":512,"force":20.3}                bare object → aux
 *   emg:512,force:20.3                      key:value pairs → aux
 *   512,20.3                                plain CSV → aux, named by `columns`
 */
export class WebSerialSource extends BaseSource {
  readonly kind = 'serial';
  readonly label = 'USB serial';
  private readonly opts: WebSerialSourceOptions;
  private port: SerialPort | null = null;
  private reader: ReadableStreamDefaultReader<Uint8Array> | null = null;
  private seq = 0;

  constructor(opts: WebSerialSourceOptions) {
    super();
    this.opts = opts;
  }

  async connect(): Promise<void> {
    if (!navigator.serial) {
      this.setState('error', 'Web Serial needs Chrome or Edge');
      return;
    }
    this.setState('connecting');
    try {
      // Must be the first await: requestPort needs the click's user gesture.
      this.port = await navigator.serial.requestPort();
      await this.port.open({ baudRate: this.opts.baudRate });
    } catch (err) {
      this.setState('error', err instanceof Error ? err.message : String(err));
      return;
    }
    this.setState('open');
    void this.readLoop();
  }

  disconnect(): void {
    const { reader, port } = this;
    this.reader = null;
    this.port = null;
    void (async () => {
      try {
        await reader?.cancel();
        reader?.releaseLock();
        await port?.close();
      } catch {
        /* already closed */
      }
    })();
    this.setState('closed');
  }

  private async readLoop(): Promise<void> {
    if (!this.port?.readable) return;
    const decoder = new TextDecoder();
    this.reader = this.port.readable.getReader();
    let buffer = '';
    try {
      for (;;) {
        const { value, done } = await this.reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let nl: number;
        while ((nl = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, nl).trim();
          buffer = buffer.slice(nl + 1);
          if (!line) continue;
          const msg = parseSerialLine(line, this.opts.columns, this.seq);
          if (msg) {
            this.seq++;
            this.emit(msg, line.length + 1);
          }
        }
      }
    } catch (err) {
      if (this.reader) this.setState('error', err instanceof Error ? err.message : String(err));
    }
  }
}

/** Exported so other line-based inputs can reuse it. */
export function parseSerialLine(line: string, columns: string[] = [], seq = 0): SensorMessage | null {
  const env = { v: PROTOCOL_VERSION, seq, t: Date.now(), src: 'serial' };

  if (line.startsWith('{')) {
    try {
      const obj = JSON.parse(line) as Record<string, unknown>;
      if (typeof obj.type === 'string') {
        const msg = normalizeMessage({ ...env, ...obj });
        return msg && !isControlMessage(msg) ? msg : null;
      }
      return { ...env, type: 'aux', channels: numericOnly(obj) };
    } catch {
      return null;
    }
  }

  const parts = line.split(/[,\t;]/).map((s) => s.trim());
  const channels: Record<string, number> = {};
  parts.forEach((part, i) => {
    const [k, v] = part.includes(':') ? part.split(':') : [columns[i] ?? `ch${i}`, part];
    const num = Number(v);
    if (k && Number.isFinite(num)) channels[k.trim()] = num;
  });
  return Object.keys(channels).length ? { ...env, type: 'aux', channels } : null;
}

function numericOnly(obj: Record<string, unknown>): Record<string, number> {
  const out: Record<string, number> = {};
  for (const [k, v] of Object.entries(obj)) if (typeof v === 'number') out[k] = v;
  return out;
}
