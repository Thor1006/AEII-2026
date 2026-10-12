import { useI18n } from '../i18n/I18n.tsx';
import { useEffect, useRef, useState } from 'react';
import { bytes } from '../lib/format.ts';
import { toJsonLine } from '../sensor/codec.ts';
import { useSensor } from '../state/SensorContext.tsx';
import s from './shell.module.css';

export interface SessionRecorderProps {
  /** Radar frames are large (~25 MB/min at 64×64, 20 fps). Turn off to record only scores/events/aux. */
  includeFrames?: boolean;
  filenamePrefix?: string;
}

/** Records the incoming stream to .ndjson, which the Replay source can play back. */
export function SessionRecorder({ includeFrames: initialFrames = true, filenamePrefix = 'session' }: SessionRecorderProps) {
  const { ui } = useI18n();
  const { store } = useSensor();
  const [recording, setRecording] = useState(false);
  const [includeFrames, setIncludeFrames] = useState(initialFrames);
  const [info, setInfo] = useState({ lines: 0, size: 0 });
  const lines = useRef<string[]>([]);
  const size = useRef(0);

  useEffect(() => {
    if (!recording) return;
    const unsub = store.subscribeRaw((msg) => {
      if (msg.type === 'frame' && !includeFrames) return;
      const line = toJsonLine(msg);
      lines.current.push(line);
      size.current += line.length + 1;
    });
    const timer = setInterval(() => setInfo({ lines: lines.current.length, size: size.current }), 500);
    return () => {
      unsub();
      clearInterval(timer);
    };
  }, [recording, includeFrames, store]);

  const start = () => {
    lines.current = [];
    size.current = 0;
    setInfo({ lines: 0, size: 0 });
    setRecording(true);
  };

  const stop = () => {
    setRecording(false);
    if (!lines.current.length) return;
    const blob = new Blob([lines.current.join('\n') + '\n'], { type: 'application/x-ndjson' });
    const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${filenamePrefix}-${stamp}.ndjson`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    lines.current = [];
  };

  return ui((
    <div className={s.recorder}>
      {recording ? (
        <>
          <span className={s.recDot} />
          <span className="num">
            {info.lines} msgs · {bytes(info.size)}
          </span>
          <button onClick={stop}>Stop &amp; save</button>
        </>
      ) : (
        <>
          <label className={s.check}>
            <input type="checkbox" checked={includeFrames} onChange={(e) => setIncludeFrames(e.target.checked)} />
            frames
          </label>
          <button onClick={start}>Record</button>
        </>
      )}
    </div>
  ));
}
