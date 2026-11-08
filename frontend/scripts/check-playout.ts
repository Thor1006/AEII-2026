/**
 * Checks src/state/PlayoutClock.ts, the clock of the live charts: they run slightly behind the Pi's clock and keep
 * moving through a Wi-Fi pause instead of freezing.
 *   node scripts/check-playout.ts
 */
import { PlayoutClock } from '../src/state/PlayoutClock.ts';

let failed = 0;
const check = (name: string, ok: boolean, detail = '') => {
  if (!ok) failed++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok || !detail ? '' : `\n  ${detail}`}`);
};

const PI0 = 1_800_000_000_000;      // the Pi's clock (ms)
const AHEAD = 3_600_000;            // the browser's clock runs an hour ahead (no time sync at a venue)
const NET = 12;                     // network delay, ms

/** Envelope samples every 40 ms (25/s), sent in 20-ms packets; `held` = [start, end) of a pause, Pi time. */
function run(clock: PlayoutClock, fromMs: number, toMs: number, held?: [number, number]) {
  const ends: { host: number; tEnd: number | null }[] = [];
  for (let pi = fromMs; pi < toMs; pi += 20) {
    const inPause = held && pi >= held[0] && pi < held[1];
    const arrive = (held && pi >= held[0] && pi < held[1] ? held[1] : pi) + NET + AHEAD;
    if (!inPause || pi + 20 >= held![1]) {
      // the samples made since the last packet (all of them at once after a pause)
      const start = inPause ? held![0] : pi;
      for (let t = Math.ceil(start / 40) * 40; t <= pi; t += 40) clock.observe(arrive, PI0 + t, true);
    }
    ends.push({ host: pi + AHEAD + NET, tEnd: clock.tEnd(pi + AHEAD + NET) });
  }
  return ends;
}

// 1. Off (a replay): no clock
{
  const c = new PlayoutClock();
  c.observe(PI0 + AHEAD, PI0, true);
  check('off: tEnd is null', c.tEnd(PI0 + AHEAD) === null);
}

// 2. Clean link: 0.25 s behind the Pi, whatever the browser's clock says
{
  const c = new PlayoutClock();
  c.enabled = true;
  const ends = run(c, 0, 20_000);
  const last = ends[ends.length - 1];
  const behind = PI0 + 20_000 - last.tEnd!;
  check('clean link: 0.25-0.30 s behind the Pi', behind >= 240 && behind <= 300, `behind ${behind.toFixed(0)} ms`);
  check('clean link: delay 250 ms', Math.abs(c.delayMs - 250) < 1, `delay ${c.delayMs}`);
}

// 3. A 1.1-s pause: the edge keeps moving (no freeze), then the delay grows smoothly to cover the next pause
{
  const c = new PlayoutClock();
  c.enabled = true;
  const ends = run(c, 0, 40_000, [20_000, 21_100]);
  const during = ends.filter((e) => e.host >= 20_000 + AHEAD && e.host <= 21_100 + AHEAD);
  const steps = during.slice(1).map((e, i) => e.tEnd! - during[i].tEnd!);
  check('pause: the edge keeps moving at ~real speed', steps.every((s) => s > 13 && s < 27), `steps ${Math.min(...steps)}-${Math.max(...steps)} ms`);
  const all = ends.slice(1).map((e, i) => e.tEnd! - ends[i].tEnd!);
  check('never jumps back or ahead (speed 0.7-1.3x)', all.every((s) => s >= 0.7 * 20 - 0.01 && s <= 1.3 * 20 + 0.01),
    `steps ${Math.min(...all).toFixed(1)}-${Math.max(...all).toFixed(1)} ms`);
  check('after the pause the delay aims at ~1.25 s', Math.abs(c.targetMs(40_000 + AHEAD) - 1250) < 60, `target ${c.targetMs(40_000 + AHEAD)}`);
  check('and gets there within ~5 s', Math.abs(c.delayMs - c.targetMs(40_000 + AHEAD)) < 5, `delay ${c.delayMs.toFixed(0)}`);
  const later = run(c, 40_000, 110_000);
  check('a minute without pauses: back to 0.25 s', Math.abs(c.delayMs - 250) < 1, `delay ${c.delayMs.toFixed(0)}`);
  check('(and still moving)', later[later.length - 1].tEnd! > later[0].tEnd!);
}

// 4. A late intermittent channel (the median frequency, stamped at its window's centre) doesn't add delay
{
  const c = new PlayoutClock();
  c.enabled = true;
  run(c, 0, 10_000);
  for (let t = 0; t < 10_000; t += 250) c.observe(t + 260 + NET + AHEAD, PI0 + t, false);
  check('intermittent lateness ignored', Math.abs(c.targetMs(10_000 + AHEAD) - 250) < 1, `target ${c.targetMs(10_000 + AHEAD)}`);
}

// 5. Never more than 1.5 s behind
{
  const c = new PlayoutClock();
  c.enabled = true;
  run(c, 0, 30_000, [10_000, 13_000]);
  check('a 3-s pause: delay capped at 1.5 s', c.targetMs(30_000 + AHEAD) === 1500, `target ${c.targetMs(30_000 + AHEAD)}`);
}

console.log(failed ? `\n${failed} FAILED` : '\nall passed');
process.exit(failed ? 1 : 0);
