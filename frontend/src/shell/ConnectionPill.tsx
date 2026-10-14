import { useI18n } from '../i18n/I18n.tsx';
import { displayAddress } from '../lib/address.ts';
import { bytes } from '../lib/format.ts';
import { ReplaySource } from '../sensor/sources/ReplaySource.ts';
import { WebSocketSource } from '../sensor/sources/WebSocketSource.ts';
import { linkQuality } from '../state/describe.ts';
import { useNow, useSensor, useSensorStore } from '../state/SensorContext.tsx';
import s from './shell.module.css';

/** "KIT-01 · Signal good". Click for details and to disconnect. */
export function ConnectionPill() {
  const { ui } = useI18n();
  const { source, state, disconnect } = useSensor();
  const store = useSensorStore();
  const now = useNow();
  if (!source) return null;

  const { quality, reasons } = linkQuality(store, now);
  const name =
    store.hello?.device.name ??
    (source instanceof WebSocketSource ? displayAddress(source.url) : source instanceof ReplaySource ? source.label : source.label);
  const live = state === 'open';
  const word =
    state === 'reconnecting' ? 'Reconnecting…' : state === 'connecting' ? 'Connecting…' : !live ? 'Disconnected' : `Signal ${quality}`;
  const tone = !live ? (state === 'reconnecting' || state === 'connecting' ? 'warn' : 'bad') : quality === 'good' ? 'good' : quality === 'fair' ? 'warn' : 'bad';
  const { stats } = store;
  const total = stats.received + stats.dropped;

  return ui((
    <details className={s.pill} data-popup>
      <summary data-tone={tone}>
        <span className={s.pillDot} />
        <span className={s.pillName}>{name}</span>
        <span className={s.pillWord}>{word}</span>
      </summary>
      <div className={s.pillPanel}>
        {live && (reasons.length ? (
          <ul className={s.reasons}>
            {reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        ) : (
          <p>Everything looks fine.</p>
        ))}
        <dl className={s.mini}>
          <div>
            <dt>Radar</dt>
            <dd>{stats.fps.toFixed(1)} frames/s</dd>
          </div>
          <div>
            <dt>Data</dt>
            <dd>{bytes(stats.bytesPerSec)}/s</dd>
          </div>
          <div>
            <dt>Lost</dt>
            <dd>{total ? ((stats.dropped / total) * 100).toFixed(1) : '0.0'}%</dd>
          </div>
          {stats.rttMs !== null && (
            <div>
              <dt>Delay</dt>
              <dd>{stats.rttMs.toFixed(0)} ms</dd>
            </div>
          )}
        </dl>
        <button type="button" onClick={disconnect}>
          Disconnect · change source
        </button>
      </div>
    </details>
  ));
}
