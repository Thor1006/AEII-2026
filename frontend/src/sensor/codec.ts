/**
 * Encode / decode protocol messages.
 *
 * Text messages are JSON. Radar frames should go as binary WebSocket messages:
 *
 *   offset  size  content
 *   0       4     magic "TRF1"
 *   4       4     uint32 LE: header length N (bytes)
 *   8       N     UTF-8 JSON header: frame fields without `data`, plus
 *                 `dtype` ("f32" | "u8" | "u16") and, for integers, `scale: [min, max]`
 *   8+N     0–3   zero padding up to a multiple of 4
 *   ...           rows*cols values, little-endian, row-major
 *
 * Shared with the Node mock server: keep it DOM-free.
 */
import type {
  ControlMessage,
  FrameDType,
  FrameMessage,
  ScoreValue,
  SensorMessage,
} from './protocol.ts';
import { PROTOCOL_VERSION } from './protocol.ts';

const MAGIC = 0x31465254; // bytes "T" "R" "F" "1" read as uint32 LE
const MESSAGE_TYPES = new Set(['frame', 'scores', 'event', 'aux', 'status', 'hello']);

export class ProtocolError extends Error {}

const align4 = (n: number) => (n + 3) & ~3;

// ---------- binary frames ----------

export function isBinaryFrame(buf: ArrayBuffer): boolean {
  return buf.byteLength >= 8 && new DataView(buf).getUint32(0, true) === MAGIC;
}

export function decodeBinaryFrame(buf: ArrayBuffer): FrameMessage {
  if (!isBinaryFrame(buf)) throw new ProtocolError('Not a TRF1 binary frame');
  const view = new DataView(buf);
  const headerLen = view.getUint32(4, true);
  const headerBytes = new Uint8Array(buf, 8, headerLen);
  const header = JSON.parse(new TextDecoder().decode(headerBytes)) as Record<string, unknown>;

  const shape = header.shape as [number, number] | undefined;
  if (!Array.isArray(shape) || shape.length !== 2) throw new ProtocolError('Frame header needs shape [rows, cols]');
  const count = shape[0] * shape[1];
  const dtype = (header.dtype as FrameDType | undefined) ?? 'f32';
  const offset = align4(8 + headerLen);

  let data: Float32Array;
  if (dtype === 'f32') {
    if (offset + count * 4 > buf.byteLength) throw new ProtocolError('Frame payload too short');
    data = new Float32Array(buf.slice(offset, offset + count * 4));
  } else {
    const bytes = dtype === 'u8' ? 1 : 2;
    if (offset + count * bytes > buf.byteLength) throw new ProtocolError('Frame payload too short');
    const [lo, hi] = (header.scale as [number, number] | undefined) ?? [0, 1];
    const maxRaw = dtype === 'u8' ? 255 : 65535;
    const k = (hi - lo) / maxRaw;
    data = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      const raw = dtype === 'u8' ? view.getUint8(offset + i) : view.getUint16(offset + i * 2, true);
      data[i] = lo + raw * k;
    }
  }

  delete header.dtype;
  delete header.scale;
  return { ...(header as Omit<FrameMessage, 'data'>), type: 'frame', data };
}

export function encodeBinaryFrame(msg: FrameMessage, dtype: FrameDType = 'f32'): ArrayBuffer {
  const { data, recvT: _recvT, ...rest } = msg;
  const header: Record<string, unknown> = { ...rest, dtype };
  let lo = 0;
  let hi = 1;
  if (dtype !== 'f32') {
    lo = Infinity;
    hi = -Infinity;
    for (const x of data) {
      if (x < lo) lo = x;
      if (x > hi) hi = x;
    }
    if (hi === lo) hi = lo + 1;
    header.scale = [lo, hi];
  }
  const headerBytes = new TextEncoder().encode(JSON.stringify(header));
  const offset = align4(8 + headerBytes.length);
  const bytesPer = dtype === 'f32' ? 4 : dtype === 'u16' ? 2 : 1;
  const buf = new ArrayBuffer(offset + data.length * bytesPer);
  const view = new DataView(buf);
  view.setUint32(0, MAGIC, true);
  view.setUint32(4, headerBytes.length, true);
  new Uint8Array(buf, 8, headerBytes.length).set(headerBytes);

  const maxRaw = dtype === 'u8' ? 255 : 65535;
  for (let i = 0; i < data.length; i++) {
    if (dtype === 'f32') view.setFloat32(offset + i * 4, data[i], true);
    else {
      const raw = Math.round(((data[i] - lo) / (hi - lo)) * maxRaw);
      if (dtype === 'u8') view.setUint8(offset + i, raw);
      else view.setUint16(offset + i * 2, raw, true);
    }
  }
  return buf;
}

// ---------- JSON ----------

/**
 * Parse one JSON text message. Accepts the shorthands senders find convenient:
 * - `scores: { fatigue: 0.4 }` (bare numbers)
 * - frame `data` as a number array, or a base64 string of little-endian float32 (`encoding: "base64-f32"`)
 * - missing `v` / `seq` / `t` are filled in.
 * Returns null for unknown message types (so newer senders don't break older UIs).
 */
export function parseJsonMessage(text: string): SensorMessage | ControlMessage | null {
  const raw = JSON.parse(text) as Record<string, unknown>;
  return normalizeMessage(raw);
}

export function normalizeMessage(raw: Record<string, unknown>): SensorMessage | ControlMessage | null {
  if (raw.type === 'pong' || raw.type === 'ack') return raw as unknown as ControlMessage;
  if (typeof raw.type !== 'string' || !MESSAGE_TYPES.has(raw.type)) return null;

  const msg = {
    ...raw,
    v: typeof raw.v === 'number' ? raw.v : PROTOCOL_VERSION,
    seq: typeof raw.seq === 'number' ? raw.seq : -1,
    t: typeof raw.t === 'number' ? raw.t : Date.now(),
  } as Record<string, unknown>;

  if (msg.type === 'scores') {
    const scores: Record<string, ScoreValue> = {};
    for (const [key, val] of Object.entries((msg.scores ?? {}) as Record<string, unknown>)) {
      if (typeof val === 'number') scores[key] = { value: val };
      else if (val && typeof val === 'object' && typeof (val as ScoreValue).value === 'number') {
        scores[key] = val as ScoreValue;
      }
    }
    msg.scores = scores;
  }

  if (msg.type === 'frame') {
    const data = msg.data;
    if (typeof data === 'string') msg.data = base64ToFloat32(data);
    else if (Array.isArray(data)) msg.data = Float32Array.from(data as number[]);
    else throw new ProtocolError('Frame data must be a number array or base64 float32');
    delete msg.encoding;
  }

  return msg as unknown as SensorMessage;
}

/** One line for a recorded session file (.ndjson). Frames are stored as base64 float32. */
export function toJsonLine(msg: SensorMessage): string {
  if (msg.type === 'frame') {
    return JSON.stringify({ ...msg, data: float32ToBase64(msg.data), encoding: 'base64-f32' });
  }
  return JSON.stringify(msg);
}

// ---------- base64 ----------

export function float32ToBase64(arr: Float32Array): string {
  const le = new Float32Array(arr); // copy so we own a tightly packed buffer
  const bytes = new Uint8Array(le.buffer);
  let bin = '';
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return btoa(bin);
}

export function base64ToFloat32(b64: string): Float32Array {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Float32Array(bytes.buffer, 0, Math.floor(bytes.length / 4));
}

export function isControlMessage(msg: SensorMessage | ControlMessage): msg is ControlMessage {
  return msg.type === 'ack' || msg.type === 'pong';
}
