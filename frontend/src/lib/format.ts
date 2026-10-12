export const pct = (v: number) => `${Math.round(v * 100)}%`;

export function bytes(n: number): string {
  if (n < 1024) return `${n.toFixed(0)} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 ** 2).toFixed(1)} MB`;
}

export function clockTime(t: number): string {
  return new Date(t).toLocaleTimeString([], { hour12: false });
}

/** "trunk_lean" → "Trunk lean" */
export function humanize(key: string): string {
  const s = key.replace(/[_-]+/g, ' ').trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ');
}
