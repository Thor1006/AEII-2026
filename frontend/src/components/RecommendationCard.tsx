import type { CSSProperties, ReactNode } from 'react';
import { clockTime, cx, humanize } from '../lib/format.ts';
import type { RecommendationAction } from '../sensor/protocol.ts';
import s from './RecommendationCard.module.css';

export interface RecommendationStyle {
  label: string;
  /** Shown under the label. */
  hint?: string;
  tone: 'good' | 'warn' | 'bad' | 'info';
  icon?: ReactNode;
}

export interface RecommendationCardProps {
  action: RecommendationAction | null;
  reason?: string;
  at?: number;
  /** Labels, hints and tones per action. Unknown actions fall back to a humanized name. */
  styles?: Record<string, RecommendationStyle>;
  emptyText?: string;
  className?: string;
  style?: CSSProperties;
}

export function RecommendationCard({ action, reason, at, styles = {}, emptyText = 'Waiting for the first rep', className, style }: RecommendationCardProps) {
  if (!action) {
    return <div className={cx(s.root, s.empty, className)} style={style}>{emptyText}</div>;
  }
  const st = styles[action] ?? { label: humanize(action), tone: 'info' as const };
  return (
    <div className={cx(s.root, className)} style={style} data-tone={st.tone} role="status" aria-live="polite">
      {st.icon && <div className={s.icon}>{st.icon}</div>}
      <div className={s.text}>
        <div className={s.label}>{st.label}</div>
        {st.hint && <div className={s.hint}>{st.hint}</div>}
        {reason && <div className={s.reason}>{reason}</div>}
      </div>
      {at !== undefined && <time className={s.time}>{clockTime(at)}</time>}
    </div>
  );
}
