/**
 * Checks src/lib/hmac.ts against the RFC 4231 test vectors and against Node's own crypto.
 *   node scripts/check-hmac.ts
 */
import { createHmac, createHash, randomBytes } from 'node:crypto';
import { fromHex, hmacHex, hmacSha256, sha256, toHex, utf8 } from '../src/lib/hmac.ts';

let failed = 0;
const check = (name: string, got: string, want: string) => {
  const ok = got === want;
  if (!ok) failed++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : `\n  got  ${got}\n  want ${want}`}`);
};

// SHA-256 known answers
check('sha256("")', toHex(sha256(new Uint8Array())), 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855');
check('sha256("abc")', toHex(sha256(utf8('abc'))), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');

// RFC 4231
const vectors: [string, Uint8Array, Uint8Array, string][] = [
  ['RFC 4231 case 1', fromHex('0b'.repeat(20)), utf8('Hi There'), 'b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7'],
  ['RFC 4231 case 2', utf8('Jefe'), utf8('what do ya want for nothing?'), '5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843'],
  ['RFC 4231 case 3', fromHex('aa'.repeat(20)), fromHex('dd'.repeat(50)), '773ea91e36800e46854db8ebd09181a72959098b3ef8c122d9635514ced565fe'],
  ['RFC 4231 case 6 (key longer than a block)', fromHex('aa'.repeat(131)), utf8('Test Using Larger Than Block-Size Key - Hash Key First'), '60e431591ee0b67f0d8a26aacbf5b77f8e0bc6213728c5140546040f0ee37f54'],
];
for (const [name, key, msg, want] of vectors) check(name, toHex(hmacSha256(key, msg)), want);

// Random inputs of awkward lengths against Node's implementation
for (const len of [0, 1, 55, 56, 57, 63, 64, 65, 119, 120, 1000, 5000]) {
  const msg = randomBytes(len);
  const key = randomBytes(1 + (len % 90));
  check(`sha256 vs node, ${len} bytes`, toHex(sha256(msg)), createHash('sha256').update(msg).digest('hex'));
  check(`hmac vs node, ${len} bytes`, toHex(hmacSha256(key, msg)), createHmac('sha256', key).update(msg).digest('hex'));
}

// Protocol vectors from Node's crypto: pi-bridge/tests/test_auth.py checks the Python side against the same numbers.
{
  const key = Uint8Array.from({ length: 32 }, (_, i) => i);
  const nonce = 'aa'.repeat(16);
  const cnonce = 'bb'.repeat(16);
  check('client proof', hmacHex(key, 'trf-client', nonce, cnonce, 'KIT-01'), 'd812712172cffd3cea59f19e23fd739c26ee34f8cab9d71f41cca09bbfd39888');
  check('server proof', hmacHex(key, 'trf-server', nonce, cnonce, 'KIT-01'), 'a7abde7e8cbcd0666486c15a5f565a0e48104b28c18a4338b748dedcfdbd5e1d');
  const sessionKey = hmacSha256(key, utf8(['trf-session', nonce, cnonce].join('|')));
  check('session key', toHex(sessionKey), 'd847b4a94ef32663f751f2326d377edc98f66e05c8d5189776a7cca0e3a3201a');
  check('command mac', hmacHex(sessionKey, 1, '{"name":"marker","args":{"label":"hi"}}'), '553023090ff90a7497d4f37817c6ee70bf323b45d1410a03500c85e09dfbfdd8');
}

console.log(failed ? `\n${failed} check(s) FAILED` : '\nAll checks passed');
process.exit(failed ? 1 : 0);
