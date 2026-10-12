/** Turning what people type ("trh-kit-01.local") into a WebSocket URL, and remembering it. */

export const DEFAULT_WS_PORT = 8765;

/**
 * Accepts: "trh-kit-01.local", "192.168.1.20", "192.168.1.20:9000",
 * "http://trh-kit-01.local:8080" (port replaced), "ws://host:8765".
 */
export function normalizePiAddress(input: string, port = DEFAULT_WS_PORT): string | null {
  let s = input.trim();
  if (!s) return null;
  if (/^wss?:\/\//i.test(s)) return s.replace(/\/+$/, '');
  const fromHttp = /^https?:\/\//i.test(s);
  s = s.replace(/^https?:\/\//i, '').replace(/\/.*$/, '');
  if (!/^[\w.-]+(:\d+)?$|^\[[0-9a-f:]+\](:\d+)?$/i.test(s)) return null;
  const hasPort = /:\d+$/.test(s) && !s.endsWith(']');
  const host = fromHttp && hasPort ? s.replace(/:\d+$/, '') : s;
  return `ws://${fromHttp || !hasPort ? `${host}:${port}` : host}`;
}

/** "ws://trh-kit-01.local:8765" → "trh-kit-01.local" */
export function displayAddress(url: string): string {
  return url.replace(/^wss?:\/\//, '').replace(new RegExp(`:${DEFAULT_WS_PORT}$`), '');
}

const RECENT_KEY = 'trf-recent-pis';

export function recentAddresses(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(RECENT_KEY) ?? '[]');
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string').slice(0, 5) : [];
  } catch {
    return [];
  }
}

export function rememberAddress(url: string): void {
  try {
    const list = [url, ...recentAddresses().filter((u) => u !== url)].slice(0, 5);
    localStorage.setItem(RECENT_KEY, JSON.stringify(list));
  } catch {
    /* private mode: nothing to remember */
  }
}

export function forgetAddress(url: string): void {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(recentAddresses().filter((u) => u !== url)));
  } catch {
    /* ignore */
  }
}

/** What the Pi bridge publishes at /truerehab-bridge.json when it serves this page. */
export interface BridgeInfo {
  ws: string;
  name?: string;
  kitId?: string;
}

/**
 * Where to connect automatically, in priority order:
 * 1. `?pi=<address>` in the page URL (e.g. from a QR code)
 * 2. the Pi bridge that served this page (it publishes /truerehab-bridge.json)
 */
export async function detectAutoConnect(): Promise<{ url: string; reason: string } | null> {
  const param = new URLSearchParams(location.search).get('pi');
  if (param) {
    const url = normalizePiAddress(param);
    if (url) return { url, reason: 'from the link' };
  }
  try {
    const res = await fetch('./truerehab-bridge.json', { cache: 'no-store' });
    if (!res.ok) return null;
    const info = (await res.json()) as BridgeInfo;
    if (typeof info.ws !== 'string') return null;
    // The bridge may say "ws://0.0.0.0:8765"; the browser must use the host it loaded the page from.
    const port = /:(\d+)/.exec(info.ws.replace(/^wss?:\/\//, ''))?.[1] ?? String(DEFAULT_WS_PORT);
    return { url: `ws://${location.hostname}:${port}`, reason: `served by ${info.name ?? 'the Pi'}` };
  } catch {
    return null; // dev server returns HTML or 404: not served by a bridge
  }
}
