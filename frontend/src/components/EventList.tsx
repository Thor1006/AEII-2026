import { useI18n } from '../i18n/I18n.tsx';
import type { CSSProperties, ReactNode } from 'react';
import { clockTime, cx, humanize } from '../lib/format.ts';
import type { EventMessage } from '../sensor/protocol.ts';
import s from './EventList.module.css';

export interface EventListProps {
  /** Newest first is up to the caller. */
  events: EventMessage[];
  /** Custom text per event; default uses label / kind / data. */
  renderEvent?: (e: EventMessage) => ReactNode;
  /** Tone per event kind, e.g. { compensation: 'bad' }. */
  tones?: Record<string, 'good' | 'warn' | 'bad' | 'info'>;
  emptyText?: string;
  className?: string;
  style?: CSSProperties;
}

export function defaultEventText(e: EventMessage): string {
  if (e.label) return e.label;
  const d = e.data ?? {};
  switch (e.kind) {
    case 'rep_start':
      return `Rep ${d.rep ?? ''} started`;
    case 'rep_end':
      return `Rep ${d.rep ?? ''} done${typeof d.romDeg === 'number' ? ` · ROM ${d.romDeg.toFixed(0)}°` : ''}`;
    case 'recommendation':
      return `Recommend: ${humanize(String(d.action ?? ''))}`;
    case 'compensation':
      return `Compensation: ${humanize(String(d.pattern ?? 'unknown'))}`;
    case 'session_start':
      return 'Session started';
    case 'session_end':
      return `Session ended${typeof d.reps === 'number' ? ` · ${d.reps} reps` : ''}`;
    case 'marker':
      return `Marker: ${String(d.label ?? '')}`;
    default:
      return humanize(e.kind);
  }
}

export function EventList({ events, renderEvent = defaultEventText, tones = {}, emptyText = 'No events yet', className, style }: EventListProps) {
  const { ui } = useI18n();
  if (!events.length) return ui(<div className={cx(s.empty, className)} style={style}>{emptyText}</div>);
  return ui((
    <ol className={cx(s.list, className)} style={style}>
      {events.map((e) => (
        <li key={`${e.src ?? ''}-${e.seq}-${e.t}`} data-tone={tones[e.kind]}>
          <time>{clockTime(e.t)}</time>
          <span translate={e.kind === 'marker' && !/^Marker(?: at \d+:\d+)?$/.test(e.label ?? String(e.data?.label ?? '')) ? 'no' : undefined}>{renderEvent(e)}</span>
        </li>
      ))}
    </ol>
  ));
}
