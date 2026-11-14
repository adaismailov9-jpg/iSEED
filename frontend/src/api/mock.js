// In-browser stand-in for the FastAPI backend: same routes, same JSON shapes.
import { RULES } from '../data/rules';
import { basinStats, demoClimate, nearestBasin, SEASONS, SHORTAGE_YEARS, SNOW_DATE, EARLY_DATE } from '../data/demo';
import { runEngine } from '../engine/engine';
import { translate } from '../i18n';
import { areaHa, centroid, fromGeoJSON } from '../lib/geo';
import { fmtDec, fmtM3 } from '../lib/format';

const reply = (data) => new Promise((resolve) => setTimeout(() => resolve(data), 200));

function getBasin(lat, lon, season = 'current') {
  const { id } = nearestBasin(lat, lon);
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
function check({ geometry, previous, crop, source, soil, well, season, priority }, lang) {
  const points = fromGeoJSON(geometry);
  const ha = areaHa(points);
  const [lat, lon] = centroid(points);
  const basin = getBasin(lat, lon, season);
  const climate = demoClimate(lat);
  const { chosen, alternatives, all } = runEngine({ areaHa: ha, previous, crop, source, well, priority, snowLevel: basin.level, climate });

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
  const why = chosen.frostOk ? source : 'frost';

  const numbers = { cropNeed: chosen.needMm };
  if (source === 'river') {
    Object.assign(numbers, { base: RULES.basePerHa, snowMultiplier: RULES.snowMultiplier[basin.level], canal: RULES.canal, efficiency: RULES.efficiency });
  }
  if (source === 'well') numbers.well = RULES.well[well];

  return reply({
    lang,
    input: { previous, crop, source, soil, well, season, priority, areaHa: ha },
    verdict: {
      level: chosen.level,
      sentence: t(`verdict.sentence.${chosen.frostOk ? chosen.level : 'frost'}`, vars),
      reason: t(`verdict.reason.${why}`, vars),
    },
    chosen,
    alternatives,
    all,
    tip: t(`tip.${chosen.group}`),
    evidence: { basin, climate, numbers, soil },
  });
}

function getHindcast(basinId) {
  const { norm, terciles, series } = basinStats(basinId);
  return reply({ basin: basinId, norm, terciles, series, shortageYears: SHORTAGE_YEARS, currentYear: SEASONS.current, demo: true });
}

export const mockApi = {
  getBasin: (lat, lon) => reply(getBasin(lat, lon)),
  getHindcast,
  check,
};
