import type { ScoreDef } from '../config/defaults.ts';
import type { SensorMessage, SessionInfo } from '../sensor/protocol.ts';
import { humanize } from '../lib/format.ts';

export interface TrendPoint { t: number; v: number; samples: number }
export interface ReportScore extends ScoreDef {
  directionKnown: boolean;
  samples: number;
  first: number | null;
  last: number | null;
  mean: number | null;
  change: number | null;
  points: TrendPoint[];
}
export interface SessionReport {
  session: SessionInfo;
  device: string;
  synthetic: boolean;
  partial: boolean;
  durationMs: number | null;
  reps: number | null;
  observedReps: number;
  reportedReps: number | null;
  scores: ReportScore[];
}
export interface ReportContext {
  defs: ScoreDef[];
  device: string;
  synthetic: boolean;
  dropped: number;
}
interface Metric {
  def: ScoreDef;
  directionKnown: boolean;
  count: number;
  sum: number;
  first?: { t: number; v: number };
  last?: { t: number; v: number };
  points: TrendPoint[];
}
interface Active {
  session: SessionInfo;
  context: ReportContext;
  partial: boolean;
  scores: Map<string, Metric>;
  observedStart: boolean;
  reps: Set<string>;
  seen: Set<string>;
}
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const timestamp = (value: unknown): value is number => finite(value) && Math.abs(value) <= 8.64e15;
const validReps = (value: unknown): value is number => finite(value) && Number.isInteger(value) && value >= 0;
const sessionIdentity = (session: SessionInfo, device: string) => JSON.stringify([device, session.id, session.startedAt]);

export const REPORT_HISTORY_LIMIT = 5;

/** Whole-session snapshots, independent of the live chart/event buffers. */
export class SessionReportTracker {
  private history: readonly SessionReport[];
  private active: Active | null = null;
  private readonly completed = new Set<string>();

  constructor(records: readonly SessionReport[] = []) {
    this.history = records.slice(0, REPORT_HISTORY_LIMIT);
    for (const report of this.history) this.completed.add(sessionIdentity(report.session, report.device));
  }
  get records(): readonly SessionReport[] { return this.history; }
  get latest(): SessionReport | null { return this.history[0] ?? null; }

  /** Remove only the exact saved snapshot; session IDs can be reused by kits. */
  remove(report: SessionReport): boolean {
    if (!this.history.includes(report)) return false;
    this.history = this.history.filter(item => item !== report);
    return true;
  }

  reset(): void { this.active = null; }

  update(session: SessionInfo | null, context: ReportContext, observedStart = false, reportedReps?: unknown): void {
    if (!session) return;
    if (session.state === 'running') {
      const same = this.active?.session.id === session.id && this.active.session.startedAt === session.startedAt;
      if (!same) {
        // An old running status must not reopen an already completed session.
        if (this.completed.has(sessionIdentity(session, context.device))) return;
        this.active = { session: { ...session }, context: { ...context }, partial: false, observedStart,
          scores: new Map(context.defs.map(def => [def.key, { def: { ...def }, directionKnown: true, count: 0, sum: 0, points: [] }])),
          reps: new Set(), seen: new Set() };
      } else {
        this.active!.session = { ...session };
        this.active!.context.synthetic ||= context.synthetic;
        this.active!.observedStart ||= observedStart;
      }
      return;
    }
    const active = this.active;
    if (!active || active.session.id !== session.id || active.session.startedAt !== session.startedAt) return;
    const validTimes = timestamp(session.startedAt) && timestamp(session.endedAt) && session.endedAt >= session.startedAt;
    const observedReps = active.reps.size;
    const report: SessionReport = {
      session: { ...session }, device: active.context.device,
      synthetic: active.context.synthetic || context.synthetic,
      partial: !active.observedStart || active.partial || !validTimes || context.dropped > active.context.dropped
        || (validReps(reportedReps) && (reportedReps < observedReps || reportedReps > observedReps + 1)),
      durationMs: validTimes ? session.endedAt! - session.startedAt! : null,
      // The kit counter can include the currently unfinished rep (the demo does).
      // Never turn that counter into a claim of completed movements.
      reps: !active.observedStart && !observedReps ? null : observedReps,
      observedReps, reportedReps: validReps(reportedReps) ? reportedReps : null,
      scores: [...active.scores.values()].map(metric => ({ ...metric.def, directionKnown: metric.directionKnown, samples: metric.count,
        first: metric.first?.v ?? null, last: metric.last?.v ?? null,
        mean: metric.count ? metric.sum / metric.count : null,
        change: metric.first && metric.last ? metric.last.v - metric.first.v : null,
        points: metric.points.map(point => ({ ...point })).sort((a,b) => a.t - b.t),
      })),
    };
    this.history = [report, ...this.history].slice(0, REPORT_HISTORY_LIMIT);
    // Late messages must not recreate a deleted report. Keep this guard bounded.
    this.completed.add(sessionIdentity(session, report.device));
    if (this.completed.size > 64) this.completed.delete(this.completed.values().next().value!);
    this.active = null;
  }

