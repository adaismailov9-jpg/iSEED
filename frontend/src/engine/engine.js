// Deterministic rules from spec section 4. No AI, no randomness.
import { CROPS } from '../data/crops';
import { RULES } from '../data/rules';

const levelOf = (ratio) => (ratio >= RULES.fits ? 'fits' : ratio >= RULES.tight ? 'tight' : 'short');
const WATER_RANK = { fits: 2, tight: 1, short: 0 };

// Crop rotation: which crop groups grow well after the previous one.
const GOOD_AFTER = { cereal: ['legume'], legume: ['cereal'], root: ['cereal'], oilseed: ['cereal', 'legume'], fodder: ['cereal'] };
export const groupOf = (id) => (id === 'wheat' ? 'cereal' : CROPS.find((c) => c.id === id)?.group);

function rotationScore(group, previousGroup) {
  if (!previousGroup) return 0;
  if (group === previousGroup) return -1; // same group again: more pests, tired soil
  return GOOD_AFTER[previousGroup].includes(group) ? 1 : 0;
}

// How the farmer's priority ranks crops (higher is better).
const PRIORITY_SCORE = {
  water: (crop) => crop.ratio,
  income: (crop) => crop.income,
  soil: (crop) => crop.rotation + (crop.group === 'legume' || crop.group === 'fodder' ? 1 : 0),
};

function evaluate(crop, { areaHa, source, canal, usual, snowLevel, climate }) {
  // 1. Water the crop needs
  const rainMm = climate.seasonRainMm * Math.min(1, crop.days / climate.seasonDays);
  const effRainMm = RULES.effectiveRain * rainMm;
  const needM3 = Math.max(0, crop.needMm - effRainMm) * 10 * areaHa;

  // 2. Water the field can expect
  let supplyM3;
  if (source === 'well') supplyM3 = needM3 * RULES.well[usual];
  else if (source === 'rain') supplyM3 = effRainMm * 10 * areaHa;
  else supplyM3 = RULES.basePerHa * areaHa * RULES.snowMultiplier[snowLevel] * RULES.canal * RULES.efficiency * (RULES.canalPosition[canal] ?? 1);

  // 3. Fit
  const ratio = needM3 > 0 ? Math.min(10, supplyM3 / needM3) : 10;
  const frostOk = crop.days <= climate.frostFreeDays;
  return { ...crop, effRainMm, needM3, supplyM3, ratio, frostOk, level: frostOk ? levelOf(ratio) : 'short' };
}

// Ranks every crop for this field: season long enough, then enough water, then good rotation,
// then the farmer's priority. The best one is recommended unless the farmer picked a crop.
export function runEngine(input) {
  const previousGroup = groupOf(input.previous);
  const priority = PRIORITY_SCORE[input.priority] ?? PRIORITY_SCORE.water;

  const rank = (r) => [r.frostOk ? 1 : 0, WATER_RANK[r.level], r.rotation >= 0 ? 1 : 0, priority(r), r.ratio];
  const better = (a, b) => {
    const [ra, rb] = [rank(a), rank(b)];
    const i = ra.findIndex((v, k) => v !== rb[k]);
    return i === -1 ? 0 : rb[i] - ra[i];
  };

  const all = CROPS.map((c) => {
    const r = evaluate(c, input);
    return { ...r, rotation: rotationScore(r.group, previousGroup) };
  }).sort(better);

  const chosen = all.find((r) => r.id === input.crop) ?? all[0];
  const alternatives = all
    .filter((r) => r.id !== chosen.id && r.frostOk)
    .slice(0, 2)
    .map((r) => ({ ...r, diffPct: Math.round((1 - r.needMm / chosen.needMm) * 100) }));

  return { chosen, alternatives, all };
}
