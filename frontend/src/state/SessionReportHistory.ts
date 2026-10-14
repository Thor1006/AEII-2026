import { REPORT_HISTORY_LIMIT } from './SessionReport.ts';
import type { SessionReport } from './SessionReport.ts';

export const REPORT_HISTORY_KEY = 'trf-session-history';
export type HistoryWarning = 'unavailable' | 'invalid' | undefined;
type HistoryStorage = Pick<Storage, 'getItem' | 'setItem'>;
const browserStorage = () => window.localStorage;
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === 'string' && value.length <= 4096;
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const count = (value: unknown): value is number => finite(value) && Number.isSafeInteger(value) && value >= 0;
const optionalCount = (value: unknown) => value === null || count(value);
const metric = (value: unknown) => value === null || (finite(value) && value >= 0 && value <= 1);

/** Treat saved JSON as untrusted input; a damaged record must not crash the dashboard. */
function validReport(value: unknown): value is SessionReport {
  if (!object(value) || !object(value.session)) return false;
  const session = value.session;
  if (!text(session.id) || !session.id || session.state !== 'stopped') return false;
  if (['exercise', 'side', 'userId'].some(key => session[key] !== undefined && !text(session[key]))) return false;
  if (['startedAt', 'endedAt'].some(key => session[key] !== undefined && !finite(session[key]))) return false;
  if (session.targetReps !== undefined && !count(session.targetReps)) return false;
  if (!text(value.device) || typeof value.synthetic !== 'boolean' || typeof value.partial !== 'boolean') return false;
  if (value.durationMs !== null && (!finite(value.durationMs) || value.durationMs < 0)) return false;
  if (!optionalCount(value.reps) || !count(value.observedReps) || !optionalCount(value.reportedReps)) return false;
  if (!Array.isArray(value.scores) || value.scores.length > 64) return false;
  const keys = new Set<string>();
  return value.scores.every(score => {
    if (!object(score) || !text(score.key) || !text(score.label) || keys.has(score.key)) return false;
    keys.add(score.key);
    if (typeof score.higherIsWorse !== 'boolean' || typeof score.directionKnown !== 'boolean' || !count(score.samples)) return false;
    if (![score.first, score.last, score.mean].every(metric)) return false;
    if (score.change !== null && (!finite(score.change) || Math.abs(score.change) > 1)) return false;
    // Only retain simple colours, never arbitrary CSS from modified browser storage.
    if (score.color !== undefined && (!text(score.color) || !/^(var\(--[a-z0-9-]+\)|#[a-f0-9]{3,8}|[a-z]+)$/i.test(score.color))) delete score.color;
    if (!Array.isArray(score.points) || score.points.length > 240) return false;
    return score.points.every(point => object(point) && finite(point.t) && Math.abs(point.t) <= 8.64e15
      && finite(point.v) && point.v >= 0 && point.v <= 1 && count(point.samples) && point.samples > 0);
  });
}

export function loadReportHistory(storage: () => HistoryStorage = browserStorage): { records: SessionReport[]; warning: HistoryWarning } {
  try {
    const raw = storage().getItem(REPORT_HISTORY_KEY);
    if (!raw) return { records: [], warning: undefined };
    if (raw.length > 5_000_000) return { records: [], warning: 'invalid' };
    const saved: unknown = JSON.parse(raw);
    if (!object(saved) || saved.version !== 1 || !Array.isArray(saved.records)) return { records: [], warning: 'invalid' };
    const identities = new Set<string>();
    const records: SessionReport[] = [];
    let invalid = false;
    for (const entry of saved.records) {
      if (!validReport(entry)) { invalid = true; continue; }
      const identity = JSON.stringify([entry.device, entry.session.id, entry.session.startedAt]);
      if (identities.has(identity)) continue;
      identities.add(identity);
      if (records.length < REPORT_HISTORY_LIMIT) records.push(entry);
    }
    return { records, warning: invalid ? 'invalid' : undefined };
  } catch (error) {
    return { records: [], warning: error instanceof SyntaxError ? 'invalid' : 'unavailable' };
  }
}

export function saveReportHistory(records: readonly SessionReport[], storage: () => HistoryStorage = browserStorage): boolean {
  try {
    storage().setItem(REPORT_HISTORY_KEY, JSON.stringify({ version: 1, records: records.slice(0, REPORT_HISTORY_LIMIT) }));
    return true;
  } catch { return false; }
}
