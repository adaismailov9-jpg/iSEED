// In-browser stand-in for the FastAPI backend: same routes, same JSON shapes.
import { RULES } from '../data/rules';
import { BASINS, basinStats, demoClimate, nearestBasin, SEASONS, SHORTAGE_YEARS, SNOW_DATE, EARLY_DATE } from '../data/demo';
import { groupOf, runEngine } from '../engine/engine';
import { translate } from '../i18n';
import { areaHa, centroid, fromGeoJSON } from '../lib/geo';
import { fmtDec, fmtM3 } from '../lib/format';

const reply = (data) => new Promise((resolve) => setTimeout(() => resolve(data), 200));

function getBasin(lat, lon, season = 'current') {
  return snowFor(nearestBasin(lat, lon).id, season);
}

function snowFor(id, season = 'current') {
  const stats = basinStats(id);
  const year = SEASONS[season];
  const { value, level } = stats.series.find((p) => p.year === year);
  return {
    id,
    level,
    anomaly: (value - stats.norm) / stats.norm,
    season,
    year,
    date: SNOW_DATE,
    early: { anomaly: stats.earlyAnomaly, date: EARLY_DATE },
    demo: true,
  };
}

// `crop` is optional: without it the engine recommends one after the `previous` crop.
function check({ geometry, previous, crop, source, canal, usual, soil, season, priority }, lang) {
  const points = fromGeoJSON(geometry);
  const ha = areaHa(points);
  const [lat, lon] = centroid(points);
  const basin = getBasin(lat, lon, season);
  const climate = demoClimate(lat);
  const { chosen, alternatives, all } = runEngine({ areaHa: ha, previous, crop, source, canal, usual, priority, snowLevel: basin.level, climate });

  // The verdict text is written by the API; the screen only styles it.
  const t = (key, vars) => translate(lang, key, vars);
  const cropName = t(`crops.${chosen.id}`);
  const vars = {
    crop: cropName,
    cropLower: cropName.toLowerCase(),
    ha: fmtDec(ha, 1, lang),
    basin: t(`basins.${basin.id}`),
    levelText: t(`levelsInline.${basin.level}`),
    need: fmtM3(chosen.needM3, lang),
    supply: fmtM3(chosen.supplyM3, lang),
    days: chosen.days,
    ffd: climate.frostFreeDays,
  };
  const why = !chosen.frostOk ? 'frost' : source === 'pump' ? 'river' : source;

  const numbers = { cropNeed: chosen.needMm };
  if (source === 'river' || source === 'pump') {
    Object.assign(numbers, { base: RULES.basePerHa, snowMultiplier: RULES.snowMultiplier[basin.level], canal: RULES.canal, efficiency: RULES.efficiency });
    if (canal) numbers.canalPosition = RULES.canalPosition[canal];
  }
  if (source === 'well') numbers.well = RULES.well[usual];

  return reply({
    lang,
    input: { previous, crop, source, canal, usual, soil, season, priority, areaHa: ha },
    verdict: {
      level: chosen.level,
      sentence: t(`verdict.sentence.${chosen.frostOk ? chosen.level : 'frost'}`, vars),
      reason: t(`verdict.reason.${why}`, vars),
    },
    chosen,
    alternatives,
    all,
    tip: t(`tip.${chosen.group}`),
    notes: notesFor(chosen, { previous, source }, t, vars),
    evidence: { basin, climate, numbers, soil },
  });
}

// Warnings and pluses under the verdict: the pump and the crop rotation.
function notesFor(chosen, { previous, source }, t, vars) {
  const notes = [];
  if (source === 'pump') notes.push({ kind: chosen.pumpStop === 'light' ? 'info' : 'warn', text: t(`note.pump.${chosen.pumpStop}`, vars) });

  const previousVars = { ...vars, previous: previous && t(`crops.${previous}`) };
  if (chosen.rotation < 0) {
    notes.push({ kind: 'warn', text: t('note.rotation.same', previousVars) });
  } else if (chosen.rotation > 0) {
    const legume = chosen.group === 'legume' && groupOf(previous) === 'cereal';
    notes.push({ kind: 'good', text: t(legume ? 'note.rotation.legume' : 'note.rotation.good', previousVars) });
  }
  return notes;
}

// Water manager: expected irrigation turns and which canal positions will be short of water.
const MANAGER_CROPS = ['beans', 'alfalfa']; // beans and hay
function manager({ basin, source, turns }) {
  const snow = snowFor(basin);
  const climate = demoClimate(BASINS.find((b) => b.id === basin).lat);
  const positions = Object.keys(RULES.canalPosition).map((position) => {
    const { all } = runEngine({ areaHa: 1, source, canal: position, snowLevel: snow.level, climate, priority: 'water' });
    return { position, crops: MANAGER_CROPS.map((id) => ({ id, level: all.find((c) => c.id === id).level })) };
  });
  const expected = Math.max(1, Math.round(turns * RULES.snowMultiplier[snow.level]));
  return reply({ snow, turns: { usual: turns, expected }, positions, demo: true });
}

function getHindcast(basinId) {
  const { norm, terciles, series } = basinStats(basinId);
  return reply({ basin: basinId, norm, terciles, series, shortageYears: SHORTAGE_YEARS, currentYear: SEASONS.current, demo: true });
}

export const mockApi = {
  getBasin: (lat, lon) => reply(getBasin(lat, lon)),
  getSnow: (basin) => reply(snowFor(basin)),
  manager,
  getHindcast,
  check,
};
