import { useI18n } from '../i18n/I18n.tsx';
import { displayAddress } from '../lib/address.ts';
import { WebSocketSource } from '../sensor/sources/WebSocketSource.ts';
import { protocolWarning } from '../state/describe.ts';
import { useNow, useSensor, useSensorStore } from '../state/SensorContext.tsx';
import { ConnectionHelp } from './ConnectionHelp.tsx';
import s from './shell.module.css';

/** One-line notices above the dashboard: demo data, lost connection, version problems. */
export function Banners() {
  const { ui } = useI18n();
  const { source, state, error } = useSensor();
  const store = useSensorStore();
  const now = useNow();
  const isPi = source instanceof WebSocketSource;

  const lost = isPi && source.everOpened && state === 'reconnecting';
  const proto = protocolWarning(store);
  const connectedMs = store.stats.firstRecvT ? now - store.stats.firstRecvT : 0;
  const noHello = isPi && state === 'open' && !store.hello && connectedMs > 3000;

  return ui((
    <>
      {lost && (
        <div className={s.banner} data-tone="bad" role="alert">
          <div>
            <strong>Lost connection to {store.hello?.device.name ?? displayAddress(source.url)}.</strong> Reconnecting… The screen is paused until data comes back.
          </div>
          <details>
            <summary>What to check</summary>
            <ConnectionHelp source={source} state={state} error={error} compact />
          </details>
        </div>
      )}
      {store.synthetic && (
        <div className={s.banner} data-tone="warn" role="note">
          <strong>Demo data.</strong> Everything on this screen is made up. It is not a measurement.
        </div>
      )}
      {isPi && state === 'open' && source.authMode === 'none' && (
        <div className={s.banner} data-tone="warn" role="note">
          <strong>This kit isn’t protected with a key.</strong> Anyone on the same Wi-Fi can see the data and start or stop sessions. Set a key on the kit to fix this.
        </div>
      )}
      {proto && (
        <div className={s.banner} data-tone="bad" role="alert">
          {proto}
        </div>
      )}
      {noHello && (
        <div className={s.banner} data-tone="info" role="note">
          This Pi didn’t describe itself (older bridge, protocol 1.0). Labels use the defaults, and the health check only lists what arrives. Update the bridge to fix this.
        </div>
      )}
    </>
  ));
}
