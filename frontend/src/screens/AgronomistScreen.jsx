import { useEffect, useState } from 'react';
import { useI18n } from '../i18n';
import Badge from '../components/Badge';
import SavedFields from '../components/SavedFields';
import { AGRONOMISTS, MINISTRY_HOTLINE } from '../data/agronomists';
import { ALL_DISTRICTS } from '../lib/terrain';
import Guide from '../components/Guide';

// Fourth tab: the agronomist of the field's district is picked automatically.
// Choosing a saved field switches to its district; any other district can be chosen too.
export default function AgronomistScreen({ hasField, district, points, plans, chooseField, goField }) {
  const { t } = useI18n();
  const [shown, setShown] = useState(district);

  useEffect(() => setShown(district), [district]);

  const byName = (a, b) => t(`districts.${a}`).localeCompare(t(`districts.${b}`));
  const agronomist = shown && AGRONOMISTS[shown];

  return (
    <div className="screen">
      <Guide role="farmer" tip="farmer.agro" />
      <h2>{t('agro.title')}</h2>
      <SavedFields plans={plans} points={points} onPick={chooseField} />

      {!hasField && (
        <section className="card">
          <p>{t('agro.noField')}</p>
          <button className="btn primary" onClick={goField}>{t('plan.goField')}</button>
        </section>
      )}

      {agronomist && (
        <section className="card agronomist">
          <div className="eyebrow">{shown === district ? t('agro.yours') : t('agro.other')}</div>
          <h3>{t('agro.district', { name: t(`districts.${shown}`) })}</h3>
          <p className="muted">
            {t('agro.role')} {agronomist.demo && <Badge kind="demo" source={t('agro.demoSource')} />}
          </p>
          <a className="phone" href={`tel:${agronomist.phone.replace(/\s/g, '')}`}>{agronomist.phone}</a>
          <p className="hint">{t('agro.hours', { hours: agronomist.hours })}</p>
          <a className="btn primary" href={`tel:${agronomist.phone.replace(/\s/g, '')}`}>{t('agro.call')}</a>
        </section>
      )}

      <section className="card">
        <label className="label" htmlFor="district">{t('agro.pick')}</label>
        <select id="district" className="select" value={shown ?? ''} onChange={(e) => setShown(e.target.value)}>
          <option value="" disabled>—</option>
          {[...ALL_DISTRICTS].sort(byName).map((id) => (
            <option key={id} value={id}>{t(`districts.${id}`)}</option>
          ))}
        </select>
      </section>

      <section className="card hotline">
        <h3>{t('agro.hotlineTitle')}</h3>
        <p className="muted">{t('agro.hotlineText')}</p>
        <a className="btn" href={`tel:${MINISTRY_HOTLINE}`}>{t('verdict.hotline')}</a>
      </section>
    </div>
  );
}
