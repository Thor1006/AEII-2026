import { useI18n } from '../i18n/I18n.tsx';
import { useSensorStore } from '../state/SensorContext.tsx';
import s from './shell.module.css';

const MARK = { ok: '✓', missing: '✕', error: '!', off: '–' } as const;

/** "Radar ✓ · Arduino ✕ Not plugged in · AI model ✓", from the Pi's heartbeat. */
export function DeviceStrip() {
  const { ui } = useI18n();
  const store = useSensorStore();
  const devices = Object.entries(store.devices);
  if (!devices.length) return null;
  return ui((
    <ul className={s.devices} aria-label="Devices">
      {devices.map(([id, d]) => (
        <li key={id} data-state={d.state} title={d.message}>
          <span className={s.devMark} aria-hidden>
            {MARK[d.state] ?? '?'}
          </span>
          {d.label ?? id}
          {d.state !== 'ok' && d.message && <span className={s.devMsg}>{d.message}</span>}
          <span className="sr-only">{d.state}</span>
        </li>
      ))}
    </ul>
  ));
}
