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
 */
import { WebSocketServer } from 'ws';
import { encodeBinaryFrame } from '../src/sensor/codec.ts';
import { MockGenerator } from '../src/sensor/mockData.ts';
import type { FrameDType } from '../src/sensor/protocol.ts';

const PORT = Number(process.env.PORT ?? 8765);
const FPS = Number(process.env.FPS ?? 20);
const DTYPE = (process.env.DTYPE ?? 'f32') as FrameDType;
const DROP = Number(process.env.DROP ?? 0);
const BREAK = process.env.BREAK ?? '';

const wss = new WebSocketServer({ port: PORT, host: '0.0.0.0' });
// One generator for all viewers, like a real kit: everyone sees the same session.
const gen = new MockGenerator({ fps: FPS, src: 'mock-server' });

const broadcast = (data: string | ArrayBuffer) => {
  for (const ws of wss.clients) if (ws.readyState === ws.OPEN) ws.send(data);
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
  if (BREAK !== 'nohello') ws.send(JSON.stringify(gen.hello()));

  ws.on('message', (data, isBinary) => {
    if (isBinary) return;
    let msg: { type?: string; id?: number; clientT?: number; name?: string; args?: Record<string, unknown> };
    try {
      msg = JSON.parse(data.toString());
    } catch {
      return;
    }
    if (msg.type === 'ping') {
      ws.send(JSON.stringify({ type: 'pong', id: msg.id, clientT: msg.clientT, t: Date.now() }));
    } else if (msg.type === 'command' && typeof msg.id === 'number' && typeof msg.name === 'string') {
      const ack = gen.handleCommand(msg.id, msg.name, msg.args ?? {});
      ws.send(JSON.stringify(ack));
      console.log(`command ${msg.name} → ${ack.ok ? 'ok' : ack.error}`);
      // Everyone sees the new session state at once, in sequence order.
      if (ack.ok) for (const m of gen.drain()) broadcast(JSON.stringify(m.type === 'status' ? { ...m, clients: wss.clients.size } : m));
    }
  });

  ws.on('close', () => console.log(`viewer disconnected (${wss.clients.size} left)`));
});

console.log(`mock bridge (SYNTHETIC) on ws://0.0.0.0:${PORT}  fps=${FPS} dtype=${DTYPE} drop=${DROP}${BREAK ? `  BREAK=${BREAK}` : ''}`);
