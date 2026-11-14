import { useI18n } from '../i18n';
import { fmtM3 } from '../lib/format';

export default function Alternatives({ items, priority, onPick, disabled }) {
  const { t, lang } = useI18n();
  return (
    <section className="card">
      <h3>{t('alt.title', { priority: t(`priority.${priority}`) })}</h3>
      {items.length === 0 && <p className="muted">{t('alt.none')}</p>}
      {items.map((crop) => (
        <div key={crop.id} className={`alt level-${crop.level}`}>
          <div>
            <b><span className="dot" /> {t(`crops.${crop.id}`)}</b>
            <div className="hint">
              {fmtM3(crop.needM3, lang)} {t('units.m3')} ·{' '}
              {crop.diffPct >= 0 ? t('alt.less', { pct: crop.diffPct }) : t('alt.more', { pct: -crop.diffPct })} ·{' '}
              {t(`income.${crop.income}`)}
            </div>
          </div>
          <button className="btn small" onClick={() => onPick(crop.id)} disabled={disabled}>{t('alt.check')}</button>
        </div>
      ))}
    </section>
  );
}
