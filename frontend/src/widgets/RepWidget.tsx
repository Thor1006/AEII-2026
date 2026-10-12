import { useI18n } from '../i18n/I18n.tsx';
import { Stat } from '../components/Stat.tsx';
import { useSensorStore } from '../state/SensorContext.tsx';

export interface RepWidgetProps {
  /** Target reps when no session sets one. */
  target?: number;
}

/** Rep count and range of motion from rep_end events in the current session. */
export function RepWidget({ target }: RepWidgetProps) {
  const { ui } = useI18n();
  const store = useSensorStore();
  const reps = store.sessionEvents('rep_end');
  const roms = reps.map((e) => e.data?.romDeg).filter((x): x is number => typeof x === 'number');
  const lastRom = roms[roms.length - 1];
  const firstRom = roms[0];
  const romDrop = firstRom && lastRom !== undefined ? (1 - lastRom / firstRom) * 100 : null;
  const goal = store.session?.targetReps ?? target;
  const done = goal !== undefined && reps.length >= goal;

  return ui((
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Stat size="lg" label={done ? 'Target reached' : 'Reps'} value={reps.length} unit={goal ? `/ ${goal}` : undefined} tone={done ? 'good' : undefined} />
      {goal !== undefined && (
        <div style={{ height: 6, borderRadius: 3, background: 'var(--surface-2)', overflow: 'hidden' }} aria-hidden>
          <div style={{ width: `${Math.min(100, (reps.length / goal) * 100)}%`, height: '100%', background: 'var(--accent)', transition: 'width 300ms' }} />
        </div>
      )}
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
        <Stat label="Range of motion, last rep" value={lastRom !== undefined ? lastRom.toFixed(0) : '–'} unit="°" />
        <Stat
          label="Change since first rep"
          value={romDrop === null ? '–' : `${romDrop > 0 ? '−' : '+'}${Math.abs(romDrop).toFixed(0)}`}
          unit="%"
          tone={romDrop !== null && romDrop > 20 ? 'warn' : undefined}
        />
      </div>
    </div>
  ));
}
