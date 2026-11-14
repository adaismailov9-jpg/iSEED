import { useI18n } from '../i18n';
import { fmtM3 } from '../lib/format';

// One other crop with a button to choose it. `field` names the field it is for (in the plan list).
export default function AltRow({ crop, onPick, disabled, field, className = '' }) {
  const { t, lang } = useI18n();
  return (
    <div className={`alt level-${crop.level} ${className}`}>
      <div>
        <b><span className="dot" /> {t(`crops.${crop.id}`)}</b>
        <div className="hint">
          {fmtM3(crop.needM3, lang)} {t('units.m3')} ·{' '}
          {crop.diffPct >= 0 ? t('alt.less', { pct: crop.diffPct }) : t('alt.more', { pct: -crop.diffPct })} ·{' '}
          {t(`income.${crop.income}`)}
        </div>
        {field && <div className="hint">{t('plan.forField', { field })}</div>}
      </div>
      <button className="btn small" onClick={() => onPick(crop.id)} disabled={disabled}>{t('alt.check')}</button>
    </div>
  );
}
