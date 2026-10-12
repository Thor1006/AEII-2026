/**
 * Kit keys live in this browser only, one per kit address (host name, not port).
 * A sticker link looks like  http://kit.local:8080/#/app?key=<64 hex>.
 * The part after # is never sent to a server; takeKeyFromLocation() saves it and removes it from the address bar.
 */
const STORE = 'trf-kit-keys';
const KEY_RE = /^[0-9a-f]{64}$/;

type KeyMap = Record<string, string>;

function read(): KeyMap {
  try {
    return JSON.parse(localStorage.getItem(STORE) ?? '{}') as KeyMap;
  } catch {
    return {};
  }
}

function write(map: KeyMap): void {
  try {
    localStorage.setItem(STORE, JSON.stringify(map));
  } catch {
    /* private mode: the key then lasts until the page closes only */
  }
}

/** Lower-case, drop spaces and dashes, check it looks like a key. Returns null if not. */
export function cleanKey(input: string): string | null {
  const k = input.replace(/[\s-]/g, '').toLowerCase();
  return KEY_RE.test(k) ? k : null;
}

const hostOf = (urlOrHost: string): string => {
  try {
    return new URL(/^[a-z]+:\/\//i.test(urlOrHost) ? urlOrHost : `ws://${urlOrHost}`).hostname;
  } catch {
    return urlOrHost;
  }
};

export function getKey(urlOrHost: string): string | undefined {
  return read()[hostOf(urlOrHost)];
}

export function saveKey(urlOrHost: string, key: string): void {
  write({ ...read(), [hostOf(urlOrHost)]: key });
}

export function forgetKey(urlOrHost: string): void {
  const map = read();
  delete map[hostOf(urlOrHost)];
  write(map);
}

/** If the page was opened from a sticker link, save its key for this host and clean the address bar. */
export function takeKeyFromLocation(): void {
  const m = /[?&]key=([^&]*)/.exec(location.hash);
  if (!m) return;
  const key = cleanKey(decodeURIComponent(m[1]));
  const route = location.hash.split('?')[0] || '#/app';
  history.replaceState(null, '', `${location.pathname}${location.search}${route}`);
  if (key) saveKey(location.hostname, key);
}
