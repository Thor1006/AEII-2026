import { isControlMessage, parseJsonMessage } from '../codec.ts';
import type { SensorMessage } from '../protocol.ts';
import type { Playback } from '../SensorSource.ts';
import { BaseSource } from '../SensorSource.ts';

export interface ReplaySourceOptions {
  /** A .ndjson recording (one protocol message per line), e.g. from the Record button. */
  file: File;
  speed?: number;
  loop?: boolean;
}

/** Plays a recorded session back with its original timing. */
export class ReplaySource extends BaseSource implements Playback {
  readonly kind = 'replay';
  readonly label: string;
  playing = false;
  speed: number;
  private readonly loop: boolean;
  private readonly file: File;
  private messages: SensorMessage[] = [];
  private cursor = 0;
  private playhead = 0;
  private lastWall = 0;
  private timer: ReturnType<typeof setInterval> | undefined;

  constructor(opts: ReplaySourceOptions) {
    super();
    this.file = opts.file;
    this.speed = opts.speed ?? 1;
    this.loop = opts.loop ?? false;
    this.label = `Replay ${opts.file.name}`;
  }

  get progress(): number {
    if (this.messages.length < 2) return 0;
    const t0 = this.messages[0].t;
    const t1 = this.messages[this.messages.length - 1].t;
    return Math.min(1, (this.playhead - t0) / (t1 - t0 || 1));
  }

  async connect(): Promise<void> {
    this.setState('connecting');
    try {
      const text = await this.file.text();
      const msgs: SensorMessage[] = [];
      let skipped = 0;
      for (const line of text.split('\n')) {
        if (!line.trim()) continue;
        try {
          const msg = parseJsonMessage(line);
          if (msg && !isControlMessage(msg)) msgs.push(msg);
        } catch {
          skipped++;
        }
      }
      if (!msgs.length) throw new Error('No protocol messages found in file');
      if (skipped) console.warn(`[ReplaySource] skipped ${skipped} bad lines`);
      this.messages = msgs.sort((a, b) => a.t - b.t);
    } catch (err) {
      this.setState('error', err instanceof Error ? err.message : String(err));
      return;
    }
    this.restart();
    this.setState('open');
    this.play();
  }

  disconnect(): void {
    this.pause();
    this.setState('closed');
  }

  play(): void {
    if (this.playing || !this.messages.length) return;
    if (this.cursor >= this.messages.length) this.restart();
    this.playing = true;
    this.lastWall = performance.now();
    this.timer = setInterval(() => this.tick(), 16);
  }

  pause(): void {
    this.playing = false;
    clearInterval(this.timer);
  }

  setSpeed(speed: number): void {
    this.speed = speed;
  }

  restart(): void {
    this.cursor = 0;
    this.playhead = this.messages[0]?.t ?? 0;
    this.emitReset();
  }

  private tick(): void {
    const now = performance.now();
    this.playhead += (now - this.lastWall) * this.speed;
    this.lastWall = now;
    while (this.cursor < this.messages.length && this.messages[this.cursor].t <= this.playhead) {
      this.emit(this.messages[this.cursor++]);
    }
    if (this.cursor >= this.messages.length) {
      if (this.loop) this.restart();
      else this.pause();
    }
  }
}
