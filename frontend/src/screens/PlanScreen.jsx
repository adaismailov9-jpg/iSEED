import { useEffect } from 'react';
import { useI18n } from '../i18n';
import Verdict from '../components/Verdict';
import AltRow from '../components/AltRow';
import CompareTable from '../components/CompareTable';
import Evidence from '../components/Evidence';
import PlanShare from '../components/PlanShare';
import SeasonMessage from '../components/SeasonMessage';
import { SEASONS } from '../data/demo';
import { fmtDec } from '../lib/format';

// Second tab: every field + crop the farmer added, saved on the phone.
export default function PlanScreen({ plans, openId, setOpenId, updatePlan, deletePlan, busy, error, goField }) {
  const { t, lang } = useI18n();
  const open = plans.find((p) => p.id === openId);

  if (open) {
    return <PlanDetail plan={open} onBack={() => setOpenId(null)} onUpdate={(changes) => updatePlan(open.id, changes)} onDelete={() => deletePlan(open.id)} busy={busy} error={error} />;
  }

  if (plans.length === 0) {
    return (
      <div className="screen empty">
        <p>{t('plan.empty')}</p>
        <button className="btn primary" onClick={goField}>{t('plan.goField')}</button>
      </div>
    );
  }

  return (
    <div className="screen">
      <h2>{t('tabs.plan')}</h2>
      <p className="hint">{t('plan.saved')}</p>
      <SeasonMessage />
      {error && <p className="error">{t('common.error')}</p>}
      <div className="plan-list">
        {plans.map((plan) => (
          <div key={plan.id} className="plan-group">
            <h3>{t('plan.chosen')}</h3>
            <PlanCard plan={plan} onOpen={() => setOpenId(plan.id)} />
            {plan.result.alternatives.length > 0 && <h3>{t('plan.others')}</h3>}
            {plan.result.alternatives.slice(0, 2).map((crop) => (
              <AltRow
                key={crop.id}
                crop={crop}
                className="card"
                field={`${fmtDec(plan.result.input.areaHa, 2, lang)} ${t('units.ha')} · ${t(`basins.${plan.result.evidence.basin.id}`)}`}
                onPick={(id) => updatePlan(plan.id, { crop: id })}
                disabled={busy}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function PlanCard({ plan, onOpen }) {
  const { t, lang } = useI18n();
  const { input, verdict, evidence, chosen } = plan.result;
  return (
    <button className={`card plan-card level-${verdict.level}`} onClick={onOpen}>
      <div className="plan-card-head">
        <b>{t(`crops.${chosen.id}`)}</b>
        <span className="plan-verdict"><span className="dot" /> {t(`verdict.${verdict.level}`)}</span>
      </div>
      <div className="hint">
        {fmtDec(input.areaHa, 2, lang)} {t('units.ha')} · {t(`basins.${evidence.basin.id}`)} · {t(`priority.${input.priority}`)} · {plan.date}
      </div>
    </button>
  );
}

function PlanDetail({ plan, onBack, onUpdate, onDelete, busy, error }) {
  const { t, lang } = useI18n();
  const { result } = plan;

  // The verdict text is written in one language: ask again after the language changes.
  useEffect(() => {
    if (result.lang !== lang) onUpdate({});
  }, [lang, plan.id]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="screen plan-detail">
      <div className="row top">
        <button className="btn small" onClick={onBack}>← {t('plan.back')}</button>
        <button className="btn small danger" onClick={() => window.confirm(t('plan.confirmDelete')) && onDelete()}>{t('plan.delete')}</button>
      </div>
      {error && <p className="error">{t('common.error')}</p>}

      <div className="columns">
        <div className="column">
          <Verdict result={result} />
          <div className="season-pick">
            {t('verdict.pickSeason')}
            <div className="segmented">
              {Object.entries(SEASONS).map(([key, year]) => (
                <button key={key} className={result.input.season === key ? 'on' : ''} onClick={() => onUpdate({ season: key })} disabled={busy}>
                  {t(`verdict.${key}`, { year })}
                </button>
              ))}
            </div>
          </div>
          <a className="btn hotline" href="tel:1210">{t('verdict.hotline')}</a>
          <PlanShare plan={plan} />
        </div>

        <div className="column">
          <details className="card">
            <summary>{t('compare.title')}</summary>
            <CompareTable rows={result.all} chosenId={result.chosen.id} onPick={(crop) => onUpdate({ crop })} disabled={busy} />
          </details>
          <details className="card">
            <summary>{t('evidence.title')}</summary>
            <Evidence result={result} />
          </details>
        </div>
      </div>
    </div>
  );
}
