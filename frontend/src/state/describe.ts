/**
 * What things are called and whether they're healthy. Labels come from the Pi's
 * `hello` manifest when there is one, and fall back to config/defaults.ts otherwise.
 */
import type { RecommendationStyle } from '../components/RecommendationCard.tsx';
import type { ScoreDef } from '../config/defaults.ts';
import { auxChannelLabels, recommendationStyles, scoreDefs as defaultScoreDefs, viewTitles } from '../config/defaults.ts';
import { humanize } from '../lib/format.ts';
import type { FrameStreamInfo } from '../sensor/protocol.ts';
import { parseProtocolVersion } from '../sensor/protocol.ts';
import type { SensorStore } from './SensorStore.ts';

const SERIES_COLORS = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)', 'var(--series-5)', 'var(--series-6)'];

export function scoreDefs(store: SensorStore): ScoreDef[] {
  const fromPi = store.hello?.manifest.scores;
  if (!fromPi?.length) return defaultScoreDefs;
  return fromPi.map((s, i) => {
    const fallback = defaultScoreDefs.find((d) => d.key === s.key);
    return {
      key: s.key,
      label: s.label || fallback?.label || humanize(s.key),
      higherIsWorse: s.higherIsWorse,
      thresholds: s.thresholds ?? fallback?.thresholds,
      color: fallback?.color ?? SERIES_COLORS[i % SERIES_COLORS.length],
      description: s.description ?? fallback?.description,
    };
  });
}

export function auxInfo(store: SensorStore, key: string): { label: string; unit?: string } {
  const fromPi = store.hello?.manifest.aux.find((a) => a.key === key);
  if (fromPi) return { label: fromPi.label, unit: fromPi.unit };
  return { label: auxChannelLabels[key] ?? humanize(key) };
}

export function auxKeys(store: SensorStore): string[] {
  const announced = store.hello?.manifest.aux.map((a) => a.key) ?? [];
  const seen = [...store.aux.keys()].filter((k) => !announced.includes(k));
  return [...announced, ...seen];
}

export function actionStyles(store: SensorStore): Record<string, RecommendationStyle> {
  const out: Record<string, RecommendationStyle> = { ...recommendationStyles };
  for (const a of store.hello?.manifest.actions ?? []) {
    out[a.key] = { ...out[a.key], label: a.label, hint: a.hint ?? out[a.key]?.hint, tone: a.tone };
  }
  return out;
}

export function frameInfo(store: SensorStore, view: string): (FrameStreamInfo & { title: string }) | undefined {
  const fromPi = store.hello?.manifest.frames.find((f) => f.view === view);
  const title = fromPi?.label ?? viewTitles[view] ?? humanize(view);
  return fromPi ? { ...fromPi, title } : undefined;
}

export function viewTitle(store: SensorStore, view: string): string {
  return frameInfo(store, view)?.title ?? viewTitles[view] ?? humanize(view);
}

// ---------- stream health ----------

export type StreamState = 'ok' | 'waiting' | 'late' | 'missing' | 'off' | 'unexpected';

export interface StreamHealth {
  id: string;
  group: 'Radar' | 'Scores' | 'Signals' | 'Link';
  label: string;
  state: StreamState;
  /** ms since last seen, null if never. */
  ageMs: number | null;
  detail?: string;
}

/** Compare what's arriving against what the Pi promised in its manifest. */
export function streamHealth(store: SensorStore, now = Date.now()): StreamHealth[] {
  const m = store.hello?.manifest;
  const connectedFor = store.stats.firstRecvT === null ? 0 : now - store.stats.firstRecvT;
  const out: StreamHealth[] = [];

  const check = (id: string, group: StreamHealth['group'], label: string, rateHz: number | undefined, detailOff?: string) => {
    const last = store.lastSeen.get(id);
    const tolerance = Math.max(3000, rateHz ? (3 * 1000) / rateHz : 0);
    const age = last === undefined ? null : now - last;
    let state: StreamState;
    if (detailOff) state = 'off';
    else if (age === null) state = connectedFor < tolerance ? 'waiting' : 'missing';
    else state = age > tolerance ? 'late' : 'ok';
    out.push({ id, group, label, state, ageMs: age, detail: detailOff });
  };

  const known = new Set<string>();
  if (m) {
    for (const f of m.frames) {
      known.add(`frame:${f.view}`);
      check(`frame:${f.view}`, 'Radar', f.label ?? humanize(f.view), f.fps);
    }
    for (const s of m.scores) {
      known.add(`score:${s.key}`);
      check(`score:${s.key}`, 'Scores', s.label, s.rateHz);
    }
    for (const a of m.aux) {
      known.add(`aux:${a.key}`);
      const dev = a.device ? store.devices[a.device] : undefined;
      const off = dev && dev.state !== 'ok' ? `${dev.label ?? a.device}: ${dev.message ?? dev.state}` : undefined;
      check(`aux:${a.key}`, 'Signals', a.label, a.rateHz, off);
    }
    known.add('status');
    check('status', 'Link', 'Heartbeat (status)', 1000 / (m.statusIntervalMs ?? 1000));
  }

  // Streams arriving that the manifest didn't list (or everything, for v1 senders).
  for (const [id, last] of store.lastSeen) {
    if (known.has(id) || id.startsWith('event:')) continue;
    const [kind, key] = id.split(':');
    const group: StreamHealth['group'] = kind === 'frame' ? 'Radar' : kind === 'score' ? 'Scores' : kind === 'aux' ? 'Signals' : 'Link';
    const age = now - last;
    out.push({
      id,
      group,
      label: key ? humanize(key) : 'Heartbeat (status)',
      state: m ? 'unexpected' : age > 3000 ? 'late' : 'ok',
      ageMs: age,
      detail: m ? 'Not listed in the Pi’s manifest' : undefined,
    });
  }
  return out;
}

// ---------- link quality in plain words ----------

export type Quality = 'good' | 'fair' | 'poor';

export function linkQuality(store: SensorStore, now = Date.now()): { quality: Quality; reasons: string[] } {
  const { stats } = store;
  const reasons: string[] = [];
  const total = stats.received + stats.dropped;
  const dropPct = total ? (stats.dropped / total) * 100 : 0;
  const expectedFps = store.hello?.manifest.frames[0]?.fps ?? store.status?.fps;
  const silentMs = stats.lastRecvT === null ? Infinity : now - stats.lastRecvT;

  if (silentMs > 3000) reasons.push(`No data for ${Math.round(silentMs / 1000)} s`);
  if (dropPct > 5) reasons.push(`${dropPct.toFixed(0)}% of messages lost`);
  else if (dropPct > 1) reasons.push(`${dropPct.toFixed(1)}% of messages lost`);
  if (expectedFps && stats.fps > 0 && stats.fps < expectedFps * 0.7) reasons.push(`Radar at ${stats.fps.toFixed(0)} of ${expectedFps} frames/s`);
  if (stats.rttMs !== null && stats.rttMs > 300) reasons.push(`Slow link (${stats.rttMs.toFixed(0)} ms)`);

  const poor = silentMs > 3000 || dropPct > 5 || (stats.rttMs ?? 0) > 800;
  return { quality: poor ? 'poor' : reasons.length ? 'fair' : 'good', reasons };
}

/** Warn when the Pi speaks a different major protocol version. */
export function protocolWarning(store: SensorStore): string | null {
  if (!store.hello) return null;
  const [major] = parseProtocolVersion(store.hello.protocol);
  if (major !== 1) return `The Pi uses protocol ${store.hello.protocol}; this page understands 1.x. Update one of them.`;
  return null;
}
