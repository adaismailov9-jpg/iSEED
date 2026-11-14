import { useEffect, useState } from 'react';
import { useI18n } from '../i18n';
import { api } from '../api/client';
import { ErrorText } from '../components/Texts';
import { BASIN_IDS } from '../data/ids';
import HindcastChart from '../components/HindcastChart';
import Guide from '../components/Guide';

const SOURCE_KEYS = ['fldas', 'modis', 'imerg', 'power', 'srtm', 'modisNdvi', 'soilgrids', 'hydrobasins', 'tiles', 'border'];

export default function AboutScreen({ basinId, role }) {
  const { t } = useI18n();
  const [basin, setBasin] = useState(basinId ?? 'talas');
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    setData(null);
    setError(null);
    api.hindcast(basin).then(setData).catch((err) => setError(err.code));
  }, [basin]);

  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
  }, []);

  const shortYears = data?.shortYears.filter((s) => data.series.some((p) => p.year === s.year && p.short)) ?? [];

  return (
    <div className="screen">
      <Guide role={role} tip="about" />
      <section className="card">
        <h2>{t('tabs.about')}</h2>
        <p>{t('about.intro')}</p>
      </section>

      <section className="card">
        <div className="chart-head">
          <h3>{t('about.chart')}</h3>
          <select value={basin} onChange={(e) => setBasin(e.target.value)} aria-label={t('basin.label')}>
            {BASIN_IDS.map((id) => <option key={id} value={id}>{t(`basins.${id}`)}</option>)}
          </select>
        </div>
        <ErrorText code={error} />
        {data && <HindcastChart data={data} />}
        {!data && !error && <p className="muted">{t('common.loading')}</p>}
        {data?.south && <p className="verdict-note">{t('season.south')}</p>}
        {shortYears.length > 0 && (
          <ul className="sources">
            {shortYears.map((s) => <li key={s.year}><b>{s.year}</b>: {s.source}</li>)}
          </ul>
        )}
        <p className="hint">{t('about.missNote')}</p>
        {data?.check && (
          <p className="hint">{t('about.modisCheck', { r: data.check.r, both: data.check.lowInBoth.join(', ') || '—' })}</p>
        )}
      </section>

      <section className="card">
        <p className="note">{t('evidence.notForecast')}</p>
      </section>

      <section className="card">
        <h3>{t('about.sources')}</h3>
        <ul className="sources">
          {SOURCE_KEYS.map((key) => <li key={key}>{t(`about.src.${key}`)}</li>)}
        </ul>
        {health && <p className="hint">{t('about.computed', { date: health.data.snow ?? '—' })}</p>}
      </section>
    </div>
  );
}
