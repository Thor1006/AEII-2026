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
  const { store, reportStorageWarning } = useSensor();
  const { ui, t, language } = useI18n();
  const subscribe = useCallback((notify: () => void) => store.subscribe(notify), [store]);
  const records = useSyncExternalStore(subscribe, () => store.reports.records);
  const latest = records[0];
  const [report, setReport] = useState<SessionReport | undefined>(latest);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string>();
  const [deleteTarget, setDeleteTarget] = useState<SessionReport>();
  const [historyStatus, setHistoryStatus] = useState<string>();
  const previous = useRef(records);
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const deleteTrigger = useRef<HTMLButtonElement | null>(null);
  const historyTrigger = useRef<HTMLElement | null>(null);
  const id = useId();

  useEffect(() => {
    // Keep the selected snapshot unchanged while someone is reading it.
    // Removing the latest entry must not open the next-oldest summary.
    if (latest && !previous.current.includes(latest)) {
      setHistoryStatus(undefined);
      if (!open) { setReport(latest); setOpen(true); setError(undefined); }
    }
    previous.current = records;
  }, [records, latest, open]);
  useEffect(() => {
    if (!open || !dialog.current) return;
    const element = dialog.current;
    const overflow = document.body.style.overflow;
    element.showModal();
    document.body.style.overflow = 'hidden';
    return () => { if (element.open) element.close(); document.body.style.overflow = overflow; };
  }, [open]);

  const exerciseName = (item: SessionReport) => exercises.find(exercise => exercise.key === item.session.exercise)?.label
    ?? (item.session.exercise ? humanize(item.session.exercise) : 'Not available');
  const exercise = report ? exerciseName(report) : 'Not available';
  const time = (value?: number) => value !== undefined && Number.isFinite(new Date(value).getTime())
    ? new Intl.DateTimeFormat(language, { dateStyle: 'medium', timeStyle: 'medium' }).format(value) : t('Not available');
  const storageNotice = reportStorageWarning === 'unavailable'
    ? 'Browser storage is unavailable. Changes to saved sessions may be lost after reloading. Download a copy to keep them.'
    : reportStorageWarning === 'invalid' ? 'Some saved records could not be loaded. Available records are shown below.' : undefined;

  function viewRecord(item: SessionReport, button: HTMLButtonElement) {
    trigger.current = button;
    setDeleteTarget(undefined);
    setReport(item); setError(undefined); setOpen(true);
  }

  function cancelDelete() {
    setDeleteTarget(undefined);
    deleteTrigger.current?.focus();
  }

  function deleteRecord(item: SessionReport) {
    const removed = store.deleteSessionReport(item);
    setDeleteTarget(undefined);
    if (removed && report === item) setReport(undefined);
    setHistoryStatus(removed ? 'Session deleted. A slot is now available.' : 'This session is no longer in your saved history.');
    historyTrigger.current?.focus();
  }

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
      {latest && <aside className={s.strip} aria-label="Last completed session">
        <span>Last completed session</span>
        <span>{t(exerciseName(latest))} · {duration(latest.durationMs)}</span>
        <button ref={trigger} type="button" onClick={event => viewRecord(latest, event.currentTarget)} aria-haspopup="dialog">View session summary</button>
      </aside>}
      <details className={s.history}>
        <summary ref={historyTrigger}>Saved sessions <span className={s.count}>{records.length} / 5</span></summary>
        <div className={s.historyBody}>
          <p className={s.caption}>The latest 5 summaries are saved in this browser. A sixth replaces the oldest. Clearing browser data removes them.</p>
          <p className={s.caption}>Records may include your patient code. Other people using this browser can view them.</p>
          {storageNotice && <p role="alert" className={s.warning}>{storageNotice}</p>}
          {historyStatus && <p role="status" className={s.caption}>{historyStatus}</p>}
          {records.length ? <ol className={s.recordList}>{records.map((item, index) =>
            <li key={JSON.stringify([item.device, item.session.id, item.session.startedAt])}>
              <div className={s.recordRow}>
              <button type="button" className={s.recordOpen} onClick={event => viewRecord(item, event.currentTarget)} aria-haspopup="dialog"
                aria-label={t('Open saved session {number}: {exercise}, {date}', { number: index + 1, exercise: t(exerciseName(item)), date: time(item.session.endedAt) })}>
                <span className={s.recordHeading}><span>{t(exerciseName(item))}</span>{item.synthetic && <small>Demo data</small>}</span>
                <span className={s.recordMeta}>{time(item.session.endedAt)} · {item.session.side ? t(humanize(item.session.side)) : t('Not available')}</span>
                <span className={s.recordMeta}>{t('Duration')}: {duration(item.durationMs)} · {t('Completed reps')}: {item.reps ?? '—'}</span>
                <span className={s.recordLink}>View session summary<span aria-hidden="true"> →</span></span>
              </button>
              <button type="button" className={s.deleteButton} aria-expanded={deleteTarget === item}
                aria-controls={deleteTarget === item ? `${id}-delete-${index}` : undefined}
                aria-label={t('Delete saved session {number}: {exercise}, {date}', { number: index + 1, exercise: t(exerciseName(item)), date: time(item.session.endedAt) })}
                onClick={event => { deleteTrigger.current = event.currentTarget; setHistoryStatus(undefined); setDeleteTarget(item); }}>Delete</button>
              </div>
              {deleteTarget === item && <div id={`${id}-delete-${index}`} className={s.deleteConfirm} data-motion="reveal"
                role="group" aria-labelledby={`${id}-delete-title-${index}`} onKeyDown={event => {
                  if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); cancelDelete(); }
                }}>
                <p id={`${id}-delete-title-${index}`}>Delete this saved session?</p>
                <p className={s.caption}>{t(exerciseName(item))} · {time(item.session.endedAt)} · <span translate="no">{item.session.id}</span></p>
                <p className={s.caption}>This removes the summary from this browser and frees one slot. This cannot be undone. Downloaded files are not deleted.</p>
                <div className={s.deleteActions}>
                  <button type="button" autoFocus onClick={cancelDelete}>Cancel</button>
                  <button type="button" onClick={() => deleteRecord(item)}>Yes, delete</button>
                </div>
              </div>}
            </li>)}</ol> : <p className={s.empty}>No saved sessions yet. Finish a session to save its summary automatically.</p>}
        </div>
      </details>
      {report && <dialog ref={dialog} data-session-report className={s.dialog} aria-labelledby={id} aria-describedby={`${id}-note`}
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
          <p className={s.caption}>The latest 5 summaries are saved in this browser. A sixth replaces the oldest. Clearing browser data removes them.</p>
          {storageNotice && <p role="alert" className={s.warning}>{storageNotice}</p>}
          {error && <p role="alert" className={s.warning}>{error}</p>}
          <footer className={s.noPrint}>
            <button type="button" className="primary" onClick={download}>Download CSV</button>
            <button type="button" onClick={print}>Print / Save as PDF</button>
            <button type="button" onClick={() => setOpen(false)}>Back to dashboard</button>
            <p className={s.caption}>To save a PDF, choose “Save as PDF” in your browser’s print dialog.</p>
          </footer>
        </div>
      </dialog>}
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
