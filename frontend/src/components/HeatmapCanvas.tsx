import type { CSSProperties, MouseEvent } from 'react';
import { useEffect, useRef, useState } from 'react';
import { useCanvasSize } from '../lib/canvas.ts';
import type { Colormap, ColormapName } from '../lib/colormaps.ts';
import { colormapCss, getColormap } from '../lib/colormaps.ts';
import { cx } from '../lib/format.ts';
import type { AxisInfo } from '../sensor/protocol.ts';
import s from './HeatmapCanvas.module.css';

export interface HeatmapCanvasProps {
  /** Row-major values, length rows*cols. */
  data: Float32Array | null;
  shape: [number, number] | null;
  colormap?: ColormapName | Colormap;
  /** Fixed value range, or 'auto' (smoothed min/max per frame). */
  range?: [number, number] | 'auto';
  /** Draw row 0 at the bottom (range increasing upward). Default true. */
  flipY?: boolean;
  xAxis?: AxisInfo;
  yAxis?: AxisInfo;
  unit?: string;
  showColorbar?: boolean;
  /** Placeholder when there's no data. */
  emptyText?: string;
  className?: string;
  style?: CSSProperties;
  onHover?: (cell: { row: number; col: number; value: number } | null) => void;
}

/** Draws any 2-D map (range–Doppler, micro-Doppler, ...) with pixel-exact cells. */
export function HeatmapCanvas({
  data,
  shape,
  colormap = 'viridis',
  range = 'auto',
  flipY = true,
  xAxis,
  yAxis,
  unit,
  showColorbar = true,
  emptyText = 'No frame yet',
  className,
  style,
  onHover,
}: HeatmapCanvasProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const offscreen = useRef<HTMLCanvasElement | null>(null);
  const auto = useRef<[number, number] | null>(null);
  const [shown, setShown] = useState<[number, number]>([0, 1]);
  const size = useCanvasSize(wrapRef, canvasRef);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data || !shape) return;
    const [rows, cols] = shape;
    if (data.length < rows * cols) return;

    let [lo, hi] = range === 'auto' ? autoRange(data, auto) : range;
    if (hi <= lo) hi = lo + 1;

    const off = (offscreen.current ??= document.createElement('canvas'));
    if (off.width !== cols || off.height !== rows) {
      off.width = cols;
      off.height = rows;
    }
    const octx = off.getContext('2d')!;
    const img = octx.createImageData(cols, rows);
    const lut = getColormap(colormap);
    const k = 255 / (hi - lo);
    for (let r = 0; r < rows; r++) {
      const dstRow = flipY ? rows - 1 - r : r;
      for (let c = 0; c < cols; c++) {
        const v = data[r * cols + c];
        const i = Number.isFinite(v) ? Math.max(0, Math.min(255, ((v - lo) * k) | 0)) : 0;
        const p = (dstRow * cols + c) * 4;
        img.data[p] = lut[i * 3];
        img.data[p + 1] = lut[i * 3 + 1];
        img.data[p + 2] = lut[i * 3 + 2];
        img.data[p + 3] = 255;
      }
    }
    octx.putImageData(img, 0, 0);

    const ctx = canvas.getContext('2d')!;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(off, 0, 0, canvas.width, canvas.height);
    // Only re-render the colorbar labels when they visibly change.
    setShown((prev) => (Math.abs(prev[0] - lo) < 0.05 && Math.abs(prev[1] - hi) < 0.05 ? prev : [lo, hi]));
  }, [data, shape, colormap, range, flipY, size]);

  const handleMove = (e: MouseEvent) => {
    if (!onHover || !data || !shape) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const [rows, cols] = shape;
    const col = Math.floor(((e.clientX - rect.left) / rect.width) * cols);
    const yFrac = (e.clientY - rect.top) / rect.height;
    const row = Math.floor((flipY ? 1 - yFrac : yFrac) * rows);
    if (row < 0 || row >= rows || col < 0 || col >= cols) return onHover(null);
    onHover({ row, col, value: data[row * cols + col] });
  };

  const fmt = (n: number) => (Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(1));

  return (
    <div className={cx(s.root, className)} style={style}>
      {yAxis && (
        <div className={s.yAxis}>
          <span>{fmt(flipY ? yAxis.max : yAxis.min)}</span>
          <span className={s.axisLabel}>
            {yAxis.label}
            {yAxis.unit && ` (${yAxis.unit})`}
          </span>
          <span>{fmt(flipY ? yAxis.min : yAxis.max)}</span>
        </div>
      )}
      <div className={s.plot}>
        <div ref={wrapRef} className={s.canvasWrap} onMouseMove={handleMove} onMouseLeave={() => onHover?.(null)}>
          <canvas ref={canvasRef} className={s.canvas} />
          {!data && <div className={s.empty}>{emptyText}</div>}
        </div>
        {xAxis && (
          <div className={s.xAxis}>
            <span>{fmt(xAxis.min)}</span>
            <span className={s.axisLabel}>
              {xAxis.label}
              {xAxis.unit && ` (${xAxis.unit})`}
            </span>
            <span>{fmt(xAxis.max)}</span>
          </div>
        )}
      </div>
      {showColorbar && (
        <div className={s.colorbar}>
          <span className="num">{fmt(shown[1])}</span>
          <div className={s.bar} style={{ background: colormapCss(colormap) }} />
          <span className="num">{fmt(shown[0])}</span>
          {unit && <span className={s.unit}>{unit}</span>}
        </div>
      )}
    </div>
  );
}

/** Min/max with exponential smoothing so the colors don't flicker frame to frame. */
function autoRange(data: Float32Array, prev: { current: [number, number] | null }): [number, number] {
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of data) {
    if (!Number.isFinite(v)) continue;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  if (!Number.isFinite(lo)) return prev.current ?? [0, 1];
  const a = 0.15;
  prev.current = prev.current ? [prev.current[0] + (lo - prev.current[0]) * a, prev.current[1] + (hi - prev.current[1]) * a] : [lo, hi];
  return prev.current;
}
