import type { CSSProperties } from 'react';
import { useEffect, useRef } from 'react';
import { cssColor, useCanvasSize } from '../lib/canvas.ts';
import { cx } from '../lib/format.ts';
import type { TimedValue } from '../state/SensorStore.ts';
import s from './TimeSeriesChart.module.css';

export interface Series {
  key: string;
  label: string;
  /** Any CSS color, including var(--series-1). */
  color?: string;
  points: TimedValue[];
  /** Draw the confidence (c) as a faint band. */
  showConfidence?: boolean;
}

export interface TimeSeriesChartProps {
  series: Series[];
  /** Visible window in ms, ending at the newest sample (sensor time, so replay works). */
  windowMs?: number;
  yRange?: [number, number] | 'auto';
  /** Break the line when samples are further apart than this (dropped data). */
  gapMs?: number;
  /** Horizontal reference lines, e.g. score thresholds. */
  thresholds?: { value: number; color?: string }[];
  formatY?: (v: number) => string;
  showLegend?: boolean;
  /** CSS height. Default fills the parent. */
  height?: number | string;
  className?: string;
  style?: CSSProperties;
}

const PAD = { l: 38, r: 8, t: 6, b: 18 };

/** Multi-series line chart on canvas. Cheap enough for 20+ updates/s. */
export function TimeSeriesChart({
  series,
  windowMs = 30_000,
  yRange = 'auto',
  gapMs = 1000,
  thresholds = [],
  formatY = defaultFormat,
  showLegend = true,
  height,
  className,
  style,
}: TimeSeriesChartProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const size = useCanvasSize(wrapRef, canvasRef);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || size.width === 0) return;
    const ctx = canvas.getContext('2d')!;
    const { width: W, height: H, dpr } = size;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);

    const tEnd = Math.max(-Infinity, ...series.map((sr) => sr.points[sr.points.length - 1]?.t ?? -Infinity));
    const tStart = tEnd - windowMs;
    const visible = series.map((sr) => sr.points.filter((p) => p.t >= tStart));

    let [lo, hi] = yRange === 'auto' ? [Infinity, -Infinity] : yRange;
    if (yRange === 'auto') {
      for (const pts of visible) for (const p of pts) {
        if (p.v < lo) lo = p.v;
        if (p.v > hi) hi = p.v;
      }
      if (!Number.isFinite(lo)) [lo, hi] = [0, 1];
      const padY = (hi - lo) * 0.08 || 1;
      lo -= padY;
      hi += padY;
    }

    const x = (t: number) => PAD.l + ((t - tStart) / windowMs) * (W - PAD.l - PAD.r);
    const y = (v: number) => PAD.t + (1 - (v - lo) / (hi - lo)) * (H - PAD.t - PAD.b);
    const el = wrapRef.current!;

    // grid + labels
    ctx.font = '10px ui-monospace, Menlo, monospace';
    ctx.fillStyle = cssColor(el, 'var(--chart-text)');
    ctx.strokeStyle = cssColor(el, 'var(--chart-grid)');
    ctx.lineWidth = 1;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    for (const v of niceTicks(lo, hi, Math.max(2, Math.floor((H - PAD.t - PAD.b) / 28)))) {
      const yy = Math.round(y(v)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(PAD.l, yy);
      ctx.lineTo(W - PAD.r, yy);
      ctx.stroke();
      ctx.fillText(formatY(v), PAD.l - 4, yy);
    }
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    const stepS = windowMs >= 60_000 ? 20 : windowMs >= 20_000 ? 10 : 2;
    for (let sec = 0; sec <= windowMs / 1000; sec += stepS) {
      ctx.fillText(sec === 0 ? 'now' : `-${sec}s`, x(tEnd - sec * 1000), H - PAD.b + 4);
    }

    for (const th of thresholds) {
      ctx.save();
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = cssColor(el, th.color ?? 'var(--text-muted)');
      ctx.beginPath();
      ctx.moveTo(PAD.l, y(th.value));
      ctx.lineTo(W - PAD.r, y(th.value));
      ctx.stroke();
      ctx.restore();
    }

    if (!Number.isFinite(tEnd)) return;

    series.forEach((sr, i) => {
      const pts = visible[i];
      if (!pts.length) return;
      const color = cssColor(el, sr.color ?? `var(--series-${(i % 6) + 1})`);

      if (sr.showConfidence && pts.some((p) => p.c !== undefined)) {
        ctx.save();
        ctx.globalAlpha = 0.12;
        ctx.fillStyle = color;
        ctx.beginPath();
        pts.forEach((p, j) => {
          const half = (1 - (p.c ?? 1)) * 0.5;
          const px = x(p.t);
          const py = y(p.v + half);
          if (j === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        });
        for (let j = pts.length - 1; j >= 0; j--) {
          const p = pts[j];
          ctx.lineTo(x(p.t), y(p.v - (1 - (p.c ?? 1)) * 0.5));
        }
        ctx.closePath();
        ctx.fill();
        ctx.restore();
      }

      ctx.strokeStyle = color;
      ctx.lineWidth = 1.75;
      ctx.lineJoin = 'round';
      ctx.beginPath();
      let prevT = -Infinity;
      for (const p of pts) {
        if (p.t - prevT > gapMs) ctx.moveTo(x(p.t), y(p.v));
        else ctx.lineTo(x(p.t), y(p.v));
        prevT = p.t;
      }
      ctx.stroke();
    });
  });

  return (
    <div className={cx(s.root, className)} style={{ height, ...style }}>
      {showLegend && series.length > 0 && (
        <ul className={s.legend}>
          {series.map((sr, i) => {
            const last = sr.points[sr.points.length - 1];
            return (
              <li key={sr.key}>
                <span className={s.swatch} style={{ background: sr.color ?? `var(--series-${(i % 6) + 1})` }} />
                {sr.label}
                <span className="num">{last ? formatY(last.v) : '–'}</span>
              </li>
            );
          })}
        </ul>
      )}
      <div ref={wrapRef} className={s.canvasWrap}>
        <canvas ref={canvasRef} className={s.canvas} />
      </div>
    </div>
  );
}

function defaultFormat(v: number): string {
  const a = Math.abs(v);
  return a >= 100 || v === Math.round(v) ? v.toFixed(0) : a >= 10 ? v.toFixed(1) : v.toFixed(2);
}

/** Round tick values (1, 2, 5 × 10^n) inside [lo, hi]. */
export function niceTicks(lo: number, hi: number, maxTicks = 5): number[] {
  const raw = (hi - lo) / maxTicks;
  if (!(raw > 0) || !Number.isFinite(raw)) return [lo];
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * mag).find((st) => st >= raw) ?? 10 * mag;
  const ticks: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) ticks.push(+v.toFixed(10));
  return ticks;
}
