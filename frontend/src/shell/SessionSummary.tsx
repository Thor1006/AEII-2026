import { useCallback, useEffect, useId, useRef, useState, useSyncExternalStore } from 'react';
import { exercises } from '../config/defaults.ts';
import { useI18n } from '../i18n/I18n.tsx';
import { humanize } from '../lib/format.ts';
import { reportCsv } from '../state/SessionReport.ts';
import type { SessionReport } from '../state/SessionReport.ts';
import { useSensor } from '../state/SensorContext.tsx';
import s from './SessionSummary.module.css';

const percent = (value: number | null) => value === null ? '—' : `${(value * 100).toFixed(1)}%`;
const duration = (ms: number | null) => ms === null ? '—' : `${Math.floor(ms / 60000)}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')}`;

/** A stable snapshot: live readings never change the finished report. */
export function SessionSummary() {
  const { store } = useSensor();
  const { ui, t, language } = useI18n();
  const subscribe = useCallback((notify: () => void) => store.subscribe(notify), [store]);
  const report = useSyncExternalStore(subscribe, () => store.reports.latest);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string>();
  const previous = useRef(report);
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const id = useId();

  useEffect(() => {
    if (report && report !== previous.current) { setOpen(true); setError(undefined); }
    previous.current = report;
  }, [report]);
  useEffect(() => {
    if (!open || !dialog.current) return;
    const element = dialog.current;
    const overflow = document.body.style.overflow;
    element.showModal();
    document.body.style.overflow = 'hidden';
    return () => { if (element.open) element.close(); document.body.style.overflow = overflow; };
  }, [open]);

  if (!report) return null;
  const exercise = exercises.find(item => item.key === report.session.exercise)?.label ?? (report.session.exercise ? humanize(report.session.exercise) : t('Not available'));
  const time = (value?: number) => value !== undefined && Number.isFinite(new Date(value).getTime())
    ? new Intl.DateTimeFormat(language, { dateStyle: 'medium', timeStyle: 'medium' }).format(value) : t('Not available');

  function download() {
    try {
      const blob = new Blob([reportCsv(report!, t)], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `session-summary-${report!.session.id.replace(/[^a-z0-9_-]/gi, '-').slice(0,80)}.csv`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { setError('Could not download the report. Please try again.'); }
  }

  function print() {
    const paths: { node: HTMLElement; previous: string | null }[] = [];
    let node = dialog.current?.parentElement;
    while (node && node !== document.body) {
      paths.push({ node, previous: node.getAttribute('data-summary-print-path') });
      node.setAttribute('data-summary-print-path', ''); node = node.parentElement;
    }
    const old = document.body.getAttribute('data-print-session');
    document.body.setAttribute('data-print-session', '');
    try { window.print(); }
    catch { setError('Could not open printing. Please use your browser print menu.'); }
    finally {
      if (old === null) document.body.removeAttribute('data-print-session');
      else document.body.setAttribute('data-print-session', old);
      for (const entry of paths) {
        if (entry.previous === null) entry.node.removeAttribute('data-summary-print-path');
        else entry.node.setAttribute('data-summary-print-path', entry.previous);
      }
    }
  }

  return ui(
    <div data-summary-host>
      <aside className={s.strip} aria-label="Last completed session">
        <span>Last completed session</span>
        <span>{t(exercise)} · {duration(report.durationMs)}</span>
        <button ref={trigger} type="button" onClick={() => { setError(undefined); setOpen(true); }} aria-haspopup="dialog">View session summary</button>
      </aside>
      <dialog ref={dialog} data-session-report className={s.dialog} aria-labelledby={id} aria-describedby={`${id}-note`}
        onClose={() => { setOpen(false); trigger.current?.focus(); }} onClick={event => { if (event.target === event.currentTarget) setOpen(false); }}>
        <header className={s.header}>
          <div><h2 id={id}>Session summary</h2><p>TrueRehab-RF</p></div>
          <button type="button" autoFocus className={s.noPrint} aria-label="Close summary" onClick={() => setOpen(false)}>Close</button>
        </header>
        <div className={s.body}>
          <p className={s.notice} id={`${id}-note`}>
            {report.synthetic ? 'Demo report: simulated data, not a clinical measurement.' : 'Prototype report: recorded scores are not a diagnosis. Follow your physiotherapist’s guidance.'}
          </p>
          {report.partial && <p className={s.warning}>Partial data: this page may have joined late, missed messages, or received invalid samples. Only received data is included.</p>}
          <dl className={s.metadata}>
            <div><dt>Exercise</dt><dd>{t(exercise)}</dd></div>
            <div><dt>Side</dt><dd>{report.session.side ? t(humanize(report.session.side)) : t('Not available')}</dd></div>
            <div><dt>Started</dt><dd>{time(report.session.startedAt)}</dd></div>
            <div><dt>Ended</dt><dd>{time(report.session.endedAt)}</dd></div>
            <div><dt>Device</dt><dd translate="no">{report.device === 'Unknown device' ? t(report.device) : report.device}</dd></div>
            <div><dt>Session ID</dt><dd translate="no">{report.session.id}</dd></div>
            {report.session.userId && <div><dt>Patient code (optional)</dt><dd translate="no">{report.session.userId}</dd></div>}
          </dl>
          <dl className={s.totals}>
            <div><dt>Completed reps</dt><dd>{report.reps ?? '—'}{report.session.targetReps ? ` / ${report.session.targetReps}` : ''}</dd></div>
            <div><dt>Duration</dt><dd>{duration(report.durationMs)}</dd></div>
          </dl>
          <p className={s.caption}>Completed reps count received finished movements.</p>
          {report.reportedReps !== null && <p className={s.caption}>{t('Kit counter: {count}. This may include an unfinished repetition.', { count: report.reportedReps })}</p>}
          <h3>Score overview</h3>
          <p className={s.caption}>Scores are percentages. Change is last minus first, in percentage points—not a percentage increase.</p>
          <div className={s.tableWrap}>
            <table className={s.table}>
              <caption className="sr-only">Session score statistics</caption>
              <thead><tr><th scope="col">Score</th><th scope="col">First</th><th scope="col">Average</th><th scope="col">Last</th><th scope="col">Change</th><th scope="col">Samples</th></tr></thead>
              <tbody>{report.scores.map(score => <tr key={score.key}>
                <th scope="row">{t(score.label)}{score.directionKnown !== false && <small>{score.higherIsWorse ? 'lower is better' : 'higher is better'}</small>}</th>
                <td>{percent(score.first)}</td><td>{percent(score.mean)}</td><td>{percent(score.last)}</td>
                <td>{score.change === null ? '—' : `${score.change > 0 ? '+' : ''}${(score.change * 100).toFixed(1)}`}</td><td>{score.samples}</td>
              </tr>)}</tbody>
            </table>
          </div>
          <h3>Session score trends</h3>
          <ReportTrend report={report} />
          <p className={s.caption}>Statistics use every valid received sample. Trend points are averaged for display. A dash means no data.</p>
          <p className={s.caption}>Only the latest completed summary is kept in this open page. Download or print it before reloading.</p>
          {error && <p role="alert" className={s.warning}>{error}</p>}
          <footer className={s.noPrint}>
            <button type="button" className="primary" onClick={download}>Download CSV</button>
            <button type="button" onClick={print}>Print / Save as PDF</button>
            <button type="button" onClick={() => setOpen(false)}>Back to dashboard</button>
            <p className={s.caption}>To save a PDF, choose “Save as PDF” in your browser’s print dialog.</p>
          </footer>
        </div>
      </dialog>
    </div>,
  );
}

function ReportTrend({ report }: { report: SessionReport }) {
  const { t, ui } = useI18n();
  const plotted = report.scores.filter(score => score.points.length);
  if (!plotted.length) return ui(<p className={s.notice}>No score samples were received in this session.</p>);
  const first = Math.min(...plotted.map(score => score.points[0].t));
  const last = Math.max(...plotted.map(score => score.points[score.points.length - 1].t));
  const start = report.session.startedAt !== undefined && Number.isFinite(new Date(report.session.startedAt).getTime()) ? report.session.startedAt : first;
  const end = report.session.endedAt !== undefined && Number.isFinite(new Date(report.session.endedAt).getTime()) && report.session.endedAt >= start ? report.session.endedAt : Math.max(start, last);
  const x = (time: number) => Math.max(0, Math.min(1, (time - start) / Math.max(1, end - start))) * 660;
  const y = (value: number) => 160 - value * 160;
  return ui(<div className={s.trend}>
    <ul className={s.legend}>{plotted.map((score,index) => <li key={score.key}><span aria-hidden="true" style={{ background: score.color ?? `var(--series-${index % 6 + 1})` }} />{t(score.label)}</li>)}</ul>
    <div className={s.plot}>
    <div className={s.yAxis} aria-hidden="true"><span>100%</span><span>50%</span><span>0%</span></div>
    <svg viewBox="0 0 660 160" preserveAspectRatio="none" role="img" aria-label={t('Session score trends')}>
      {[0, .5, 1].map(value => <line key={value} x1="0" x2="660" y1={y(value)} y2={y(value)} stroke="var(--border)" />)}
      {plotted.map((score,index) => <g key={score.key} fill="none" stroke={score.color ?? `var(--series-${index % 6 + 1})`}>
        <polyline strokeWidth="2" points={score.points.map(point => `${x(point.t)},${y(point.v)}`).join(' ')} />
        {score.points.length === 1 && <circle cx={x(score.points[0].t)} cy={y(score.points[0].v)} r="3" />}
      </g>)}
    </svg>
    </div>
    <div className={s.xAxis} aria-hidden="true"><span>0:00</span><span>{duration(Math.max(0,end-start))}</span></div>
  </div>);
}
