// Kyrgyz and Russian: "9 717" and "6,5". English: "9,717" and "6.5".
export const fmtInt = (n, lang) =>
  Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, lang === 'en' ? ',' : ' ');

export const fmtDec = (n, digits, lang) => (lang === 'en' ? n.toFixed(digits) : n.toFixed(digits).replace('.', ','));

export const fmtM3 = (n, lang) => fmtInt(Math.round(n / 100) * 100, lang); // volumes are estimates

export const fmtPct = (x) => `${x > 0 ? '+' : ''}${Math.round(x * 100)}%`;

export const fmtRatio = (r, lang) => (r >= 10 ? '≥10' : fmtDec(r, 2, lang));
