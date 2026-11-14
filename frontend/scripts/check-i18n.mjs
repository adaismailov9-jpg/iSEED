// Fails if ky.json, ru.json and en.json do not have the same keys and the same {placeholders}.
import { readFileSync } from 'node:fs';

const LANGS = ['ky', 'ru', 'en'];

const flatten = (obj, prefix = '', out = {}) => {
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === 'object') flatten(value, path, out);
    else out[path] = value;
  }
  return out;
};
const placeholders = (text) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(',');
const load = (lang) => flatten(JSON.parse(readFileSync(new URL(`../src/i18n/${lang}.json`, import.meta.url), 'utf8')));

const en = load('en');
const errors = [];
for (const lang of LANGS.filter((l) => l !== 'en')) {
  const dict = load(lang);
  for (const key of Object.keys(en)) {
    if (!(key in dict)) errors.push(`${lang}: missing ${key}`);
    else if (placeholders(dict[key]) !== placeholders(en[key])) errors.push(`${lang}: placeholders differ in ${key}`);
  }
  for (const key of Object.keys(dict)) if (!(key in en)) errors.push(`${lang}: extra key ${key}`);
}

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}
console.log(`i18n OK: ${Object.keys(en).length} keys in ${LANGS.join(', ')}`);
