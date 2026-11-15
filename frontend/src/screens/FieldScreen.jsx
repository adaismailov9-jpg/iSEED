import { useState } from 'react';
import { useI18n } from '../i18n';
import FieldMap from '../components/FieldMap';
import PlaceSearch from '../components/PlaceSearch';
import Questions, { buildSteps } from '../components/Questions';
import Guide from '../components/Guide';
import { SnowMountain } from '../components/Art';
import { SourceBadge } from '../components/Badge';
import FieldCheck from '../components/FieldCheck';
import Icon from '../components/Icon';
import SavedFields from '../components/SavedFields';
import SeasonMessage from '../components/SeasonMessage';
import { ErrorText } from '../components/Texts';
import { MIN_POINTS, areaHa, centroid, squareAround } from '../lib/geo';
import { MAX_FIELD_ELEVATION, whyNotHere } from '../lib/terrain';
import { fmtDec, fmtInt, fmtPct, snowDirection } from '../lib/format';

// First tab: the questions (left on wide screens) and the field on the map (right).
export default function FieldScreen({ points, setPoints, plans, place, user, answers, setAnswers, resetAnswers, onSubmit, busy, error }) {
  const { t, lang } = useI18n();
  const [moving, setMoving] = useState(null); // corners while a handle is being dragged
  const [focus, setFocus] = useState(null);
  const [warning, setWarning] = useState(null); // { reason, height } when a spot is refused
  const [checking, setChecking] = useState(false);
  const [basemap, setBasemap] = useState('satellite');
  const [round, setRound] = useState(0); // a new field starts a new round of questions

  const shown = moving ?? points;
  const hasField = points.length >= MIN_POINTS;
  // The guide's tip follows the farmer: find the field, then each question, then the button.
  const nextQuestion = buildSteps(answers, t).find((step) => !answers[step.key]);
  const tip = !hasField ? 'farmer.map' : nextQuestion ? `farmer.q.${nextQuestion.key}` : 'farmer.ready';

  function commit(next) {
    setMoving(null);
    setPoints(next);
  }

  // New or removed field: the old answers no longer apply, so ask again from the first question.
  function startOver(next) {
    commit(next);
    resetAnswers();
    setRound(round + 1);
  }

  // A 1 ha field around a point, unless the spot is water, too high or outside Kyrgyzstan.
  // The farmer then drags the corners to the real edges.
  async function placeField(center) {
    setWarning(null);
    setChecking(true);
    const problem = await whyNotHere(center);
    setChecking(false);
    if (problem) return setWarning(problem);
    startOver(squareAround(center, 1));
    setFocus({ center, zoom: 17 });
  }

  // Put a saved field back on the map; the agronomist tab follows the field's district.
  function pickSaved(saved) {
    setWarning(null);
    startOver(saved);
    setFocus({ center: centroid(saved), zoom: 16 });
  }

  function locate() {
    navigator.geolocation.getCurrentPosition(
      (pos) => placeField([pos.coords.latitude, pos.coords.longitude]),
      () => setWarning({ reason: 'locate' })
    );
  }

  return (
    <div className="field-screen">
      <div className="map-box">
        <FieldMap points={points} onChange={commit} onMove={setMoving} onTapEmpty={placeField} focus={focus} basemap={basemap} />
        <div className="map-top">
          <PlaceSearch onPick={(center) => setFocus({ center, zoom: 15 })} />
          <button className="btn small floating" onClick={locate}><Icon name="locate" size={18} /> {t('field.locate')}</button>
        </div>
        <div className="map-switch">
          {['satellite', 'map'].map((id) => (
            <button key={id} className={basemap === id ? 'on' : ''} onClick={() => setBasemap(id)}>
              <Icon name={id} size={16} /> {t(`basemap.${id}`)}
            </button>
          ))}
        </div>

        {checking && <div className="map-message">{t('field.checking')}</div>}
        {warning && (
          <div className="map-message warning" role="alert">
            <span>⚠ {t(`warning.${warning.reason}`, { height: fmtInt(warning.height ?? 0, lang), max: fmtInt(MAX_FIELD_ELEVATION, lang) })}</span>
            <button onClick={() => setWarning(null)} aria-label={t('common.close')}>×</button>
          </div>
        )}
      </div>

      <aside className="panel">
        <Guide role="farmer" tip={tip} />
        <SeasonMessage village={user.village} />
        <section className="field-card">
          <h2>{t('field.title')}</h2>
          <p className="hint">{t(hasField ? 'field.editHint' : 'field.hint')}</p>
          {hasField && (
            <div className="field-summary">
              <div>
                <div className="label">{t('field.area')}</div>
                <div className="big">{fmtDec(areaHa(shown), 2, lang)} <small>{t('units.ha')}</small></div>
                <div className="hint">{t('field.corners', { n: shown.length })}</div>
                <button className="btn small" onClick={() => startOver([])}>{t('field.clear')}</button>
              </div>
              <BasinInfo place={place} />
            </div>
          )}
          {place && !place.error && <FieldCheck check={place.fieldCheck} />}
          <SavedFields plans={plans} points={points} onPick={pickSaved} />
        </section>

        <Questions key={round} answers={answers} setAnswers={setAnswers} onSubmit={onSubmit} hasField={hasField} busy={busy} />
        <ErrorText code={error} />
      </aside>
    </div>
  );
}

function BasinInfo({ place }) {
  const { t } = useI18n();
  if (!place) return <div className="muted">{t('basin.loading')}</div>;
  if (place.error) return <ErrorText code={place.error} />;
  const { basin, snow } = place;
  return (
    <div className="basin">
      <SnowMountain anomaly={snow.anomaly} size={72} label={t(`levels.${snowDirection(snow.anomaly)}`)} />
      <div className="label">{t('basin.label')}</div>
      <div className="basin-name">{t(`basins.${basin}`)}</div>
      <div className="label">{t('basin.snow')} <SourceBadge id="fldas" /></div>
      <span className={`snow-chip snow-${snowDirection(snow.anomaly)}`}>
        {t(`levels.${snowDirection(snow.anomaly)}`)} · {fmtPct(snow.anomaly)}
      </span>
    </div>
  );
}
