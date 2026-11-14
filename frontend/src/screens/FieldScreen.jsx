import { useState } from 'react';
import { useI18n } from '../i18n';
import FieldMap from '../components/FieldMap';
import PlaceSearch from '../components/PlaceSearch';
import Questions from '../components/Questions';
import Badge from '../components/Badge';
import { MIN_POINTS, areaHa, squareAround } from '../lib/geo';
import { fmtDec, fmtPct } from '../lib/format';
import { SOURCES } from '../data/rules';

// First tab: the questions (left on wide screens) and the field on the map (right).
export default function FieldScreen({ points, setPoints, basin, answers, setAnswers, onSubmit, busy, error }) {
  const { t, lang } = useI18n();
  const [moving, setMoving] = useState(null); // corners while a handle is being dragged
  const [focus, setFocus] = useState(null);
  const [locateError, setLocateError] = useState('');

  const shown = moving ?? points;
  const hasField = points.length >= MIN_POINTS;

  function commit(next) {
    setMoving(null);
    setPoints(next);
  }

  // A 1 ha field around a point; the farmer then drags the corners to the real edges.
  function placeField(center) {
    commit(squareAround(center, 1));
    setFocus({ center, zoom: 17 });
    setLocateError('');
  }

  function locate() {
    navigator.geolocation.getCurrentPosition(
      (pos) => placeField([pos.coords.latitude, pos.coords.longitude]),
      () => setLocateError(t('field.locateFailed'))
    );
  }

  return (
    <div className="field-screen">
      <div className="map-box">
        <FieldMap points={points} onChange={commit} onMove={setMoving} onTapEmpty={placeField} focus={focus} />
        <div className="map-top">
          <PlaceSearch onPick={(center) => setFocus({ center, zoom: 15 })} />
          <button className="btn small floating" onClick={locate}>{t('field.locate')}</button>
        </div>
      </div>

      <aside className="panel">
        <section className="field-card">
          <h2>{t('field.title')}</h2>
          <p className="hint">{locateError || t(hasField ? 'field.editHint' : 'field.hint')}</p>
          {hasField && (
            <div className="field-summary">
              <div>
                <div className="label">{t('field.area')}</div>
                <div className="big">{fmtDec(areaHa(shown), 2, lang)} <small>{t('units.ha')}</small></div>
                <div className="hint">{t('field.corners', { n: shown.length })}</div>
                <button className="btn small" onClick={() => commit([])}>{t('field.clear')}</button>
              </div>
              <BasinInfo basin={basin} />
            </div>
          )}
        </section>

        <Questions answers={answers} setAnswers={setAnswers} onSubmit={onSubmit} hasField={hasField} busy={busy} />
        {error && <p className="error">{t('common.error')}</p>}
      </aside>
    </div>
  );
}

function BasinInfo({ basin }) {
  const { t } = useI18n();
  if (!basin) return <div className="muted">{t('basin.loading')}</div>;
  return (
    <div className="basin">
      <div className="label">{t('basin.label')}</div>
      <div className="basin-name">
        {t(`basins.${basin.id}`)} {basin.demo && <Badge kind="demo" source={SOURCES.snow} />}
      </div>
      <div className="label">{t('basin.snow')}</div>
      <span className={`snow-chip snow-${basin.level}`}>
        {t(`levels.${basin.level}`)} · {fmtPct(basin.anomaly)}
      </span>
    </div>
  );
}
