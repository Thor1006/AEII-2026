/**
 * Mock Raspberry Pi bridge: serves SYNTHETIC data over WebSocket using protocol 1.1
 * (hello + manifest, status heartbeat, session commands). For frontend work without Python.
 * The reference bridge is pi-bridge/ (Python); both must pass pi-bridge/check_bridge.py.
 *
 *   npm run mock                                   # ws://0.0.0.0:8765, 20 fps, float32 frames
 *   PORT=9000 FPS=10 DTYPE=u8 DROP=0.05 npm run mock
 *
 * DROP simulates lost messages (0–1) to check the drop counter.
 * BREAK deliberately violates the protocol, to prove the checker catches it:
 *   BREAK=nohello    never send hello
 *   BREAK=badframe   frame payload shorter than its header says
 *   BREAK=noscores   announce scores in the manifest but never send them
 *
 * KEY=<64 hex> protects the mock like a real kit: challenge/auth handshake before any data, signed commands.
 *   KEY=$(node -e "console.log(require('crypto').randomBytes(32).toString('hex'))") npm run mock
 * These BREAK modes only apply with KEY set, and each one must make the browser refuse the kit:
 *   BREAK=fakeserver  answers the handshake with a wrong server proof (an impostor kit)
 *   BREAK=skipauth    sends data without any handshake (an impostor that pretends to be open)
 * Node's own crypto is used here on purpose: it cross-checks src/lib/hmac.ts, which the browser runs.
 */
import { createHmac, randomBytes, timingSafeEqual } from 'node:crypto';
import { WebSocketServer } from 'ws';
import { encodeBinaryFrame } from '../src/sensor/codec.ts';
import { MockGenerator } from '../src/sensor/mockData.ts';
import type { FrameDType } from '../src/sensor/protocol.ts';

const PORT = Number(process.env.PORT ?? 8765);
const FPS = Number(process.env.FPS ?? 20);
const DTYPE = (process.env.DTYPE ?? 'f32') as FrameDType;
const DROP = Number(process.env.DROP ?? 0);
const BREAK = process.env.BREAK ?? '';
const KEY = process.env.KEY ? Buffer.from(process.env.KEY, 'hex') : null;
if (process.env.KEY && (!/^[0-9a-f]{64}$/i.test(process.env.KEY))) throw new Error('KEY must be 64 hex characters');
const PROTECTED = KEY !== null && BREAK !== 'skipauth';

const hmacHex = (key: Buffer, ...parts: (string | number)[]) => createHmac('sha256', key).update(parts.join('|')).digest('hex');
const sameHex = (a: string, b: string) => a.length === b.length && timingSafeEqual(Buffer.from(a), Buffer.from(b));

/** Per-connection handshake state. */
interface Auth {
  nonce: string;
  authed: boolean;
  sessionKey?: Buffer;
  lastCtr: number;
}
const auths = new WeakMap<object, Auth>();
const failures: number[] = [];
const isOk = (ws: { readyState: number; OPEN: number }) => ws.readyState === ws.OPEN;

const wss = new WebSocketServer({ port: PORT, host: '0.0.0.0' });
// One generator for all viewers, like a real kit: everyone sees the same session.
const gen = new MockGenerator({ fps: FPS, src: 'mock-server' });

const broadcast = (data: string | ArrayBuffer) => {
  for (const ws of wss.clients) {
    if (!isOk(ws)) continue;
    if (PROTECTED && !auths.get(ws)?.authed) continue; // no data before the handshake
    ws.send(data);
  }
};

setInterval(() => {
  if (!wss.clients.size) return;
  for (const msg of gen.next(Date.now())) {
    if (DROP > 0 && Math.random() < DROP) continue;
    if (BREAK === 'noscores' && msg.type === 'scores') continue;
    if (msg.type === 'frame') {
      const buf = encodeBinaryFrame(msg, DTYPE);
      broadcast(BREAK === 'badframe' ? buf.slice(0, buf.byteLength - 100) : buf);
    } else if (msg.type === 'status') {
      broadcast(JSON.stringify({ ...msg, clients: wss.clients.size }));
    } else {
      broadcast(JSON.stringify(msg));
    }
  }
}, 1000 / FPS);

