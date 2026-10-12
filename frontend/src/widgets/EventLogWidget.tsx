import type { EventListProps } from '../components/EventList.tsx';
import { EventList } from '../components/EventList.tsx';
import { eventTones } from '../config/defaults.ts';
import { useSensorStore } from '../state/SensorContext.tsx';

export interface EventLogWidgetProps extends Partial<Omit<EventListProps, 'events'>> {
  /** Only these kinds. Default: everything except rep_start. */
  kinds?: string[];
  limit?: number;
}

export function EventLogWidget({ kinds, limit = 50, ...list }: EventLogWidgetProps) {
  const store = useSensorStore();
  const events = store.events
    .toArray()
    .filter((e) => (kinds ? kinds.includes(e.kind) : e.kind !== 'rep_start'))
    .slice(-limit)
    .reverse();
  return <EventList events={events} tones={eventTones} {...list} style={{ maxHeight: 400, ...list.style }} />;
}
