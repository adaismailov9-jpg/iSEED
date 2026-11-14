import { useI18n } from '../i18n';
import { fmtDec, fmtInt, fmtPct } from '../lib/format';
import { SOURCES } from '../data/rules';
import Badge from './Badge';

function Row({ label, children }) {
  return (
    <div className="ev-row">
      <span>{label}</span>
      <b>{children}</b>
    </div>
  );
}

export default function Evidence({ result }) {
  const { t, lang } = useI18n();
  const { basin, climate, numbers, soil } = result.evidence;
  const units = { cropNeed: ` ${t('units.mm')}`, base: ` ${t('units.m3')}/${t('units.ha')}` };

  return (
    <div className="evidence">
      <h4>{t('evidence.snow')} {basin.demo && <Badge kind="demo" source={SOURCES.snow} />}</h4>
      <Row label={t('evidence.basin')}>{t(`basins.${basin.id}`)}</Row>
      <Row label={t('evidence.level')}>{t(`levels.${basin.level}`)} ({fmtPct(basin.anomaly)})</Row>
      <Row label={t('evidence.date')}>{basin.date}</Row>
      <Row label={t('evidence.early')}>{t('evidence.earlyText', { pct: fmtPct(basin.early.anomaly), date: basin.early.date })}</Row>

      <h4>{t('evidence.climate')} {climate.demo && <Badge kind="demo" source={SOURCES.climate} />}</h4>
      <Row label={t('evidence.frostFree')}>{climate.frostFreeDays} {t('units.days')}</Row>
      <Row label={t('evidence.rain')}>{climate.seasonRainMm} {t('units.mm')}</Row>
      <Row label={t('evidence.effRain')}>{fmtInt(result.chosen.effRainMm, lang)} {t('units.mm')}</Row>
      <Row label={t('evidence.soilWet')}>{fmtDec(climate.gwetroot, 2, lang)}</Row>
      <Row label={t('evidence.years')}>{climate.years}</Row>
      <p className="hint">{t('evidence.soilInfo', { soil: t(`soil.${soil}`) })}</p>

      <h4>{t('evidence.numbers')}</h4>
      {Object.entries(numbers).map(([key, value]) => (
        <Row key={key} label={t(`evidence.${key}`)}>
          {units[key] ? fmtInt(value, lang) + units[key] : fmtDec(value, 2, lang)} <Badge source={SOURCES[key]} />
        </Row>
      ))}

      <p className="formula">{t('evidence.formula')}</p>
      <p className="note">{t('evidence.notForecast')}</p>
    </div>
  );
}
