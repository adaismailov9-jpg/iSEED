import { useI18n } from '../i18n';
import { fitLevel, fmtShare, fmtSomRange } from '../lib/format';
import { waterLeftText } from './Texts';
import Badge from './Badge';
import SowingWindow from './SowingWindow';
import { CropIcon } from './Art';

// One option of POST /farmer: his plan, the water saver or the soil builder.
export default function OptionCard({ option, shortFit, onPick, busy }) {
  const { t, lang } = useI18n();
  const { kind, crop, highlight, normal, dry, priceKnown, waterLeftM3, soil, frostOk, sowing, pumpGap } = option;

  return (
    <section id={`option-${kind}`} className={`card option level-${fitLevel(normal.fit, shortFit)}${highlight ? ' highlight' : ''}`}>
      <div className="option-head">
        <div className="eyebrow">{t(`option.${kind}`)}</div>
        {highlight && <span className="pill">💧 {t('option.highlight')}</span>}
      </div>
      <div className="option-title">
        <CropIcon id={crop} size={56} />
        <h3 className="option-crop">{t(`crops.${crop}`)}</h3>
      </div>

      <div className="years">
        <Year label={t('option.normal')} data={normal} shortFit={shortFit} priceKnown={priceKnown} />
        <Year label={t('option.dry')} data={dry} shortFit={shortFit} priceKnown={priceKnown} />
      </div>
      {priceKnown && <p className="hint">{t('option.gross')} <Badge source={t('option.priceSource')} /></p>}

      {kind !== 'plan' && (
        <p className={waterLeftM3 >= 0 ? 'water-left' : 'water-left more'}>
          {waterLeftText(waterLeftM3, t, lang)}
        </p>
      )}

      <ul className="soil-list">
        {soil.nitrogen && <li className="good">✓ {t('option.nitrogen')}</li>}
        {soil.rotation === 'plus' && <li className="good">✓ {t('option.rotationPlus')}</li>}
        {soil.rotation === 'warning' && <li className="warn">⚠ {t('option.rotationWarning')}</li>}
        <li>{t('option.bareMonths', { n: soil.bareMonths })}</li>
      </ul>

      {pumpGap && <p className={`verdict-note ${pumpGap === 'light' ? '' : 'warn'}`}>⚠ {t(`option.pump.${pumpGap}`)}</p>}
      {!frostOk && <p className="verdict-note warn">⚠ {t('option.frost')}</p>}

      <SowingWindow sowing={sowing} />

      {onPick && <button className="btn" onClick={() => onPick(crop)} disabled={busy}>{t('option.pick')}</button>}
    </section>
  );
}

// A normal or a dry year: how much of the water need the field gets, and the gross income.
function Year({ label, data, shortFit, priceKnown }) {
  const { t, lang } = useI18n();
  return (
    <div className={`year level-${fitLevel(data.fit, shortFit)}`}>
      <div className="label">{label}</div>
      <div className="meter-track"><div className="meter-fill supply" style={{ width: fmtShare(data.fit) }} /></div>
      <div className="year-water"><span className="dot" /> {t('option.water', { pct: fmtShare(data.fit) })}</div>
      <div className="year-income">{priceKnown ? `${fmtSomRange(data.income, lang)} ${t('units.som')}` : t('option.noPrice')}</div>
    </div>
  );
}
