import { useI18n } from '../i18n/I18n.tsx';
import type { ScoreGaugeProps } from '../components/ScoreGauge.tsx';
import { ScoreGauge } from '../components/ScoreGauge.tsx';
import type { ScoreDef } from '../config/defaults.ts';
import { humanize } from '../lib/format.ts';
import { scoreDefs } from '../state/describe.ts';
import { useSensorStore } from '../state/SensorContext.tsx';

export interface ScoresWidgetProps {
  /** Override the scores shown. Default: what the Pi announces, else config/defaults.ts. */
  defs?: ScoreDef[];
  /** Also show score keys that arrive but aren't in `defs`. */
  showUnknown?: boolean;
  /** Show "lower is better" / "higher is better" under each gauge. */
  showDirection?: boolean;
  gauge?: Partial<ScoreGaugeProps>;
}

/** One gauge per model score (fatigue, quality, compensation, ...). */
export function ScoresWidget({ defs, showUnknown = true, showDirection = true, gauge }: ScoresWidgetProps) {
  const { ui } = useI18n();
  const store = useSensorStore();
  const base = defs ?? scoreDefs(store);
  const known = new Set(base.map((d) => d.key));
  const all: ScoreDef[] = [
    ...base,
    ...(showUnknown
      ? [...store.scores.keys()].filter((k) => !known.has(k)).map((k) => ({ key: k, label: humanize(k), higherIsWorse: true }))
      : []),
  ];
  return ui((
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: 12 }}>
      {all.map((d) => {
        const last = store.scores.get(d.key)?.last();
        return (
          <ScoreGauge
            key={d.key}
            label={d.label}
            value={last?.v ?? null}
            confidence={last?.c}
            higherIsWorse={d.higherIsWorse}
            thresholds={d.thresholds}
            footer={
              showDirection && (
                <div style={{ fontSize: 11, color: 'var(--chart-text)' }} title={d.description}>
                  {d.higherIsWorse ? 'lower is better' : 'higher is better'}
                </div>
              )
            }
            {...gauge}
          />
        );
      })}
    </div>
  ));
}
