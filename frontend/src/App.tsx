import type { ComponentType, CSSProperties } from 'react';
import { useEffect, useState } from 'react';
import { Panel } from './components/Panel.tsx';
import type { Layout, PanelConfig } from './dashboard.config.ts';
import { layouts as defaultLayouts } from './dashboard.config.ts';
import { detectAutoConnect, rememberAddress } from './lib/address.ts';
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
      if (found && !cancelled) void connect(new WebSocketSource({ url: found.url }));
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
        <div className={s.brand}>
          <svg className={s.mark} viewBox="0 0 36 36" aria-hidden>
            <rect width="36" height="36" rx="10" fill="currentColor" />
            <g fill="var(--bg)" transform="translate(18 18) scale(0.00822 -0.00822) translate(-1247.25 -710.75)">
            <path transform="translate(0 0)" d="M616 -19.5Q545 -19.5 505 22Q465 63.5 465 138V1193H166.5Q105.5 1193 67.8 1226.2Q30 1259.5 30 1318Q30 1376.5 67.5 1409.8Q105 1443 166.5 1443H1065.5Q1127.5 1443 1164.8 1409.8Q1202 1376.5 1202 1318Q1202 1259.5 1164.2 1226.2Q1126.5 1193 1065.5 1193H767V138Q767 63.5 727 22Q687 -19.5 616 -19.5Z" />
            <path transform="translate(1232 0)" d="M271 -21.5Q200.5 -21.5 160.2 20.2Q120 62 120 136V1285.5Q120 1360.5 160 1401.8Q200 1443 271 1443H711Q877 1443 993.5 1387.2Q1110 1331.5 1171.2 1228.5Q1232.5 1125.5 1232.5 983Q1232.5 847.5 1168.5 739.8Q1104.5 632 985 580.5L1192.5 221Q1212 188.5 1218.2 166Q1224.5 143.5 1224.5 117Q1224.5 57 1181.5 17.8Q1138.5 -21.5 1073 -21.5Q1036.5 -21.5 1011.2 -11.2Q986 -1 964.8 24Q943.5 49 918.5 92.5L679 527.5Q679 527.5 679 527.5Q679 527.5 679 527.5H422V136Q422 62 382 20.2Q342 -21.5 271 -21.5ZM422 747H682Q796 747 859.5 808Q923 869 923 976.5Q923 1081.5 857.2 1144Q791.5 1206.5 678.5 1206.5H422Z" />
            </g>
          </svg>
          <div>
            <h1>{title}</h1>
            <p>Contactless rehab monitoring</p>
          </div>
        </div>
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
