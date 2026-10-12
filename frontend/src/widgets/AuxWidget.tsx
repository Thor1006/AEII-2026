import { useI18n } from '../i18n/I18n.tsx';
import type { TimeSeriesChartProps } from '../components/TimeSeriesChart.tsx';
import { TimeSeriesChart } from '../components/TimeSeriesChart.tsx';
import { auxInfo, auxKeys } from '../state/describe.ts';
import { useSensorStore } from '../state/SensorContext.tsx';

export interface AuxWidgetProps extends Partial<Omit<TimeSeriesChartProps, 'series'>> {
  /** Channels to plot. Default: what the Pi announces plus anything else that arrives. */
  channels?: string[];
  /** 'stacked': one chart per channel (own y-scale). 'overlay': all on one axis. */
  mode?: 'stacked' | 'overlay';
}

/** Ground-truth signals (sEMG, force, joint angle) from serial or the Pi. */
export function AuxWidget({ channels, mode = 'stacked', ...chart }: AuxWidgetProps) {
  const { ui } = useI18n();
  const store = useSensorStore();
  const keys = channels ?? auxKeys(store);
  const series = keys.map((key, i) => {
    const { label, unit } = auxInfo(store, key);
    return {
      key,
      label: unit ? `${label} (${unit})` : label,
      color: `var(--series-${((i + 3) % 6) + 1})`,
      points: store.aux.get(key)?.toArray() ?? [],
    };
  });
  if (!series.length) return ui(<div style={{ color: 'var(--text-muted)' }}>No reference signals. Plug in the Arduino (sEMG / force) to see them here.</div>);
  if (mode === 'overlay') return ui(<TimeSeriesChart series={series} windowMs={15_000} {...chart} />);

  // Charts share the time window (newest sample), so they stay aligned.
  return ui((
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, height: '100%' }}>
      {series.map((sr) =>
        sr.points.length ? (
          <TimeSeriesChart key={sr.key} series={[sr]} windowMs={15_000} style={{ flex: 1, minHeight: 90 }} {...chart} />
        ) : (
          <div key={sr.key} style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {sr.label}: no data
          </div>
        ),
      )}
    </div>
  ));
}
