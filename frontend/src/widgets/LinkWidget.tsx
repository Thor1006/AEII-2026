import { useI18n } from '../i18n/I18n.tsx';
import { displayAddress } from '../lib/address.ts';
import { bytes } from '../lib/format.ts';
import { WebSocketSource } from '../sensor/sources/WebSocketSource.ts';
import { useNow, useSensor, useSensorStore } from '../state/SensorContext.tsx';
import s from './widgets.module.css';

/** Raw connection numbers for troubleshooting. */
export function LinkWidget() {
  const { ui } = useI18n();
  const { source } = useSensor();
  const store = useSensorStore();
  const now = useNow();
  const { stats, hello, status } = store;
  const total = stats.received + stats.dropped;
  const connectedS = stats.firstRecvT ? Math.round((now - stats.firstRecvT) / 1000) : null;

  const rows: [string, string][] = [
    ['Device', hello?.device.name ?? '–'],
    ['Kit', hello?.device.kitId ?? hello?.kitId ?? '–'],
    ['Address', source instanceof WebSocketSource ? displayAddress(source.url) : (source?.label ?? '–')],
    ['Protocol', hello?.protocol ?? '1.0 (no hello)'],
    ['Bridge version', hello?.device.bridgeVersion ?? '–'],
    ['Radar frames/s', `${stats.fps.toFixed(1)}${hello?.manifest.frames[0] ? ` of ${hello.manifest.frames[0].fps}` : ''}`],
    ['Data rate', `${bytes(stats.bytesPerSec)}/s`],
    ['Messages lost', `${stats.dropped} of ${total} (${total ? ((stats.dropped / total) * 100).toFixed(1) : '0.0'}%)`],
    ['Round trip', stats.rttMs === null ? '–' : `${stats.rttMs.toFixed(0)} ms`],
    ['Pi CPU temp', status?.cpuTempC === undefined ? '–' : `${status.cpuTempC.toFixed(0)} °C`],
    ['Viewers on this Pi', status?.clients === undefined ? '–' : String(status.clients)],
    ['Connected for', connectedS === null ? '–' : `${Math.floor(connectedS / 60)} min ${connectedS % 60} s`],
  ];
  return ui((
    <dl className={s.kv}>
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  ));
}
