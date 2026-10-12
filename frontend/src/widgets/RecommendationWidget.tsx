import { useI18n } from '../i18n/I18n.tsx';
import type { RecommendationCardProps } from '../components/RecommendationCard.tsx';
import { RecommendationCard } from '../components/RecommendationCard.tsx';
import { actionStyles } from '../state/describe.ts';
import { useSensorStore } from '../state/SensorContext.tsx';

export type RecommendationWidgetProps = Partial<Omit<RecommendationCardProps, 'action'>>;

/** Latest `recommendation` event. Labels come from the Pi's manifest. */
export function RecommendationWidget(props: RecommendationWidgetProps) {
  const { ui } = useI18n();
  const store = useSensorStore();
  const recs = store.eventsOfKind('recommendation');
  const last = recs[recs.length - 1];
  return ui((
    <RecommendationCard
      action={last ? String(last.data?.action ?? '') || null : null}
      reason={typeof last?.data?.reason === 'string' ? last.data.reason : undefined}
      at={last?.t}
      styles={actionStyles(store)}
      emptyText="Waiting for the first rep. A suggestion appears after each repetition."
      {...props}
    />
  ));
}
