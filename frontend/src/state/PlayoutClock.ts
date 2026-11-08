/**
 * The clock of the live charts. They run on the Pi's clock, a little behind it, so a short Wi-Fi pause no longer
 * freezes them: data that was held back arrives late but still lands before the charts reach it. A pause longer than
 * the delay shows as a gap at the right edge that fills in when the data arrives; the chart keeps moving either way.
 *
 * The Pi stamps every message with its own clock (ms). The browser's clock may differ (a kit with no internet has no
 * time sync), so "Pi time now" = host time − the smallest (arrival − stamp) of the last 10 s.
 * The delay follows how late the regular samples arrived over the last minute: 0.25 s on a clean link, at most 1.5 s.
 * It changes gradually (the chart runs 0.7–1.3× fast while it adjusts), never by a jump.
 */

const MIN_DELAY_MS = 250;
const MAX_DELAY_MS = 1500;
/** Added to the worst lateness of the last minute. */
const MARGIN_MS = 150;
/** The delay may change by at most this many ms per ms. */
const SLEW = 0.3;
const SKEW_WINDOW_S = 10;
const LATE_WINDOW_S = 60;

/** The smallest (or largest) value seen in each of the last n seconds. */
class SecondBuckets {
  private readonly n: number;
  private readonly pick: (a: number, b: number) => number;
  private readonly secs: number[];
  private readonly vals: number[];

  constructor(n: number, pick: (a: number, b: number) => number) {
    this.n = n;
    this.pick = pick;
    this.secs = new Array<number>(n).fill(-Infinity);
    this.vals = new Array<number>(n).fill(0);
  }

  add(nowMs: number, v: number): void {
    const sec = Math.floor(nowMs / 1000);
    const i = ((sec % this.n) + this.n) % this.n;
    if (this.secs[i] !== sec) {
      this.secs[i] = sec;
      this.vals[i] = v;
    } else {
      this.vals[i] = this.pick(this.vals[i], v);
    }
  }

  value(nowMs: number): number | null {
    const sec = Math.floor(nowMs / 1000);
    let out: number | null = null;
    for (let i = 0; i < this.n; i++) {
      const age = sec - this.secs[i];
      if (age >= 0 && age < this.n) out = out === null ? this.vals[i] : this.pick(out, this.vals[i]);
    }
    return out;
  }

  clear(): void {
    this.secs.fill(-Infinity);
  }
}

export class PlayoutClock {
  /** On for a live source (Pi bridge, demo). Replays and serial sources keep "end at the newest sample". */
  enabled = false;
  private readonly skew = new SecondBuckets(SKEW_WINDOW_S, Math.min);
  private readonly late = new SecondBuckets(LATE_WINDOW_S, Math.max);
  private delay = MIN_DELAY_MS;
  private lastNow: number | null = null;

  /**
   * A message stamped `t` (Pi clock, ms) arrived at `recvT` (host clock, ms).
   * `regular`: a sample of a steadily sent channel (e.g. the sEMG envelope), whose lateness sets the delay.
   */
  observe(recvT: number, t: number, regular: boolean): void {
    if (!Number.isFinite(t) || !Number.isFinite(recvT)) return;
    const d = recvT - t;
    this.skew.add(recvT, d);
    if (regular) {
      const skew = this.skew.value(recvT);
      if (skew !== null) this.late.add(recvT, d - skew);
    }
  }

  /** The delay the charts are moving towards (ms). */
  targetMs(now = Date.now()): number {
    const late = this.late.value(now) ?? 0;
    return Math.min(MAX_DELAY_MS, Math.max(MIN_DELAY_MS, late + MARGIN_MS));
  }

  /** The current delay (ms). */
  get delayMs(): number {
    return this.delay;
  }

  /** The right edge of the live charts in Pi time (ms), or null when off or before the first message. */
  tEnd(now = Date.now()): number | null {
    if (!this.enabled) return null;
    const skew = this.skew.value(now);
    if (skew === null) return null;
    const target = this.targetMs(now);
    if (this.lastNow === null) {
      this.delay = target;
    } else {
      const dt = Math.max(0, Math.min(200, now - this.lastNow));
      this.delay += Math.max(-SLEW * dt, Math.min(SLEW * dt, target - this.delay));
    }
    this.lastNow = now;
    return now - skew - this.delay;
  }

  reset(): void {
    this.skew.clear();
    this.late.clear();
    this.delay = MIN_DELAY_MS;
    this.lastNow = null;
  }
}
