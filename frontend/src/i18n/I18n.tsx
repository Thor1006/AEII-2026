import type { ReactElement, ReactNode } from 'react';
import { cloneElement, createContext, isValidElement, useContext, useEffect, useMemo, useState } from 'react';
import { createTranslator } from './messages.ts';
import type { Language } from './messages.ts';

export const languages = [
  { code: 'en', name: 'English' },
  { code: 'th', name: 'ไทย' },
  { code: 'zh-HK', name: '繁體中文（香港）' },
] as const;
const STORAGE_KEY = 'trf-language';
export type Translator = (message: string, values?: Record<string, string | number>) => string;
interface I18nValue {
  language: Language;
  setLanguage: (language: Language) => void;
  t: Translator;
  ui: (node: ReactNode) => ReactNode;
}
const english = createTranslator('en');
// Reusable display components still work in English when rendered without the app provider.
const I18nContext = createContext<I18nValue>({
  language: 'en', setLanguage: () => {}, t: english,
  ui: (node) => localizeUi(node, english),
});

function readLanguage(): Language {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved === 'th' || saved === 'zh-HK' ? saved : 'en';
  } catch { return 'en'; }
}

/** Translate display text only; do not change form values, events, refs, or protocol data. */
export function localizeUi(node: ReactNode, t: Translator): ReactNode {
  if (typeof node === 'string') return t(node);
  if (Array.isArray(node)) return node.map((child, index) => {
    const translated = localizeUi(child, t);
    // Static JSX siblings normally rely on positional identity. Cloning turns them
    // into a dynamic array, so give only unkeyed elements a stable positional key.
    return isValidElement(translated) && translated.key === null
      ? cloneElement(translated, { key: `i18n-static-${index}` }) : translated;
  });
  if (!isValidElement(node)) return node;
  const element = node as ReactElement<Record<string, unknown>>;
  const props = element.props;
  if (props.translate === 'no' || element.type === 'code' || element.type === 'pre') return node;
  const changes: Record<string, unknown> = {};
  for (const key of ['title', 'aria-label', 'aria-description', 'placeholder', 'alt']) {
    if (typeof props[key] === 'string') changes[key] = t(props[key] as string);
  }
  // Translating <option> content must never change its submitted value.
  if (element.type === 'option' && props.value === undefined && typeof props.children === 'string') changes.value = props.children;
  if ('children' in props) changes.children = localizeUi(props.children as ReactNode, t);
  return cloneElement(element, changes);
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(readLanguage);
  useEffect(() => {
    document.documentElement.lang = language;
    try { localStorage.setItem(STORAGE_KEY, language); } catch { /* Storage may be disabled. */ }
  }, [language]);
  const value = useMemo(() => {
    const t = createTranslator(language);
    return { language, setLanguage, t, ui: (node: ReactNode) => localizeUi(node, t) };
  }, [language]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  return useContext(I18nContext);
}
