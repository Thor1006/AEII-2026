import { useI18n } from '../i18n/I18n.tsx';
import type { FormEvent } from 'react';
import { useState } from 'react';
import { exercises } from '../config/defaults.ts';
import { humanize } from '../lib/format.ts';
import type { SessionStartArgs } from '../sensor/protocol.ts';
import { ReplaySource } from '../sensor/sources/ReplaySource.ts';
import { useNow, useSensor, useSensorStore } from '../state/SensorContext.tsx';
import s from './shell.module.css';

const FORM_KEY = 'trf-session-form';

function loadForm(): Required<Pick<SessionStartArgs, 'exercise' | 'side'>> & { targetReps: number; userId: string } {
  const fallback = { exercise: exercises[0]?.key ?? 'elbow_flexion', side: 'right', targetReps: 12, userId: '' };
  try {
    return { ...fallback, ...JSON.parse(localStorage.getItem(FORM_KEY) ?? '{}') };
  } catch {
    return fallback;
  }
}

const mmss = (ms: number) => {
  const sec = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
};

/** Start / stop a session on the Pi and show its progress. */
export function SessionBar() {
  const { ui, t } = useI18n();
  const { canCommand, sendCommand, source, state } = useSensor();
  const store = useSensorStore();
  const now = useNow();
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState(loadForm);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string>();
  const [confirmStop, setConfirmStop] = useState(false);
  const [flash, setFlash] = useState<string>();

  const session = store.session;
  const running = session?.state === 'running';
  const commands = store.hello?.manifest.commands;
  const supports = (c: string) => canCommand && state === 'open' && (!commands || commands.includes(c));
  const reps = running ? store.sessionEvents('rep_end').length : 0;
  const exerciseLabel = (k?: string) => exercises.find((e) => e.key === k)?.label ?? (k ? humanize(k) : 'Exercise');

  const run = async (name: string, args?: Record<string, unknown>, after?: () => void) => {
    setBusy(true);
    setErr(undefined);
    try {
      const ack = await sendCommand(name, args);
      if (!ack.ok) setErr(ack.error ?? 'The Pi refused the command');
      else after?.();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onStart = (e: FormEvent) => {
    e.preventDefault();
    try {
      localStorage.setItem(FORM_KEY, JSON.stringify(form));
    } catch {
      /* ignore */
    }
    const args: SessionStartArgs = { exercise: form.exercise, side: form.side, targetReps: form.targetReps || undefined, userId: form.userId.trim() || undefined };
    void run('session.start', args as Record<string, unknown>, () => setFormOpen(false));
  };

  const onMarker = () =>
    void run('marker', { label: `Marker at ${mmss(now - (session?.startedAt ?? now))}` }, () => {
      setFlash('Marker added');
      setTimeout(() => setFlash(undefined), 2000);
    });

  // Sources that can't take commands.
  if (!canCommand) {
    return ui((
      <div className={s.sessionBar} data-state="na">
        <span className={s.muted}>
          {source instanceof ReplaySource ? 'Playing a recording. Session controls are off.' : 'Session controls need a Pi kit.'}
        </span>
      </div>
    ));
  }
  if (commands && !commands.includes('session.start')) {
    return ui((
      <div className={s.sessionBar} data-state="na">
        <span className={s.muted}>This kit doesn’t support sessions.</span>
      </div>
    ));
  }

  return ui((
    <div key={running ? 'running' : formOpen ? 'form' : 'idle'} className={s.sessionBar} data-state={running ? 'running' : 'idle'}>
      {running ? (
        <>
          <span className={s.liveTag}>
            <span className={s.recDot} /> Session running
          </span>
          <span className={s.sessionInfo}>
            <strong>{exerciseLabel(session.exercise)}</strong>
            {session.side && <span>{t('{side} side', { side: t(humanize(session.side)) })}</span>}
            <span className="num">{mmss(now - (session.startedAt ?? now))}</span>
            <span className="num">
              {reps}
              {session.targetReps ? ` / ${session.targetReps}` : ''} reps
            </span>
          </span>
          <span className={s.spacer} />
          {flash && <span className={s.flash}>{flash}</span>}
          {supports('marker') && (
            <button type="button" onClick={onMarker} disabled={busy} title="Tag this moment, e.g. when the patient reports pain">
              Add marker
            </button>
          )}
          {confirmStop ? (
            <span className={s.confirm}>
              <span>Stop now?</span>
              <button type="button" className={s.danger} disabled={busy} onClick={() => void run('session.stop', undefined, () => setConfirmStop(false))}>
                Yes, stop
              </button>
              <button type="button" onClick={() => setConfirmStop(false)}>
                Keep going
              </button>
            </span>
          ) : (
            <button type="button" onClick={() => setConfirmStop(true)} disabled={busy || !supports('session.stop')}>
              Stop session
            </button>
          )}
        </>
      ) : formOpen ? (
        <form className={s.sessionForm} onSubmit={onStart}>
          <label>
            <span>Exercise</span>
            <select value={form.exercise} onChange={(e) => setForm({ ...form, exercise: e.target.value })}>
              {exercises.map((x) => (
                <option key={x.key} value={x.key}>
                  {x.label}
                </option>
              ))}
            </select>
          </label>
          <fieldset>
            <legend>Side</legend>
            {['left', 'right'].map((side) => (
              <label key={side} className={s.radio}>
                <input type="radio" name="side" checked={form.side === side} onChange={() => setForm({ ...form, side })} />
                {humanize(side)}
              </label>
            ))}
          </fieldset>
          <label>
            <span>Target reps</span>
            <input type="number" min={1} max={200} value={form.targetReps} onChange={(e) => setForm({ ...form, targetReps: Number(e.target.value) })} style={{ width: 80 }} />
          </label>
          <label>
            <span>Patient code (optional)</span>
            <input value={form.userId} onChange={(e) => setForm({ ...form, userId: e.target.value })} placeholder="U-0007" title="A code, never a name" style={{ width: 110 }} />
          </label>
          <button type="submit" className="primary" disabled={busy}>
            {busy ? 'Starting…' : 'Start'}
          </button>
          <button type="button" onClick={() => setFormOpen(false)}>
            Cancel
          </button>
        </form>
      ) : (
        <>
          <span className={s.muted}>
            {session?.state === 'stopped' && session.startedAt && session.endedAt
              ? `Last session: ${exerciseLabel(session.exercise)}, ${mmss(session.endedAt - session.startedAt)}.`
              : 'No session running. Start one to count reps and save results for this exercise.'}
          </span>
          <span className={s.spacer} />
          <button type="button" className="primary" onClick={() => setFormOpen(true)} disabled={!supports('session.start')}>
            Start session
          </button>
        </>
      )}
      {err && <span className={s.error}>{err}</span>}
    </div>
  ));
}