wss.on('connection', (ws, req) => {
  console.log(`viewer connected: ${req.socket.remoteAddress} (${wss.clients.size} total)`);
  const hello = () => JSON.stringify({ ...gen.hello(), auth: PROTECTED ? 'hmac-sha256' : 'none' });
  if (PROTECTED) {
    const a: Auth = { nonce: randomBytes(16).toString('hex'), authed: false, lastCtr: 0 };
    auths.set(ws, a);
    ws.send(JSON.stringify({ type: 'challenge', nonce: a.nonce, kitId: gen.hello().device.kitId }));
  } else if (BREAK !== 'nohello') ws.send(hello());

  ws.on('message', (data, isBinary) => {
    if (isBinary) return;
    let msg: { type?: string; id?: number; clientT?: number; name?: string; args?: Record<string, unknown>; cnonce?: string; proof?: string; ctr?: number; payload?: string; mac?: string };
    try {
      msg = JSON.parse(data.toString());
    } catch {
      return;
    }
    const a = auths.get(ws);
    if (PROTECTED && a && !a.authed) {
      if (msg.type !== 'auth' || typeof msg.cnonce !== 'string' || typeof msg.proof !== 'string') return;
      const now = Date.now();
      while (failures.length && now - failures[0] > 60_000) failures.shift();
      if (failures.length >= 5) {
        ws.send(JSON.stringify({ type: 'autherr', error: 'locked' }));
        return ws.close(4401);
      }
      const kitId = gen.hello().device.kitId ?? '';
      if (!sameHex(msg.proof, hmacHex(KEY!, 'trf-client', a.nonce, msg.cnonce, kitId))) {
        failures.push(now);
        console.log('auth: wrong key');
        ws.send(JSON.stringify({ type: 'autherr', error: 'wrong-key' }));
        return ws.close(4401);
      }
      const serverProof = hmacHex(KEY!, 'trf-server', a.nonce, msg.cnonce, kitId);
      ws.send(JSON.stringify({ type: 'authok', proof: BREAK === 'fakeserver' ? serverProof.replace(/.$/, (c) => (c === '0' ? '1' : '0')) : serverProof }));
      a.authed = true;
      a.sessionKey = createHmac('sha256', KEY!).update(['trf-session', a.nonce, msg.cnonce].join('|')).digest();
      console.log('auth: ok');
      ws.send(hello());
      return;
    }
    if (msg.type === 'ping') {
      ws.send(JSON.stringify({ type: 'pong', id: msg.id, clientT: msg.clientT, t: Date.now() }));
    } else if (msg.type === 'command' && typeof msg.id === 'number') {
      let name = msg.name;
      let args = msg.args ?? {};
      if (PROTECTED && a?.sessionKey) {
        // Signed command: check the counter and the MAC over the exact text, then read the payload.
        const ok = typeof msg.ctr === 'number' && typeof msg.payload === 'string' && typeof msg.mac === 'string' && msg.ctr > a.lastCtr && sameHex(msg.mac, hmacHex(a.sessionKey, msg.ctr, msg.payload));
        if (!ok) {
          console.log('command refused: not signed correctly');
          ws.send(JSON.stringify({ type: 'ack', id: msg.id, ok: false, error: 'Command not signed correctly' }));
          return;
        }
        a.lastCtr = msg.ctr!;
        const p = JSON.parse(msg.payload!) as { name?: string; args?: Record<string, unknown> };
        name = p.name;
        args = p.args ?? {};
      }
      if (typeof name !== 'string') return;
      const ack = gen.handleCommand(msg.id, name, args);
      ws.send(JSON.stringify(ack));
      console.log(`command ${name} → ${ack.ok ? 'ok' : ack.error}`);
      // Everyone sees the new session state at once, in sequence order.
      if (ack.ok) for (const m of gen.drain()) broadcast(JSON.stringify(m.type === 'status' ? { ...m, clients: wss.clients.size } : m));
    }
  });

  ws.on('close', () => console.log(`viewer disconnected (${wss.clients.size} left)`));
});

console.log(`mock bridge (SYNTHETIC) on ws://0.0.0.0:${PORT}  fps=${FPS} dtype=${DTYPE} drop=${DROP}${KEY ? '  PROTECTED (key set)' : ''}${BREAK ? `  BREAK=${BREAK}` : ''}`);
