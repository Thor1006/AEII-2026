import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { languages, useI18n } from './I18n.tsx';
import type { Language } from './messages.ts';
import s from './LanguageSelector.module.css';

function Flag({ language }: { language: Language }) {
  return (
    <svg className={s.flag} width="18" height="12" viewBox="0 0 30 20" aria-hidden="true" focusable="false">
      {language === 'en' ? <>
        <path fill="#fff" d="M0 0h30v20H0z" />
        {Array.from({ length: 7 }, (_, row) => <rect key={row} y={row * 40 / 13} width="30" height={20 / 13} fill="#b22234" />)}
        <path fill="#3c3b6e" d="M0 0h12v10.77H0z" />
        {Array.from({ length: 9 }, (_, row) => Array.from({ length: row % 2 ? 5 : 6 }, (_, col) =>
          <path key={`${row}-${col}`} fill="#fff" d="M0-.48.14-.15.5-.15.22.07.32.42 0 .21-.32.42-.22.07-.5-.15-.14-.15Z" transform={`translate(${1 + col * 2 + (row % 2)}, ${.65 + row * 1.18})`} />
        ))}
      </> : language === 'th' ? <>
        <path fill="#a51931" d="M0 0h30v20H0z" />
        <path fill="#fff" d="M0 3.33h30v13.34H0z" />
        <path fill="#2d2a4a" d="M0 6.67h30v6.66H0z" />
      </> : language === 'ja' ? <>
        <path fill="#fff" d="M0 0h30v20H0z" />
        <circle cx="15" cy="10" r="6" fill="#bc002d" />
      </> : language === 'ko' ? <>
        <path fill="#fff" d="M0 0h30v20H0z" />
        <g transform="rotate(33.7 15 10)">
          <circle cx="15" cy="10" r="5" fill="#cd2e3a" />
          <path fill="#0047a0" d="M10 10a5 5 0 0 0 10 0a2.5 2.5 0 0 0-5 0a2.5 2.5 0 0 1-5 0Z" />
        </g>
        {[{ x: 6, y: 5, angle: -56.3, broken: [false, false, false] },
          { x: 24, y: 15, angle: -56.3, broken: [true, true, true] },
          { x: 24, y: 5, angle: 56.3, broken: [true, false, true] },
          { x: 6, y: 15, angle: 56.3, broken: [false, true, false] }].map((trigram,index) =>
          <g key={index} fill="#000" transform={`translate(${trigram.x} ${trigram.y}) rotate(${trigram.angle})`}>
            {trigram.broken.map((broken,row) => broken
              ? <path key={row} d={`M-2.5 ${row * 1.1 - 1.5}h2.1v.7h-2.1zM.4 ${row * 1.1 - 1.5}h2.1v.7H.4z`} />
              : <rect key={row} x="-2.5" y={row * 1.1 - 1.5} width="5" height=".7" />)}
          </g>)}
      </> : language === 'zh-CN' ? <>
        <path fill="#de2910" d="M0 0h30v20H0z" />
        <path fill="#ffde00" d="m5 2 1 3 3.2 0-2.6 1.9 1 3-2.6-1.9-2.6 1.9 1-3L.8 5H4Z" />
        {[{x:10,y:2.4,r:20},{x:12,y:4.5,r:45},{x:12,y:7.5,r:0},{x:10,y:9.6,r:20}].map((star,index) =>
          <path key={index} fill="#ffde00" d="M0-1.2.28-.37 1.14-.37.46.14.71.97 0 .46-.71.97-.46.14-1.14-.37-.28-.37Z" transform={`translate(${star.x} ${star.y}) rotate(${star.r})`} />)}
      </> : language === 'vi' ? <>
        <path fill="#da251d" d="M0 0h30v20H0z" />
        <path fill="#ff0" d="m15 4 1.8 4.4 4.7.3-3.7 3 1.2 4.6-4-2.6-4 2.6 1.2-4.6-3.7-3 4.7-.3Z" />
      </> : language === 'id' ? <>
        <path fill="#fff" d="M0 0h30v20H0z" />
        <path fill="#ff0000" d="M0 0h30v10H0z" />
      </> : language === 'fr' ? <>
        <path fill="#fff" d="M0 0h30v20H0z" />
        <path fill="#002395" d="M0 0h10v20H0z" />
        <path fill="#ed2939" d="M20 0h10v20H20z" />
      </> : language === 'es' ? <>
        <path fill="#aa151b" d="M0 0h30v20H0z" />
        <path fill="#f1bf00" d="M0 5h30v10H0z" />
        <path fill="#aa151b" stroke="#fff" strokeWidth=".3" d="M8.5 8h4v3.5a2 2 0 0 1-4 0Z" />
        <path fill="#f1bf00" d="M8.2 6.6 9 7.2l1.5-1 1.5 1 .8-.6-.3 1.6H8.5Z" />
        <path stroke="#aa151b" strokeWidth=".6" d="M7 8.5v4m7-4v4" />
      </> : <>
        <path fill="#de2910" d="M0 0h30v20H0z" />
        {Array.from({ length: 5 }, (_, petal) => <g key={petal} transform={`rotate(${petal * 72} 15 10)`}>
          <path fill="#fff" d="M15 10C12.1 8.8 11.9 5.1 15.4 4.2c-.6 1.1.9 1.5 1.3 2.9.3 1.3-.4 2.3-1.7 2.9Z" />
          <path fill="#de2910" d="m14.6 6.3.16.4.43.03-.33.27.1.42-.36-.23-.37.22.11-.41-.32-.28.42-.02Z" />
          <path d="M15 10c-1-.9-1.2-1.8-.6-2.7" stroke="#de2910" strokeWidth=".2" fill="none" />
        </g>)}
      </>}
    </svg>
  );
}

