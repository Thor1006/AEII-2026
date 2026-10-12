import type { ComponentType, CSSProperties } from 'react';
import { useEffect, useState } from 'react';
import { Logo } from './components/Logo.tsx';
import { Panel } from './components/Panel.tsx';
import type { Layout, PanelConfig } from './dashboard.config.ts';
import { layouts as defaultLayouts } from './dashboard.config.ts';
import { detectAutoConnect, rememberAddress } from './lib/address.ts';
import { getKey } from './lib/keystore.ts';
import { WebSocketSource } from './sensor/sources/WebSocketSource.ts';
import { useSensor } from './state/SensorContext.tsx';
import { Banners } from './shell/Banners.tsx';
import { ConnectionPill } from './shell/ConnectionPill.tsx';
import { DeviceStrip } from './shell/DeviceStrip.tsx';
import { PlaybackBar } from './shell/PlaybackBar.tsx';
import { SessionBar } from './shell/SessionBar.tsx';
import { SessionRecorder } from './shell/SessionRecorder.tsx';
import { StartScreen } from './shell/StartScreen.tsx';
import { ThemeToggle } from './shell/ThemeToggle.tsx';
import { ViewToggle } from './shell/ViewToggle.tsx';
import { widgets } from './widgets/index.ts';
import s from './App.module.css';

export interface AppProps {
  layouts?: Layout[];
  title?: string;
  /** Try ?pi= and the serving bridge on load. */
  autoConnect?: boolean;
}

const VIEW_KEY = 'trf-view';

export function App({ layouts = defaultLayouts, title = 'TrueRehab-RF', autoConnect = true }: AppProps) {
  const { source, state, connect } = useSensor();
  const [view, setView] = useState(() => {
    try {
      return localStorage.getItem(VIEW_KEY) ?? layouts[0].key;
    } catch {
      return layouts[0].key;
    }
  });
  const layout = layouts.find((l) => l.key === view) ?? layouts[0];

  // Opened from the Pi (or with ?pi=): connect without asking.
  useEffect(() => {
    if (!autoConnect) return;
    let cancelled = false;
    void detectAutoConnect().then((found) => {
      if (found && !cancelled) void connect(new WebSocketSource({ url: found.url, key: getKey(found.url) }));
    });
    return () => {
      cancelled = true;
    };
  }, [autoConnect, connect]);

  // Remember Pis that worked, for the "Recent" list.
  useEffect(() => {
    if (state === 'open' && source instanceof WebSocketSource) rememberAddress(source.url);
  }, [state, source]);

  const changeView = (k: string) => {
    setView(k);
    try {
      localStorage.setItem(VIEW_KEY, k);
    } catch {
      /* ignore */
    }
  };

  const everOpened = source instanceof WebSocketSource ? source.everOpened : state === 'open';
  const showStart = !source || state === 'closed' || state === 'idle' || (!everOpened && state !== 'open');

  return (
    <div className={s.app}>
      <header className={s.header}>
        <a className={s.brand} href="#/" aria-label="TrueRehab-RF home">
          <Logo className={s.mark} />
          <div>
            <h1>{title}</h1>
            <p>Contactless rehab monitoring</p>
          </div>
        </a>
        {!showStart && (
          <ViewToggle options={layouts.map((l) => ({ key: l.key, label: l.label, title: l.description }))} value={layout.key} onChange={changeView} />
        )}
        <div className={s.controls}>
          {!showStart && <ConnectionPill />}
          <ThemeToggle />
        </div>
      </header>

      {showStart ? (
        <StartScreen />
      ) : (
        <>
          <Banners />
          <SessionBar />
          <div className={s.subbar}>
            <DeviceStrip />
            <div className={s.subbarRight}>
              <PlaybackBar />
              <SessionRecorder />
            </div>
          </div>
          <main className={s.grid}>
            {layout.panels.map((p) => (
              <Panel key={`${layout.key}-${p.id}`} title={p.title} info={p.info} style={{ '--span': p.span ?? 4, '--rows': p.rows ?? 1 } as CSSProperties} className={s.cell}>
                <WidgetSlot panel={p} />
              </Panel>
            ))}
          </main>
        </>
      )}
    </div>
  );
}

function WidgetSlot({ panel }: { panel: PanelConfig }) {
  // The config's discriminated union guarantees props match the widget.
  const Widget = widgets[panel.widget] as ComponentType<Record<string, unknown>>;
  return <Widget {...(panel.props ?? {})} />;
}
