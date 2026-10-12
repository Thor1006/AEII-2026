import { BackendTelemetrySource } from './backendSource';
import { BrowserDemoSource } from './browserSource';
import type { TelemetryFrame, TelemetrySource } from './types';

/** Prefer the Python WebSocket stream locally; static Sites remain fully interactive. */
export async function createTelemetrySource(): Promise<TelemetrySource> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 800);
  try {
    const response = await fetch('/api/health', { signal: controller.signal, cache: 'no-store' });
    if (!response.ok) throw new Error('No backend');
    const health = await response.json() as { status?: string };
    if (health.status !== 'ok') throw new Error('No backend');
    const initialResponse = await fetch('/api/state', { signal: controller.signal, cache: 'no-store' });
    if (!initialResponse.ok) throw new Error('No telemetry');
    return new BackendTelemetrySource(await initialResponse.json() as TelemetryFrame);
  } catch {
    return new BrowserDemoSource();
  } finally {
    window.clearTimeout(timer);
  }
}
