import type { ReactNode } from 'react';
import { displayAddress } from '../lib/address.ts';
import { WebSocketSource } from '../sensor/sources/WebSocketSource.ts';
import type { SensorSource, SourceState } from '../sensor/SensorSource.ts';
import s from './StartScreen.module.css';

export interface ConnectionHelpProps {
  source: SensorSource;
  state: SourceState;
  error?: string;
  /** Compact list for the in-dashboard "connection lost" banner. */
  compact?: boolean;
}

/** Plain-language checklist for "can't reach the Pi". */
export function piChecklist(address: string): { title: string; body: ReactNode; urgent?: boolean }[] {
  const items: { title: string; body: ReactNode; urgent?: boolean }[] = [];
  if (location.protocol === 'https:') {
    items.push({
      urgent: true,
      title: 'This page was opened with https',
      body: (
        <>
          Browsers block the Pi’s connection from https pages. Open{' '}
          <a href={`http://${address.replace(/:\d+$/, '')}:8080`}>the Pi’s own page over http</a> instead.
        </>
      ),
    });
  }
  items.push(
    { title: 'Is the Pi switched on and on the same Wi-Fi?', body: 'This phone or laptop must be on the same network as the kit. Guest Wi-Fi often blocks devices from seeing each other.' },
    {
      title: 'Is the bridge running?',
      body: (
        <>
          On the Pi, run <code>sudo systemctl status truerehab-bridge</code>. It should say <em>active (running)</em>.
        </>
      ),
    },
    {
      title: 'Is the address right?',
      body: (
        <>
          Names ending in <code>.local</code> don’t work on some Android phones and networks. Try the Pi’s IP address instead (on the Pi: <code>hostname -I</code>).
        </>
      ),
    },
  );
  return items;
}

export function ConnectionHelp({ source, state, error, compact }: ConnectionHelpProps) {
  if (!(source instanceof WebSocketSource)) {
    return <p className={state === 'error' ? s.error : s.muted}>{state === 'error' ? (error ?? 'Could not open this source.') : 'Opening…'}</p>;
  }
  const address = displayAddress(source.url);
  const items = piChecklist(address);
  const shown = compact ? items.filter((i) => !i.urgent).slice(0, 3) : items;
  return (
    <ol className={s.checklist}>
      {shown.map((i) => (
        <li key={i.title} data-urgent={i.urgent || undefined}>
          <strong>{i.title}</strong>
          <span>{i.body}</span>
        </li>
      ))}
    </ol>
  );
}
