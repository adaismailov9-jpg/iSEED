import { createContext, useContext, useEffect, useState } from 'react';
import ky from './ky.json';
import ru from './ru.json';
import en from './en.json';
import { load, save } from '../lib/storage';

const DICTS = { ky, ru, en };
export const LANGS = ['ky', 'ru', 'en'];

// translate('ky', 'alt.less', { pct: 20 }) → "20% азыраак суу талап кылат"
// `fallback`: another key to use when `key` is missing (e.g. an error code the app does not know).
export function translate(lang, key, vars = {}, fallback) {
  const text = key.split('.').reduce((obj, k) => obj?.[k], DICTS[lang]);
  if (typeof text !== 'string') return fallback ? translate(lang, fallback, vars) : key;
  return text.replace(/\{(\w+)\}/g, (match, name) => vars[name] ?? match);
}

const I18nContext = createContext();

export function I18nProvider({ children }) {
  const [lang, setLang] = useState(load('lang', 'ky'));

  useEffect(() => {
    document.documentElement.lang = lang;
    save('lang', lang);
  }, [lang]);

  const t = (key, vars, fallback) => translate(lang, key, vars, fallback);
  return <I18nContext.Provider value={{ lang, setLang, t }}>{children}</I18nContext.Provider>;
}

export const useI18n = () => useContext(I18nContext);
