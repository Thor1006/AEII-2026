import { useI18n } from '../i18n/I18n.tsx';
import { useState } from 'react';
import type { HeatmapCanvasProps } from '../components/HeatmapCanvas.tsx';
import { HeatmapCanvas } from '../components/HeatmapCanvas.tsx';
import { useSensorStore } from '../state/SensorContext.tsx';

export interface RadarWidgetProps extends Partial<Omit<HeatmapCanvasProps, 'data' | 'shape'>> {
  /** Which frame view to show. Default: the first one received. */
  view?: string;
  showReadout?: boolean;
}

/** Live radar map from the latest frame of one view. */
export function RadarWidget({ view, showReadout = true, ...heatmap }: RadarWidgetProps) {
  const { ui } = useI18n();
  const store = useSensorStore();
  const [hover, setHover] = useState<{ row: number; col: number; value: number } | null>(null);
  const frame = view ? store.frames.get(view) : store.frames.values().next().value;

  return ui((
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 6 }}>
      <HeatmapCanvas
        data={frame?.data ?? null}
        shape={frame?.shape ?? null}
        xAxis={frame?.axes?.x}
        yAxis={frame?.axes?.y}
        unit={frame?.unit}
        onHover={setHover}
        {...heatmap}
        style={{ flex: 1, ...heatmap.style }}
      />
      {showReadout && (
        <div className="num" style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {frame ? `${frame.view} · ${frame.shape[0]}×${frame.shape[1]} · #${frame.frameIndex ?? frame.seq}` : 'waiting for frames'}
          {hover && ` · r${hover.row} c${hover.col} = ${hover.value.toFixed(1)}${frame?.unit ?? ''}`}
        </div>
      )}
    </div>
  ));
}
