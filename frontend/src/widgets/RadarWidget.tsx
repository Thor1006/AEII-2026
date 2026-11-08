import { useI18n } from '../i18n/I18n.tsx';
import { useRef, useState } from 'react';
import type { HeatmapCanvasProps } from '../components/HeatmapCanvas.tsx';
import { HeatmapCanvas } from '../components/HeatmapCanvas.tsx';
import { useSensorStore } from '../state/SensorContext.tsx';
import { viewTitle } from '../state/describe.ts';
import s from './widgets.module.css';

export interface RadarWidgetProps extends Partial<Omit<HeatmapCanvasProps, 'data' | 'shape'>> {
  /** Which frame view to show. Default: the first one, with buttons to switch when the source sends several. */
  view?: string;
  showReadout?: boolean;
}

function hasNegative(data: Float32Array): boolean {
  for (let i = 0; i < data.length; i++) if (data[i] < 0) return true;
  return false;
}

function maxAbs(data: Float32Array): number {
  let m = 0;
  for (let i = 0; i < data.length; i++) m = Math.max(m, Math.abs(data[i]));
  return m;
}

/** Live radar map from the latest frame of one view. Signed maps (e.g. phase change) get a two-sided colour scale. */
export function RadarWidget({ view, showReadout = true, ...heatmap }: RadarWidgetProps) {
  const { ui } = useI18n();
  const store = useSensorStore();
  const [hover, setHover] = useState<{ row: number; col: number; value: number } | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const announced = store.hello?.manifest.frames.map((f) => f.view) ?? [];
  const views = view ? [view] : [...new Set([...announced, ...store.frames.keys()])];
  const current = view ?? (picked && views.includes(picked) ? picked : views[0]);
  const frame = current ? store.frames.get(current) : undefined;
  // A view that has shown a negative value is signed (phase change, point height): it keeps the two-sided colour
  // scale even for frames that happen to be all positive or empty, so its colours don't flicker between scales.
  const signedViews = useRef(new Set<string>());
  const fixed = store.hello?.manifest.frames.find((f) => f.view === current)?.range;   // the Pi's own colour scale
  if (frame && current && (hasNegative(frame.data) || (fixed && fixed[0] < 0))) signedViews.current.add(current);
  const signed = !!frame && !!current && signedViews.current.has(current);
  const m = frame && signed ? Math.max(1e-6, maxAbs(frame.data)) : 1;
  const colormap = signed ? 'diverge' : heatmap.colormap ?? 'viridis';
  const range = fixed ?? (signed ? ([-(m <= 1 ? 1 : m), m <= 1 ? 1 : m] as [number, number]) : heatmap.range ?? 'auto');

  return ui((
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 6 }}>
      {views.length > 1 && (
        <div className={s.viewTabs} role="tablist" aria-label="Switch radar map">
          {views.map((v) => (
            <button key={v} type="button" role="tab" aria-selected={v === current} className={s.viewTab}
              data-active={v === current ? '' : undefined} onClick={() => setPicked(v)}>
              {viewTitle(store, v)}
            </button>
          ))}
        </div>
      )}
      <HeatmapCanvas
        data={frame?.data ?? null}
        shape={frame?.shape ?? null}
        xAxis={frame?.axes?.x}
        yAxis={frame?.axes?.y}
        unit={frame?.unit}
        onHover={setHover}
        {...heatmap}
        colormap={colormap}
        range={range}
        style={{ flex: 1, ...heatmap.style }}
      />
      {showReadout && (
        <div className="num" style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {frame ? `${frame.view} · ${frame.shape[0]}×${frame.shape[1]} · #${frame.frameIndex ?? frame.seq}` : 'waiting for frames'}
          {hover && ` · r${hover.row} c${hover.col} = ${hover.value.toFixed(2)}${frame?.unit ? ' ' + frame.unit : ''}`}
        </div>
      )}
    </div>
  ));
}
