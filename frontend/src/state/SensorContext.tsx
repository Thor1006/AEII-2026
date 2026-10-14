import type { ReactNode } from 'react';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { AckMessage, CommandName, SessionInfo } from '../sensor/protocol.ts';
import type { SensorSource, SourceState } from '../sensor/SensorSource.ts';
import { CommandError } from '../sensor/SensorSource.ts';
import { SensorStore } from './SensorStore.ts';

interface SensorContextValue {
  store: SensorStore;
  source: SensorSource | null;
  state: SourceState;
  error?: string;
  /** Replace the active source. Call from a click handler (Web Serial needs the gesture). */
  connect(source: SensorSource): Promise<void>;
  disconnect(): void;
  /** True if the active source accepts commands (Pi bridge, demo). */
  canCommand: boolean;
  /** Send a command to the Pi. Resolves with the ack; rejects if it can't be sent or times out. */
  sendCommand(name: CommandName, args?: Record<string, unknown>): Promise<AckMessage>;
}

const SensorContext = createContext<SensorContextValue | null>(null);

export interface SensorProviderProps {
  children: ReactNode;
  /** Pass your own store to share it or tune buffer sizes. */
  store?: SensorStore;
  /** Connected on mount, e.g. a mock for development. */
  initialSource?: () => SensorSource;
}

export function SensorProvider({ children, store: external, initialSource }: SensorProviderProps) {
  const store = useMemo(() => external ?? new SensorStore(), [external]);
  const [source, setSource] = useState<SensorSource | null>(null);
  const [state, setState] = useState<SourceState>('idle');
  const [error, setError] = useState<string>();
  const current = useRef<{ source: SensorSource; unsubs: (() => void)[] } | null>(null);

  const disconnect = useCallback(() => {
    if (!current.current) return;
    current.current.unsubs.forEach((u) => u());
    current.current.source.disconnect();
    current.current = null;
    setSource(null);
    setState('closed');
  }, []);

  const connect = useCallback(
    (next: SensorSource) => {
      // No awaits before next.connect(): keeps the user gesture for Web Serial.
      disconnect();
      store.reset();
      const unsubs = [
        next.onMessage((msg, meta) => store.ingest(msg, meta.bytes)),
        next.onState((s, err) => {
          setState(s);
          setError(err);
        }),
      ];
      if (next.onRtt) unsubs.push(next.onRtt((ms) => store.setRtt(ms)));
      if (next.onReset) unsubs.push(next.onReset(() => store.reset()));
      current.current = { source: next, unsubs };
      setSource(next);
      setState(next.state);
      return next.connect();
    },
    [disconnect, store],
  );

  const sendCommand = useCallback(
    async (name: CommandName, args?: Record<string, unknown>) => {
      const src = current.current?.source;
      if (!src?.command) throw new CommandError('This source can\u2019t receive commands');
      const ack = await src.command(name, args);
      const session = ack.result?.session as SessionInfo | undefined;
      if (ack.ok && session) store.setSession(session, name === 'session.start', ack.result?.reps);
      return ack;
    },
    [store],
  );

  useEffect(() => {
    if (initialSource) void connect(initialSource());
    return disconnect;
    // Mount only: initialSource is a factory, not a dependency.
  }, []);

  const value = useMemo(
    () => ({ store, source, state, error, connect, disconnect, sendCommand, canCommand: !!source?.command }),
    [store, source, state, error, connect, disconnect, sendCommand],
  );
  return <SensorContext.Provider value={value}>{children}</SensorContext.Provider>;
}

export function useSensor(): SensorContextValue {
  const ctx = useContext(SensorContext);
  if (!ctx) throw new Error('useSensor must be used inside <SensorProvider>');
  return ctx;
}

/**
 * Re-render at most once per animation frame while data arrives.
 * Returns the store so widgets can read what they need.
 */
export function useSensorStore(): SensorStore {
  const { store } = useSensor();
  const [, setTick] = useState(0);
  useEffect(() => {
    let raf = 0;
    const unsub = store.subscribe(() => {
      if (!raf) {
        raf = requestAnimationFrame(() => {
          raf = 0;
          setTick((t) => t + 1);
        });
      }
    });
    return () => {
      unsub();
      if (raf) cancelAnimationFrame(raf);
    };
  }, [store]);
  return store;
}

/** Re-render every `intervalMs` (for "last seen 5 s ago" displays that must update when data stops). */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}
