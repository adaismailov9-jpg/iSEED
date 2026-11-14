// Mirror of backend rules.json.
export const RULES = {
  fits: 1.1, // ratio ≥ 1.1 → enough water
  tight: 0.9, // 0.9–1.1 → tight, below → short
  basePerHa: 6.19e9 / 637000, // national irrigation use ÷ irrigated ploughland ≈ 9,717 m³/ha
  snowMultiplier: { low: 0.75, normal: 1.0, high: 1.1 },
  canal: 0.82, // ~18% transport losses
  efficiency: 0.6, // furrow irrigation
  effectiveRain: 0.7,
  well: { enough: 1.0, sometimes: 0.8, often: 0.6, unknown: 0.8 },
  canalPosition: { start: 1.0, middle: 0.85, end: 0.7 }, // share of canal water that reaches the field
};

// Shown when the user taps an "estimate" badge.
export const SOURCES = {
  base: 'National Statistical Committee KR: 6.19 km³ irrigation use (2024) ÷ ~637,000 ha irrigated',
  snowMultiplier: 'Assumption, to be checked against the hindcast and a hydrologist',
  canal: 'National transport losses 1.7–2.3 of 10–12 km³ (~18%)',
  efficiency: 'FAO, typical furrow irrigation',
  well: 'Farmer answer: enough 1.0 / sometimes short 0.8 / often short 0.6 / not sure 0.8',
  cropNeed: 'FAO-56 Tables 11–12, typical seasonal values',
  snow: 'NASA MODIS MOD10A1 v6.1, NDSI ≥ 40, mean of 1 Feb – 31 Mar',
  climate: 'NASA POWER daily point API (AG), 5-year mean',
  canalPosition: 'Assumption: start 100% / middle 85% / end 70% of the canal water; to be checked with water managers',
  turns: 'Usual number of turns × snow multiplier (low 0.75 / normal 1.0 / high 1.1)',
  pumpStop: 'Demo estimate: loss from a 10-day pump stop in July',
  income: 'Demo estimate (low / medium / high); to be replaced with real farm budgets',
};
