import type { TelemetryFrame, TelemetrySource } from './types';

export class BackendTelemetrySource implements TelemetrySource {
  readonly kind = 'backend';
  private frame: TelemetryFrame;
  private listeners = new Set<(frame: TelemetryFrame) => void>();
  private socket: WebSocket | null = null;
  private reconnectTimer: number | undefined;
  private disposed = false;

  constructor(initial: TelemetryFrame) { this.frame = initial; }
  get initial(): TelemetryFrame { return this.frame; }

  subscribe(listener: (frame: TelemetryFrame) => void): () => void {
    this.listeners.add(listener);
    listener(this.frame);
    if (!this.socket) this.connect();
    return () => this.listeners.delete(listener);
  }

  private notify(frame: TelemetryFrame): void {
    this.frame = frame;
    this.listeners.forEach(listener => listener(frame));
  }

  private connect(): void {
    const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.socket = new WebSocket(`${scheme}//${location.host}/ws/telemetry`);
    this.socket.onmessage = event => {
      try { this.notify(JSON.parse(event.data) as TelemetryFrame); } catch { /* keep latest valid frame */ }
    };
    this.socket.onclose = () => {
      this.socket = null;
      if (!this.disposed) this.reconnectTimer = window.setTimeout(() => this.connect(), 1200);
    };
  }

  private async command(action: 'start' | 'stop' | 'reset'): Promise<void> {
    const response = await fetch(`/api/session/${action}`, { method: 'POST' });
    if (!response.ok) throw new Error(`Session ${action} failed (${response.status})`);
    this.notify(await response.json() as TelemetryFrame);
  }

  start(): Promise<void> { return this.command('start'); }
  stop(): Promise<void> { return this.command('stop'); }
  reset(): Promise<void> { return this.command('reset'); }

  async exportCsv(): Promise<void> {
    const response = await fetch('/api/session/export.csv');
    if (!response.ok) throw new Error(`Export failed (${response.status})`);
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = `${this.frame.session_id}.csv`;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async saveSession(): Promise<string> {
    const response = await fetch('/api/session/save', { method: 'POST' });
    if (!response.ok) throw new Error(`Save failed (${response.status})`);
    const result = await response.json() as { path: string };
    return `Saved to ${result.path}`;
  }

  dispose(): void {
    this.disposed = true;
    this.socket?.close();
    if (this.reconnectTimer !== undefined) window.clearTimeout(this.reconnectTimer);
    this.listeners.clear();
  }
}
