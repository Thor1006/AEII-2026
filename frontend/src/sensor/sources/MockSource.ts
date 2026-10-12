import type { MockOptions } from '../mockData.ts';
import { MockGenerator } from '../mockData.ts';
import type { AckMessage, CommandName } from '../protocol.ts';
import { BaseSource } from '../SensorSource.ts';

/** In-browser synthetic data that behaves like a Pi (hello, status, session commands). No server needed. */
export class MockSource extends BaseSource {
  readonly kind = 'mock';
  readonly label = 'Demo data';
  private readonly opts: MockOptions;
  private timer: ReturnType<typeof setInterval> | undefined;
  private gen: MockGenerator | null = null;
  private commandId = 1;

  constructor(opts: MockOptions = {}) {
    super();
    this.opts = opts;
  }

  async connect(): Promise<void> {
    const gen = (this.gen = new MockGenerator(this.opts));
    this.setState('open');
    this.emit(gen.hello(), 2000);
    this.timer = setInterval(() => {
      for (const msg of gen.next(Date.now())) {
        this.emit(msg, msg.type === 'frame' ? msg.data.byteLength : 200);
      }
    }, 1000 / gen.fps);
  }

  disconnect(): void {
    clearInterval(this.timer);
    this.gen = null;
    this.setState('closed');
  }

  async command(name: CommandName, args?: Record<string, unknown>): Promise<AckMessage> {
    if (!this.gen) return { type: 'ack', id: 0, ok: false, error: 'Not connected' };
    const ack = this.gen.handleCommand(this.commandId++, name, args);
    // Push the new session state right away, like the real bridge does.
    if (ack.ok) for (const msg of this.gen.drain()) this.emit(msg, 200);
    return ack;
  }
}
