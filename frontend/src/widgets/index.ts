/**
 * Connected widgets: read the SensorStore and render presentational components.
 * Add a widget here and it becomes available to dashboard.config.ts.
 */
import type { ComponentProps, ComponentType } from 'react';
import { AuxWidget } from './AuxWidget.tsx';
import { EventLogWidget } from './EventLogWidget.tsx';
import { LinkWidget } from './LinkWidget.tsx';
import { StreamHealthWidget } from './StreamHealthWidget.tsx';
import { RadarWidget } from './RadarWidget.tsx';
import { RecommendationWidget } from './RecommendationWidget.tsx';
import { RepWidget } from './RepWidget.tsx';
import { ScoresWidget } from './ScoresWidget.tsx';
import { ScoreTrendWidget } from './ScoreTrendWidget.tsx';

export const widgets = {
  radar: RadarWidget,
  scores: ScoresWidget,
  scoreTrend: ScoreTrendWidget,
  recommendation: RecommendationWidget,
  reps: RepWidget,
  events: EventLogWidget,
  aux: AuxWidget,
  health: StreamHealthWidget,
  link: LinkWidget,
} satisfies Record<string, ComponentType<never>>;

export type WidgetName = keyof typeof widgets;
export type WidgetProps<K extends WidgetName> = ComponentProps<(typeof widgets)[K]>;

export { AuxWidget, EventLogWidget, LinkWidget, RadarWidget, RecommendationWidget, RepWidget, ScoresWidget, ScoreTrendWidget, StreamHealthWidget };
