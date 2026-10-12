import { useI18n } from '../i18n/I18n.tsx';
import type { TimeSeriesChartProps } from '../components/TimeSeriesChart.tsx';
import { TimeSeriesChart } from '../components/TimeSeriesChart.tsx';
import type { ScoreDef } from '../config/defaults.ts';
import { pct } from '../lib/format.ts';
import { scoreDefs } from '../state/describe.ts';
import { useSensorStore } from '../state/SensorContext.tsx';

export interface ScoreTrendWidgetProps extends Partial<Omit<TimeSeriesChartProps, 'series'>> {
  defs?: ScoreDef[];
  showConfidence?: boolean;
}

/** Score history over time. Where the temporal "predict the next reps" view will go. */
export function ScoreTrendWidget({ defs, showConfidence = false, ...chart }: ScoreTrendWidgetProps) {
  const { ui } = useI18n();
  const store = useSensorStore();
  const series = (defs ?? scoreDefs(store)).map((d) => ({
    key: d.key,
    label: d.label,
    color: d.color,
    showConfidence,
    points: store.scores.get(d.key)?.toArray() ?? [],
  }));
  return ui(<TimeSeriesChart series={series} yRange={[0, 1]} formatY={pct} windowMs={60_000} {...chart} />);
}
