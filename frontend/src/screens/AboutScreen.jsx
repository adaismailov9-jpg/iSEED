import { useEffect, useState } from 'react';
import { useI18n } from '../i18n';
import { api } from '../api/client';
import { BASINS } from '../data/demo';
import HindcastChart from '../components/HindcastChart';

const SOURCE_KEYS = ['modis', 'power', 'basins', 'fao', 'stats', 'tiles'];

export default function AboutScreen({ basinId = 'chuy' }) {
  const { t } = useI18n();
  const [basin, setBasin] = useState(basinId);
  const [data, setData] = useState(null);

  useEffect(() => {
    api.getHindcast(basin).then(setData);
  }, [basin]);

  return (
    <div className="screen">
      <section className="card">
        <h2>{t('tabs.about')}</h2>
        <p>{t('about.intro')}</p>
      </section>

      <section className="card">
        <div className="chart-head">
          <h3>{t('about.chart')}</h3>
          <select value={basin} onChange={(e) => setBasin(e.target.value)} aria-label={t('basin.label')}>
            {BASINS.map((b) => (
              <option key={b.id} value={b.id}>{t(`basins.${b.id}`)}</option>
            ))}
          </select>
        </div>
        {data ? <HindcastChart data={data} /> : <p className="muted">{t('common.loading')}</p>}
        <p className="hint">{t('about.missNote')}</p>
      </section>

      <section className="card">
        <p>{t('about.seasonNote')}</p>
        <p className="note">{t('evidence.notForecast')}</p>
      </section>

      <section className="card">
        <h3>{t('about.sources')}</h3>
        <ul className="sources">
          {SOURCE_KEYS.map((key) => <li key={key}>{t(`about.src.${key}`)}</li>)}
        </ul>
        {data?.demo && <p className="note">{t('about.demoNote')}</p>}
      </section>
    </div>
  );
}
