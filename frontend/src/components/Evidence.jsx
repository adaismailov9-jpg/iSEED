import { useI18n } from '../i18n';
import { fmtDec, fmtInt, fmtPct, snowDirection } from '../lib/format';
import Badge, { SourceBadge } from './Badge';

function Row({ label, children }) {
  return (
    <div className="ev-row">
      <span>{label}</span>
      <b>{children}</b>
    </div>
  );
}

// "What the answer is based on": the numbers and their sources, straight from the /farmer response.
export default function Evidence({ result }) {
  const { t, lang } = useI18n();
  const { snow, scenarios, evidence, options } = result;
  const { climate, rain, prices, rules, formula } = evidence;
  const need = options[0].need;
  const mm = (n) => `${fmtInt(n, lang)} ${t('units.mm')}`;
  const estimates = Object.entries(rules).filter(([, rule]) => rule.estimate);

  return (
    <div className="evidence">
      <h4>{t('evidence.snow')} <SourceBadge id="fldas" /></h4>
      <Row label={t('evidence.basin')}>{t(`basins.${snow.basin}`)}</Row>
      <Row label={t('evidence.level')}>{t(`levels.${snowDirection(snow.anomaly)}`)} ({fmtPct(snow.anomaly)})</Row>
      <Row label={t('evidence.month')}>{snow.month}</Row>
      <Row label={t('evidence.dry')}>{fmtPct(scenarios.dry.snowAnomaly)} · S {fmtDec(scenarios.dry.s, 2, lang)} · P {fmtDec(scenarios.dry.p, 2, lang)}</Row>
      <Row label={t('evidence.normal')}>S {fmtDec(scenarios.normal.s, 2, lang)} · P {fmtDec(scenarios.normal.p, 2, lang)}</Row>

      <h4>{t('evidence.need', { crop: t(`crops.${options[0].crop}`) })} {need.source === 'hargreaves' ? <SourceBadge id="power" /> : <Badge source={t('evidence.needSource.typical')} />}</h4>
      <Row label={t('evidence.gross')}>{mm(need.grossMm)}</Row>
      <Row label={t('evidence.rain')}>{mm(need.rainMm)}</Row>
      <Row label={t('evidence.net')}>{mm(need.netMm)}</Row>

      <h4>{t('evidence.climate')} <SourceBadge id="power" /></h4>
      <Row label={t('evidence.frostFree')}>{climate.frostFreeDays} {t('units.days')}</Row>
      <Row label={t('evidence.seasonRain')}>{mm(climate.seasonRainMm)}</Row>
      <Row label={t('evidence.height')}>{fmtInt(climate.elevM, lang)} {t('units.m')}</Row>
      <Row label={t('evidence.years')}>{climate.window}</Row>
      {rain && <Row label={t('evidence.rainData')}>{rain.window} <SourceBadge id="imerg" /></Row>}

      {Object.keys(prices).length > 0 && <h4>{t('evidence.prices')}</h4>}
      {Object.entries(prices).map(([crop, p]) => (
        <Row key={crop} label={t(`crops.${crop}`)}>
          {fmtDec(p.yield_t_ha[0], 1, lang)}–{fmtDec(p.yield_t_ha[1], 1, lang)} {t('units.tHa')} · {p.price_som_kg[0]}–{p.price_som_kg[1]} {t('units.somKg')} · {p.date}{' '}
          <Badge source={p.source} />
        </Row>
      ))}

      <details className="estimates">
        <summary>{t('evidence.estimates', { n: estimates.length })}</summary>
        <ul>{estimates.map(([key, rule]) => <li key={key}>{rule.source}</li>)}</ul>
      </details>
      <p className="formula">{formula}</p>
      <p className="note">{t('evidence.notForecast')}</p>
    </div>
  );
}
