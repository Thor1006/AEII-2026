import { useI18n } from '../i18n/I18n.tsx';
import type { CSSProperties, ReactNode } from 'react';
import { useId, useState } from 'react';
import { cx } from '../lib/format.ts';
import s from './Panel.module.css';

export interface PanelProps {
  title?: ReactNode;
  /** Plain-language explanation, shown by the ⓘ button. */
  info?: ReactNode;
  /** Right side of the header: buttons, badges, ... */
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  /** Remove body padding (for edge-to-edge canvases). */
  flush?: boolean;
}

/** Card shell used by every dashboard panel. */
export function Panel({ title, info, actions, children, className, style, flush }: PanelProps) {
  const { ui } = useI18n();
  const [showInfo, setShowInfo] = useState(false);
  const infoId = useId();
  return ui((
    <section className={cx(s.panel, className)} style={style}>
      {(title || actions || info) && (
        <header className={s.header}>
          <h2 className={s.title}>{title}</h2>
          <div className={s.actions}>
            {actions}
            {info && (
              <button
                type="button"
                className={s.infoBtn}
                aria-expanded={showInfo}
                aria-controls={infoId}
                aria-label={showInfo ? 'Hide explanation' : 'What is this?'}
                title="What is this?"
                onClick={() => setShowInfo((v) => !v)}
              >
                {showInfo ? '×' : 'i'}
              </button>
            )}
          </div>
        </header>
      )}
      {info && (
        <p id={infoId} className={s.info} data-motion="reveal" hidden={!showInfo} aria-hidden={!showInfo}>
          {info}
        </p>
      )}
      <div className={cx(s.body, flush && s.flush)}>{children}</div>
    </section>
  ));
}
