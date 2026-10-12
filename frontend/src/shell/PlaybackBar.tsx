import { isPlayback } from '../sensor/SensorSource.ts';
import { useSensor, useSensorStore } from '../state/SensorContext.tsx';
import s from './shell.module.css';

const SPEEDS = [0.25, 0.5, 1, 2, 4];

/** Shown only when the active source supports playback (replay). */
export function PlaybackBar() {
  const { source } = useSensor();
  useSensorStore(); // re-render as playback advances
  if (!isPlayback(source)) return null;
  return (
    <div className={s.playback}>
      <button onClick={() => (source.playing ? source.pause() : source.play())}>{source.playing ? 'Pause' : 'Play'}</button>
      <button onClick={() => source.restart()}>Restart</button>
      <select aria-label="Speed" value={source.speed} onChange={(e) => source.setSpeed(Number(e.target.value))}>
        {SPEEDS.map((x) => (
          <option key={x} value={x}>
            {x}×
          </option>
        ))}
      </select>
      <progress value={source.progress} max={1} />
    </div>
  );
}