export function LanguageSelector() {
  const { language, setLanguage, t } = useI18n();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [menuOffset, setMenuOffset] = useState(0);
  const [menuMaxHeight, setMenuMaxHeight] = useState(450);
  const container = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const id = useId();
  const selected = languages.find((item) => item.code === language)!;

  useLayoutEffect(() => {
    if (!open) return;
    // Keep all language options reachable without letting the menu leave the viewport.
    const position = () => {
      if (!list.current || !container.current) return;
      const width = list.current.offsetWidth;
      const bounds = container.current.getBoundingClientRect();
      const naturalLeft = bounds.right - width;
      const left = Math.max(8, Math.min(naturalLeft, document.documentElement.clientWidth - width - 8));
      setMenuOffset(left - naturalLeft);
      setMenuMaxHeight(Math.max(44, Math.min(450, document.documentElement.clientHeight - bounds.bottom - 12)));
    };
    position();
    window.addEventListener('resize', position);
    return () => window.removeEventListener('resize', position);
  }, [open, language]);

  useLayoutEffect(() => {
    const menu = list.current;
    const option = menu?.children.item(active) as HTMLElement | null;
    if (!open || !menu || !option) return;
    // Scroll only the option list, never the page behind it.
    if (option.offsetTop < menu.scrollTop) menu.scrollTop = option.offsetTop;
    else if (option.offsetTop + option.offsetHeight > menu.scrollTop + menu.clientHeight)
      menu.scrollTop = option.offsetTop + option.offsetHeight - menu.clientHeight;
  }, [open, active, menuMaxHeight]);

  useEffect(() => {
    if (!open) return;
    list.current?.focus({ preventScroll: true });
    const dismiss = (event: PointerEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', dismiss);
    return () => document.removeEventListener('pointerdown', dismiss);
  }, [open]);

  function show() {
    setActive(languages.findIndex((item) => item.code === language));
    setOpen(true);
  }

  function choose(index: number) {
    setLanguage(languages[index].code);
    setOpen(false);
    trigger.current?.focus();
  }

  function handleKey(event: KeyboardEvent<HTMLDivElement>) {
    switch (event.key) {
      case 'ArrowDown': setActive((index) => (index + 1) % languages.length); break;
      case 'ArrowUp': setActive((index) => (index + languages.length - 1) % languages.length); break;
      case 'Home': setActive(0); break;
      case 'End': setActive(languages.length - 1); break;
      case 'Enter': case ' ': choose(active); break;
      case 'Escape': setOpen(false); trigger.current?.focus(); break;
      case 'Tab': setOpen(false); return;
      default: {
        const index = languages.findIndex((item) => item.name.toLocaleLowerCase().startsWith(event.key.toLocaleLowerCase()));
        if (event.key.length === 1 && index !== -1) setActive(index);
        return;
      }
    }
    event.preventDefault();
  }

  return (
    <div ref={container} className={s.selector} onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
    }}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
        <circle cx="12" cy="12" r="9" /><ellipse cx="12" cy="12" rx="4" ry="9" /><path d="M3 12h18" />
      </svg>
      <button ref={trigger} type="button" className={s.trigger} aria-label={`${t('Language')}: ${selected.name}`}
        aria-haspopup="listbox" aria-expanded={open} aria-controls={open ? id : undefined}
        onClick={() => open ? setOpen(false) : show()}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); show(); }
        }}>
        <Flag language={language} /><span lang={language}>{selected.name}</span>
        <svg className={s.chevron} width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" aria-hidden="true"><path d="m3 4.5 3 3 3-3" /></svg>
      </button>
      <div ref={list} id={id} className={s.options} style={{ translate: `${menuOffset}px 0`, maxHeight: `${menuMaxHeight}px` }} data-motion="popup" hidden={!open} aria-hidden={!open} role="listbox" tabIndex={-1}
        aria-label={t('Language')} aria-activedescendant={`${id}-${active}`} onKeyDown={handleKey}>
        {languages.map((item, index) => <div key={item.code} id={`${id}-${index}`} role="option"
          aria-selected={language === item.code} className={`${s.option} ${active === index ? s.active : ''}`}
          onPointerMove={() => setActive(index)} onClick={() => choose(index)}>
          <Flag language={item.code} /><span lang={item.code}>{item.name}</span>
        </div>)}
      </div>
    </div>
  );
}
