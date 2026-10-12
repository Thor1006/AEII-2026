import type { FormEvent } from 'react';
import { useState } from 'react';
import type { FieldValue, SourceDefinition } from '../sensor/sources/index.ts';
import { useSensor } from '../state/SensorContext.tsx';
import s from './StartScreen.module.css';

/** A connect form generated from a source definition's `fields`. Used for "More options". */
export function SourceForm({ def }: { def: SourceDefinition }) {
  const { connect } = useSensor();
  const [values, setValues] = useState<Record<string, FieldValue>>(() => Object.fromEntries(def.fields.map((f) => [f.name, f.default])));
  const [err, setErr] = useState<string>();
  const supported = def.isSupported?.() ?? true;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setErr(undefined);
    try {
      // Synchronous up to connect(): keeps the click's user gesture (Web Serial needs it).
      void connect(def.create(values));
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : String(ex));
    }
  };

  return (
    <form className={s.subForm} onSubmit={onSubmit}>
      <div className={s.subHead}>
        <strong>{def.label}</strong>
        <span>{def.description}</span>
      </div>
      {def.fields.map((f) => (
        <label key={f.name} className={s.field}>
          <span>
            {f.label}
            {f.help && <small> · {f.help}</small>}
          </span>
          {f.type === 'select' ? (
            <select value={String(values[f.name] ?? '')} onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}>
              {f.options?.map((o) => <option key={o}>{o}</option>)}
            </select>
          ) : f.type === 'file' ? (
            <input type="file" accept={f.accept} onChange={(e) => setValues({ ...values, [f.name]: e.target.files?.[0] })} />
          ) : (
            <input
              type={f.type}
              value={String(values[f.name] ?? '')}
              placeholder={f.placeholder}
              onChange={(e) => setValues({ ...values, [f.name]: f.type === 'number' ? Number(e.target.value) : e.target.value })}
            />
          )}
        </label>
      ))}
      <div className={s.row}>
        <button type="submit" disabled={supported !== true}>
          Connect
        </button>
        {supported !== true && <span className={s.error}>{supported}</span>}
        {err && <span className={s.error}>{err}</span>}
      </div>
    </form>
  );
}
