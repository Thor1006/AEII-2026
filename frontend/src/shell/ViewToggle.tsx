import { useI18n } from '../i18n/I18n.tsx';
import s from './shell.module.css';

export interface ViewOption<K extends string> {
  key: K;
  label: string;
  title?: string;
}

/** Segmented control for switching dashboard views. */
export function ViewToggle<K extends string>({ options, value, onChange }: { options: ViewOption<K>[]; value: K; onChange: (k: K) => void }) {
  const { ui } = useI18n();
  return ui((
    <div className={s.segmented} role="radiogroup" aria-label="View">
      {options.map((o) => (
        <button key={o.key} type="button" role="radio" aria-checked={value === o.key} title={o.title} onClick={() => onChange(o.key)}>
          {o.label}
        </button>
      ))}
    </div>
  ));
}
