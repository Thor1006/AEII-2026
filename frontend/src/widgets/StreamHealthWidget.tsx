import { humanize } from '../lib/format.ts';
import type { StreamHealth, StreamState } from '../state/describe.ts';
import { streamHealth } from '../state/describe.ts';
import { useNow, useSensorStore } from '../state/SensorContext.tsx';
import s from './widgets.module.css';

const WORDS: Record<StreamState, string> = {
  ok: 'Arriving',
  waiting: 'Waiting…',
  late: 'Stopped',
  missing: 'Never arrived',
  off: 'Device off',
  unexpected: 'Arriving (not announced)',
};

function detail(h: StreamHealth): string | undefined {
  if (h.detail) return h.detail;
  if (h.state === 'late' && h.ageMs !== null) return `Last seen ${Math.round(h.ageMs / 1000)} s ago`;
  if (h.state === 'missing') return 'The Pi said it would send this';
  return undefined;
}

/** Every stream the Pi promised, and whether it's arriving. */
export function StreamHealthWidget() {
  const store = useSensorStore();
  const now = useNow();
  const rows = streamHealth(store, now);
  const problems = rows.filter((r) => r.state === 'late' || r.state === 'missing');
  const groups = [...new Set(rows.map((r) => r.group))];

  return (
    <div className={s.health}>
      <p className={s.summary} data-tone={problems.length ? 'bad' : rows.length ? 'good' : undefined}>
        {!rows.length
          ? 'No data yet.'
          : problems.length
            ? `${problems.length} of ${rows.length} streams not arriving`
            : `All ${rows.length} streams arriving`}
        {!store.hello && rows.length > 0 && <span className={s.muted}> · the Pi didn’t send a manifest, so this only lists what arrived</span>}
      </p>
      {groups.map((g) => (
        <div key={g}>
          <h3 className={s.groupTitle}>{g}</h3>
          <ul className={s.rows}>
            {rows
              .filter((r) => r.group === g)
              .map((r) => (
                <li key={r.id} data-state={r.state}>
                  <span className={s.dot} />
                  <span className={s.rowLabel}>{r.label || humanize(r.id)}</span>
                  <span className={s.rowState}>
                    {WORDS[r.state]}
                    {detail(r) && <small>{detail(r)}</small>}
                  </span>
                </li>
              ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
