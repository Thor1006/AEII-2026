import { catalog } from './catalog.ts';
export type Language = 'en' | 'th' | 'zh-HK';
export const dictionaries: Record<Language, Record<string, string>> = {
  en: Object.fromEntries(Object.keys(catalog).map((key) => [key, key])),
  th: Object.fromEntries(Object.entries(catalog).map(([key, value]) => [key, value[0]])),
  'zh-HK': Object.fromEntries(Object.entries(catalog).map(([key, value]) => [key, value[1]])),
};
const escape = (text: string) => text.replace(/[.*+?^$()|[\]\\]/g, '\\$&');
const patterns = Object.keys(catalog).filter((key) => /\{\w+\}/.test(key)).sort((a,b) => b.length-a.length).map((key) => {
  const names: string[] = [];
  const source = key.split(/(\{\w+\})/).map((part) => {
    if (/^\{\w+\}$/.test(part)) { names.push(part.slice(1,-1)); return '(.*?)'; }
    return escape(part);
  }).join('');
  return { key, names, regex: new RegExp(`^${source}$`) };
});
const interpolate = (message: string, values: Record<string, string | number>) => message.replace(/\{(\w+)\}/g, (token,key: string) => Object.hasOwn(values, key) ? String(values[key] ?? token) : token);

/** Known UI messages translate; product identifiers and arbitrary user/kit text pass through. */
export function createTranslator(language: Language) {
  const dictionary = dictionaries[language];
  const lookup = (key: string) => Object.hasOwn(dictionary, key) ? dictionary[key] : undefined;
  const cache = new Map<string, string>();
  function translate(input: string, values: Record<string, string | number> = {}, depth = 0): string {
    if (language === 'en') return interpolate(input, values);
    if (Object.keys(values).length) return interpolate(lookup(input) ?? input, values);
    if (depth > 5 || !/[A-Za-z]/.test(input)) return input;
    const cached = cache.get(input);
    if (cached !== undefined) return cached;
    const text = input.trim().replace(/\s+/g, ' ');
    let result: string | undefined = lookup(text);
    if (result === undefined) {
      for (const pattern of patterns) {
        const match = pattern.regex.exec(text);
        if (!match) continue;
        result = interpolate(dictionary[pattern.key], Object.fromEntries(pattern.names.map((name,i) => [name, ['action','pattern','reason','exercise','label','side'].includes(name) ? translate(match[i+1], {}, depth+1) : match[i+1]])));
        break;
      }
    }
    if (result === undefined && / · |: /.test(text)) {
      result = text.split(/( · |: )/).map((part) => translate(part, {}, depth+1)).join('');
      if (result === text) result = undefined;
    }
    if (result === undefined) {
      const unitSuffix = /^(.*?) (\([^()]+\))$/.exec(text);
      if (unitSuffix && lookup(unitSuffix[1])) result = `${lookup(unitSuffix[1])} ${unitSuffix[2]}`;
    }
    const output = result === undefined ? input : input.slice(0,input.indexOf(input.trimStart())) + result + input.slice(input.trimEnd().length);
    if (cache.size > 1000) cache.clear();
    cache.set(input, output);
    return output;
  }
  return translate;
}
