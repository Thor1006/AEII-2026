/**
 * End-to-end check of the kit key handshake and signed commands.
 * Starts the mock server with a key, then talks to it like a browser would
 * (using the same src/lib/hmac.ts) and checks every way in must be refused.
 *   node scripts/check-auth.ts
 */
import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { WebSocket } from 'ws';
import { fromHex, hmacHex, hmacSha256, toHex, utf8 } from '../src/lib/hmac.ts';

const PORT = 18765;
const KEY = randomBytes(32).toString('hex');
const OTHER_KEY = randomBytes(32).toString('hex');
const url = `ws://127.0.0.1:${PORT}`;

let failed = 0;
const check = (name: string, ok: boolean, extra = '') => {
  if (!ok) failed++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : `  ${extra}`}`);
};

type Msg = Record<string, any>;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** A tiny client: collects messages, lets a test wait for one. */
class Client {
  ws: WebSocket;
  msgs: Msg[] = [];
  binary = 0;
  closeCode: number | null = null;
  constructor() {
    this.ws = new WebSocket(url);
    this.ws.on('message', (d, isBinary) => (isBinary ? this.binary++ : this.msgs.push(JSON.parse(d.toString()))));
    this.ws.on('close', (c) => (this.closeCode = c));
  }
  async until(pred: (m: Msg) => boolean, ms = 3000): Promise<Msg | undefined> {
    const t0 = Date.now();
    while (Date.now() - t0 < ms) {
      const m = this.msgs.find(pred);
      if (m) return m;
      await sleep(20);
    }
  }
  send(m: Msg) {
    this.ws.send(JSON.stringify(m));
  }
  close() {
    this.ws.close();
  }
}

async function handshake(key: string, c: Client) {
  const ch = await c.until((m) => m.type === 'challenge');
  if (!ch) throw new Error('no challenge');
  const cnonce = toHex(randomBytes(16));
  const k = fromHex(key);
  c.send({ type: 'auth', cnonce, proof: hmacHex(k, 'trf-client', ch.nonce, cnonce, ch.kitId ?? '') });
  const ok = await c.until((m) => m.type === 'authok' || m.type === 'autherr');
  return { ch, cnonce, ok, k, sessionKey: hmacSha256(k, utf8(['trf-session', ch.nonce, cnonce].join('|'))) };
}

const signed = (sessionKey: Uint8Array, id: number, ctr: number, name: string, args: Msg = {}) => {
  const payload = JSON.stringify({ name, args });
  return { type: 'command', id, ctr, payload, mac: hmacHex(sessionKey, ctr, payload) };
};

const server = spawn('node', ['mock-server/server.ts'], { env: { ...process.env, PORT: String(PORT), KEY, FPS: '10' }, stdio: 'ignore' });
await sleep(1200);

try {
  // 1. Nothing is sent before the handshake.
  {
    const c = new Client();
    await c.until((m) => m.type === 'challenge');
    await sleep(600);
    check('first message is a challenge', c.msgs[0]?.type === 'challenge');
    check('no hello, status or frames before the handshake', c.msgs.length === 1 && c.binary === 0, `got ${c.msgs.map((m) => m.type)} + ${c.binary} frames`);
    c.close();
  }

  // 2. Right key: authok with a valid server proof, then hello with auth flag, then data.
  {
    const c = new Client();
    const { ch, cnonce, ok, k, sessionKey } = await handshake(KEY, c);
    check('right key is accepted', ok?.type === 'authok');
    check('server proves it knows the key', ok?.proof === hmacHex(k, 'trf-server', ch.nonce, cnonce, ch.kitId ?? ''));
    const hello = await c.until((m) => m.type === 'hello');
    check('hello says auth is hmac-sha256', hello?.auth === 'hmac-sha256');
    await sleep(500);
    check('data flows after the handshake', c.binary > 0);

    // 3. Signed commands.
    c.send(signed(sessionKey, 1, 1, 'session.start', { exercise: 'elbow_flexion' }));
    const a1 = await c.until((m) => m.type === 'ack' && m.id === 1);
    check('signed command is accepted', a1?.ok === true, JSON.stringify(a1));
    c.send(signed(sessionKey, 2, 1, 'marker', { label: 'again' }));
    const a2 = await c.until((m) => m.type === 'ack' && m.id === 2);
    check('replayed counter is refused', a2?.ok === false, JSON.stringify(a2));
    const tampered = signed(sessionKey, 3, 2, 'marker', { label: 'a' });
    tampered.payload = tampered.payload.replace('"a"', '"b"');
    c.send(tampered);
    const a3 = await c.until((m) => m.type === 'ack' && m.id === 3);
    check('edited payload is refused', a3?.ok === false, JSON.stringify(a3));
    c.send({ type: 'command', id: 4, name: 'session.stop', args: {} });
    const a4 = await c.until((m) => m.type === 'ack' && m.id === 4);
    check('unsigned command is refused', a4?.ok === false, JSON.stringify(a4));
    c.send({ ...signed(sessionKey, 5, 3, 'session.stop'), mac: '0'.repeat(64) });
    const a5 = await c.until((m) => m.type === 'ack' && m.id === 5);
    check('wrong signature is refused', a5?.ok === false, JSON.stringify(a5));
    c.send(signed(sessionKey, 6, 4, 'session.stop'));
    const a6 = await c.until((m) => m.type === 'ack' && m.id === 6);
    check('a later valid command still works', a6?.ok === true, JSON.stringify(a6));
    c.close();
  }

  // 4. A key from a different session can't sign for this one.
  {
    const a = new Client();
    const b = new Client();
    const ha = await handshake(KEY, a);
    await handshake(KEY, b);
    a.send(signed(ha.sessionKey, 7, 1, 'session.start'));
    const r = await a.until((m) => m.type === 'ack' && m.id === 7);
    check('each connection has its own session key', r?.ok === true);
    const other = signed(ha.sessionKey, 8, 1, 'session.stop'); // a's key used on b's connection
    b.send(other);
    const rb = await b.until((m) => m.type === 'ack' && m.id === 8);
    check('a command signed for another connection is refused', rb?.ok === false, JSON.stringify(rb));
    a.close();
    b.close();
  }

  // 5. Wrong key: refused, closed with 4401, no data.
  {
    const c = new Client();
    const { ok } = await handshake(OTHER_KEY, c);
    await sleep(300);
    check('wrong key is refused', ok?.type === 'autherr' && ok.error === 'wrong-key', JSON.stringify(ok));
    check('connection is closed with code 4401', c.closeCode === 4401, String(c.closeCode));
    check('no data leaked to a wrong key', c.binary === 0 && !c.msgs.some((m) => m.type === 'hello'));
  }

  // 6. Sending data requests without any auth gets nothing.
  {
    const c = new Client();
    await c.until((m) => m.type === 'challenge');
    c.send({ type: 'command', id: 1, name: 'session.start', args: {} });
    c.send({ type: 'ping', id: 1, clientT: 0 });
    await sleep(500);
    check('commands and pings before auth are ignored', !c.msgs.some((m) => m.type === 'ack' || m.type === 'pong') && c.binary === 0);
    c.close();
  }

  // 7. Five wrong keys lock the kit for a while, even for the right key.
  {
    for (let i = 0; i < 5; i++) {
      const c = new Client();
      await handshake(OTHER_KEY, c);
      c.close();
    }
    const c = new Client();
    const { ok } = await handshake(KEY, c);
    check('after repeated wrong keys the kit is locked', ok?.type === 'autherr' && ok.error === 'locked', JSON.stringify(ok));
    c.close();
  }
} finally {
  server.kill();
}

console.log(failed ? `\n${failed} check(s) FAILED` : '\nAll checks passed');
process.exit(failed ? 1 : 0);
