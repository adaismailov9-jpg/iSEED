// DEMO data in the shape of data/snow.json and GET /climate.
// The real numbers come from scripts/ (MODIS, HydroBASINS, NASA POWER) during the event.

export const YEARS = Array.from({ length: 24 }, (_, i) => 2003 + i); // 2003–2026
export const SHORTAGE_YEARS = [2008, 2014, 2021, 2023];
export const SEASONS = { current: 2026, example: 2023 };
export const SNOW_DATE = '2026-04-02';
export const EARLY_DATE = '2026-11-12';

// Approximate basin centres (real lookup: point in polygon on basins.geojson).
export const BASINS = [
  { id: 'chuy', lat: 42.75, lon: 74.8, scale: 1 },
  { id: 'talas', lat: 42.45, lon: 72.3, scale: 0.95 },
  { id: 'issykkul', lat: 42.4, lon: 77.5, scale: 0.86 },
  { id: 'naryn_upper', lat: 41.5, lon: 75.6, scale: 1.14 },
  { id: 'naryn_toktogul', lat: 41.85, lon: 73.2, scale: 1.03 },
  { id: 'atbashy', lat: 41.05, lon: 75.9, scale: 1.07 },
  { id: 'chatkal', lat: 41.9, lon: 71.5, scale: 1.1 },
  { id: 'karadarya', lat: 40.7, lon: 73.2, scale: 0.83 },
  { id: 'batken', lat: 39.95, lon: 70.9, scale: 0.76 },
  { id: 'saryjaz', lat: 42.0, lon: 79.0, scale: 1.24 },
];

// Chüy Feb–Mar snow fraction. 2021 is a deliberate "miss": the shortage came from summer heat.
const CHUY = [0.62, 0.58, 0.66, 0.55, 0.57, 0.38, 0.64, 0.7, 0.52, 0.68, 0.54, 0.41,
  0.6, 0.63, 0.67, 0.5, 0.61, 0.56, 0.56, 0.59, 0.4, 0.65, 0.53, 0.58];

export function basinStats(id) {
  const n = BASINS.findIndex((b) => b.id === id);
  // Other basins: the Chüy series scaled, with a small wobble so they don't look identical.
  const wobble = (i) => (id === 'chuy' ? 1 : 1 + 0.08 * Math.sin(i * 1.7 + n));
  const values = CHUY.map((v, i) => v * BASINS[n].scale * wobble(i));

  const history = values.slice(0, -1); // 2003–2025
  const norm = history.reduce((a, b) => a + b, 0) / history.length;
  const sorted = [...history].sort((a, b) => a - b);
  const terciles = [sorted[Math.floor(sorted.length / 3)], sorted[Math.floor((sorted.length * 2) / 3)]];
  const levelOf = (v) => (v < terciles[0] ? 'low' : v > terciles[1] ? 'high' : 'normal');

  return {
    norm,
    terciles,
    series: YEARS.map((year, i) => ({ year, value: values[i], level: levelOf(values[i]) })),
    earlyAnomaly: 0.15 * Math.sin(n * 2.3) - 0.05, // snow so far this winter vs norm
  };
}

export function nearestBasin(lat, lon) {
  const dist = (b) => (b.lat - lat) ** 2 + ((b.lon - lon) * 0.73) ** 2;
  return BASINS.reduce((best, b) => (dist(b) < dist(best) ? b : best));
}

// Northern fields get a shorter, wetter season.
export function demoClimate(lat) {
  return {
    frostFreeDays: Math.round(230 - (lat - 39) * 20),
    seasonRainMm: Math.round(140 + (lat - 39) * 25), // Apr–Sep
    seasonDays: 183,
    gwetroot: 0.42,
    years: '2021–2025',
    demo: true,
  };
}
