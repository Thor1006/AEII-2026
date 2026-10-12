import type { CSSProperties, ReactNode } from 'react';
import { cx } from '../lib/format.ts';
import s from './Stat.module.css';

export interface StatProps {
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  tone?: 'good' | 'warn' | 'bad';
  size?: 'sm' | 'lg';
  className?: string;
  style?: CSSProperties;
}

/** A labelled number. */
export function Stat({ label, value, unit, tone, size = 'sm', className, style }: StatProps) {
  return (
    <div className={cx(s.stat, s[size], className)} style={style} data-tone={tone}>
      <div className={s.value}>
        {value}
        {unit && <span className={s.unit}>{unit}</span>}
      </div>
      <div className={s.label}>{label}</div>
    </div>
  );
}
