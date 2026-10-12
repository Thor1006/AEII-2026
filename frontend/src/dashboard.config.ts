/**
 * Dashboard layouts. Add, remove or reorder panels here. `props` is type-checked
 * against the widget, so the editor autocompletes valid options.
 *
 * Grid is 12 columns; `span` = columns, `rows` = row height multiples. Narrow screens stack everything.
 */
import { panelHelp } from './config/defaults.ts';
import type { WidgetName, WidgetProps } from './widgets/index.ts';

type PanelFor<K extends WidgetName> = {
  id: string;
  widget: K;
  title?: string;
  /** Plain-language explanation behind the ⓘ button. */
  info?: string;
  span?: number;
  rows?: number;
  props?: WidgetProps<K>;
};

export type PanelConfig = { [K in WidgetName]: PanelFor<K> }[WidgetName];

export interface Layout {
  key: string;
  label: string;
  /** Tooltip on the view switch. */
  description: string;
  panels: PanelConfig[];
}

export const layouts: Layout[] = [
  {
    key: 'session',
    label: 'Session',
    description: 'What a patient or physiotherapist needs during the exercise',
    panels: [
      { id: 'rec', widget: 'recommendation', title: 'What to do now', info: panelHelp.recommendation, span: 8 },
      { id: 'reps', widget: 'reps', title: 'Reps', info: panelHelp.reps, span: 4 },
      { id: 'scores', widget: 'scores', title: 'How it’s going', info: panelHelp.scores, span: 6 },
      { id: 'trend', widget: 'scoreTrend', title: 'Last minute', info: panelHelp.trend, span: 6, props: { windowMs: 60_000, thresholds: [{ value: 0.7 }] } },
    ],
  },
  {
    key: 'technical',
    label: 'Technical',
    description: 'Radar map, reference signals and connection health, for the team',
    panels: [
      { id: 'radar', widget: 'radar', title: 'Radar map', info: panelHelp.radar, span: 6, rows: 2, props: { colormap: 'viridis' } },
      { id: 'health', widget: 'health', title: 'Data streams', info: panelHelp.health, span: 3, rows: 2 },
      { id: 'link', widget: 'link', title: 'Connection', info: panelHelp.link, span: 3, rows: 2 },
      { id: 'aux', widget: 'aux', title: 'Reference signals (sEMG · force · angle)', info: panelHelp.aux, span: 7, rows: 2 },
      { id: 'events', widget: 'events', title: 'Event log', info: panelHelp.events, span: 5, rows: 2 },
      { id: 'scores', widget: 'scores', title: 'Scores', info: panelHelp.scores, span: 5 },
      { id: 'trend', widget: 'scoreTrend', title: 'Score trend', info: panelHelp.trend, span: 7, props: { windowMs: 60_000, showConfidence: true } },
    ],
  },
];

/** Source connected on page load when nothing else applies. null = show the start screen. */
export const initialSource: { kind: string; values: Record<string, string | number> } | null = null;