  ingest(message: SensorMessage, session: SessionInfo | null, context: ReportContext): void {
    const start = message.type === 'event' && message.kind === 'session_start';
    const reported = message.type === 'event' && message.kind === 'session_end' ? message.data?.reps : undefined;
    this.update(session, context, start, reported);
    const active = this.active;
    if (!active || (message.sessionId && message.sessionId !== active.session.id)) return;
    if (!timestamp(message.t)) { active.partial = true; return; }
    if (finite(active.session.startedAt) && message.t < active.session.startedAt) return;
    if (message.type !== 'scores' && !(message.type === 'event' && message.kind === 'rep_end')) return;
    const identity = `${message.src ?? ''}:${message.type}:${message.seq}:${message.t}`;
    if (active.seen.has(identity)) return;
    active.seen.add(identity);
    if (active.seen.size > 512) active.seen.delete(active.seen.values().next().value!);
    if (message.type === 'event') {
      // Rep numbers deduplicate repeats even if they are re-broadcast with a new seq.
      const key = validReps(message.data?.rep) ? `rep:${message.data.rep}` : identity;
      active.reps.add(key);
      return;
    }
    for (const [key, score] of Object.entries(message.scores)) {
      if (!finite(score.value) || score.value < 0 || score.value > 1) { active.partial = true; continue; }
      let metric = active.scores.get(key);
      if (!metric) {
        if (active.scores.size >= 64) { active.partial = true; continue; }
        metric = { def: { key, label: humanize(key), higherIsWorse: true }, directionKnown: false, count: 0, sum: 0, points: [] };
        active.scores.set(key, metric);
      }
      const value = score.value;
      if (metric.last && message.t - metric.last.t > 5000) active.partial = true;
      if (!metric.first || message.t < metric.first.t) metric.first = { t: message.t, v: value };
      if (!metric.last || message.t >= metric.last.t) metric.last = { t: message.t, v: value };
      metric.count++; metric.sum += value;
      metric.points.push({ t: message.t, v: value, samples: 1 });
      if (metric.points.length > 240) {
        metric.points.sort((a,b) => a.t - b.t);
        const compact: TrendPoint[] = [];
        for (let i = 0; i < metric.points.length; i += 2) {
          const a = metric.points[i], b = metric.points[i + 1];
          if (!b) { compact.push(a); continue; }
          const samples = a.samples + b.samples;
          compact.push({ t: (a.t * a.samples + b.t * b.samples) / samples,
            v: (a.v * a.samples + b.v * b.samples) / samples, samples });
        }
        metric.points = compact;
      }
    }
  }
}

/** Quote every cell and neutralise spreadsheet formulas in user/device text. */
export function reportCsv(report: SessionReport, t: (text: string) => string = text => text): string {
  const rows: (string | number | null)[][] = [[t('Section'), t('Field'), t('Value'), t('Unit'), t('Samples'), t('Timestamp')]];
  const meta = (field: string, value: string | number | null, unit = '') => rows.push([t('Session'), t(field), value, unit, '', '']);
  meta('Session ID', report.session.id); meta('Exercise', report.session.exercise ?? '');
  meta('Side', report.session.side ?? ''); meta('Patient code (optional)', report.session.userId ?? '');
  meta('Device', report.device); meta('Demo data', report.synthetic ? t('Yes') : t('No'));
  meta('Started', timestamp(report.session.startedAt) ? new Date(report.session.startedAt).toISOString() : null);
  meta('Ended', timestamp(report.session.endedAt) ? new Date(report.session.endedAt).toISOString() : null);
  meta('Duration', report.durationMs === null ? null : report.durationMs / 1000, 's');
  meta('Completed reps', report.reps); meta('Observed reps', report.observedReps);
  meta('Kit counter', report.reportedReps);
  meta('Partial data', report.partial ? t('Yes') : t('No'));
  for (const score of report.scores) {
    for (const [label, value] of [['First', score.first], ['Average', score.mean], ['Last', score.last], ['Change', score.change]] as const) {
      rows.push([t(score.label), t(label), value === null ? null : +(value * 100).toFixed(3), label === 'Change' ? t('percentage points') : '%', score.samples, '']);
    }
    for (const point of score.points) rows.push([t(score.label), t('Trend sample'), +(point.v * 100).toFixed(3), '%', point.samples, new Date(point.t).toISOString()]);
  }
  const cell = (value: string | number | null) => {
    let text = value === null ? '' : String(value);
    if (typeof value === 'string' && /^[\s]*[=+\-@]/.test(text)) text = `'${text}`;
    return `"${text.replaceAll('"', '""')}"`;
  };
  return '\uFEFF' + rows.map(row => row.map(cell).join(',')).join('\r\n') + '\r\n';
}
