import { useI18n } from '../i18n/I18n.tsx';
import type { CSSProperties, ReactNode } from 'react';
import { cx, pct } from '../lib/format.ts';
import s from './ScoreGauge.module.css';

export interface ScoreGaugeProps {
  label: ReactNode;
  /** 0–1, or null when there's no reading yet. */
  value: number | null;
  confidence?: number;
  /** Fatigue/compensation: high is bad. Quality: high is good. */
  higherIsWorse?: boolean;
  /** [warn, bad] cut-offs on the "badness" scale (0–1). */
  thresholds?: [number, number];
  format?: (v: number) => string;
  /** Override the tone color (any CSS color). */
  color?: string;
  footer?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

const R = 42;
const ARC = Math.PI * R; // half circle

export type Tone = 'good' | 'warn' | 'bad' | 'none';

export function scoreTone(value: number | null, higherIsWorse = true, thresholds: [number, number] = [0.4, 0.7]): Tone {
  if (value === null) return 'none';
  const badness = higherIsWorse ? value : 1 - value;
  return badness >= thresholds[1] ? 'bad' : badness >= thresholds[0] ? 'warn' : 'good';
}

/** Half-circle gauge for a 0–1 score. */
export function ScoreGauge({
  label,
  value,
  confidence,
  higherIsWorse = true,
  thresholds = [0.4, 0.7],
  format = pct,
  color,
  footer,
  className,
  style,
}: ScoreGaugeProps) {
  const { ui } = useI18n();
  const tone = scoreTone(value, higherIsWorse, thresholds);
  const v = value === null ? 0 : Math.min(1, Math.max(0, value));
  const stroke = color ?? (tone === 'none' ? 'var(--border)' : `var(--${tone})`);
  return ui((
    <div className={cx(s.root, className)} style={style} data-tone={tone}>
      <svg viewBox="0 0 100 58" className={s.svg} role="img" aria-label={`${typeof label === 'string' ? label : 'score'}: ${value === null ? 'no data' : format(v)}`}>
        <path d="M8 50 A42 42 0 0 1 92 50" className={s.track} />
        <path
          d="M8 50 A42 42 0 0 1 92 50"
          className={s.fill}
          style={{ stroke, strokeDasharray: `${ARC * v} ${ARC}` }}
        />
      </svg>
      <div className={s.value}>{value === null ? '–' : format(v)}</div>
      <div className={s.label}>{label}</div>
      {confidence !== undefined && <div className={s.conf}>conf. {pct(confidence)}</div>}
      {footer}
    </div>
  ));
}
