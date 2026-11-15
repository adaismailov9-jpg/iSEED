// Kyrgyz and Russian: "9 717" and "6,5". English: "9,717" and "6.5".
export const fmtInt = (n, lang) =>
  Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, lang === 'en' ? ',' : ' ');

export const fmtDec = (n, digits, lang) => (lang === 'en' ? n.toFixed(digits) : n.toFixed(digits).replace('.', ','));

// Below / near / above normal from the snow anomaly, the same number the water factor uses.
// (The tercile level from snow.json can call -20% "normal", which reads as a contradiction.)
export const snowDirection = (anomaly) => (anomaly <= -0.05 ? 'low' : anomaly >= 0.05 ? 'high' : 'normal');

export const fmtPct = (x) => `${x > 0 ? '+' : ''}${Math.round(x * 100)}%`; // change: +12%, −20%

export const fmtShare = (x) => `${Math.round(x * 100)}%`; // share: 81%

// Income is an estimate: round to 1,000 som. "59 000–144 000"
export const fmtSomRange = ({ low, high }, lang) =>
  `${fmtInt(Math.round(low / 1000) * 1000, lang)}–${fmtInt(Math.round(high / 1000) * 1000, lang)}`;

// Chrome has no Kyrgyz month names (it falls back to English), so they are written out here.
const KY_MONTHS = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь'];

// API dates are "MM-DD": show "6-май" / "6 мая" / "May 6".
export function fmtDay(mmdd, lang) {
  const [m, d] = mmdd.split('-').map(Number);
  if (lang === 'ky') return `${d}-${KY_MONTHS[m - 1]}`;
  try {
    return new Date(2027, m - 1, d).toLocaleDateString(lang, { day: 'numeric', month: 'long' });
  } catch {
    return mmdd;
  }
}

// Fit (share of the water need the field gets) as a colour level. shortFit comes from the API's rules.
export const fitLevel = (fit, shortFit) => (fit >= 0.99 ? 'fits' : fit >= shortFit ? 'tight' : 'short');
