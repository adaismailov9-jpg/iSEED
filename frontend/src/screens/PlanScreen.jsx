import { useI18n } from '../i18n';
import OptionCard from '../components/OptionCard';
import FieldCheck from '../components/FieldCheck';
import Evidence from '../components/Evidence';
import PlanShare from '../components/PlanShare';
import SeasonMessage, { MessageBox } from '../components/SeasonMessage';
import { ErrorText, waterLeftText } from '../components/Texts';
import Badge from '../components/Badge';
import { fitLevel, fmtDay, fmtDec, fmtInt, fmtPct, fmtShare } from '../lib/format';

const shortFitOf = (result) => result.evidence.rules.short_fit.value;

// Second tab: every field + crop the farmer checked, kept on the phone.
export default function PlanScreen({ plans, user, openId, setOpenId, updatePlan, deletePlan, busy, error, goField }) {
  const { t, lang } = useI18n();
  const open = plans.find((p) => p.id === openId);
  const choose = (plan, crop) => updatePlan(plan.id, { plan: crop }); // ask again with another crop as the plan

  if (open) {
    return <PlanDetail plan={open} onBack={() => setOpenId(null)} onPick={(crop) => choose(open, crop)} onDelete={() => deletePlan(open.id)} busy={busy} error={error} />;
  }

  if (plans.length === 0) {
    return (
      <div className="screen empty">
        <SeasonMessage village={user.village} />
        <p>{t('plan.empty')}</p>
        <button className="btn primary" onClick={goField}>{t('plan.goField')}</button>
      </div>
    );
  }

  return (
    <div className="screen">
      <h2>{t('tabs.plan')}</h2>
      <p className="hint">{t('plan.saved')}</p>
      <SeasonMessage village={user.village} />
      <ErrorText code={error} />
      <div className="plan-list">
        {plans.map((plan) => {
          const { field, options } = plan.result;
          const fieldName = `${fmtDec(field.areaHa, 2, lang)} ${t('units.ha')} · ${t(`basins.${field.basin}`)}`;
          return (
            <div key={plan.id} className="plan-group">
              <h3>{t('plan.chosen')}</h3>
              <PlanCard plan={plan} fieldName={fieldName} onOpen={() => setOpenId(plan.id)} />
              {options.length > 1 && <h3>{t('plan.others')}</h3>}
              {options.slice(1).map((option) => (
                <OtherOption key={option.kind} option={option} shortFit={shortFitOf(plan.result)} fieldName={fieldName}
                  onPick={() => choose(plan, option.crop)} busy={busy} />
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// The water saver or soil builder under his plan in the list, with "Choose".
function OtherOption({ option, shortFit, fieldName, onPick, busy }) {
  const { t, lang } = useI18n();
  return (
    <div className={`alt card level-${fitLevel(option.normal.fit, shortFit)}`}>
      <div>
        <div className="eyebrow">{t(`option.${option.kind}`)}</div>
        <b><span className="dot" /> {t(`crops.${option.crop}`)}</b>
        <div className="hint">{t('option.water', { pct: fmtShare(option.normal.fit) })} · {waterLeftText(option.waterLeftM3, t, lang)}</div>
        <div className="hint">{t('plan.forField', { field: fieldName })}</div>
      </div>
      <button className="btn small" onClick={onPick} disabled={busy}>{t('alt.check')}</button>
    </div>
  );
}

function PlanCard({ plan, fieldName, onOpen }) {
  const { t } = useI18n();
  const { options } = plan.result;
  const level = fitLevel(options[0].normal.fit, shortFitOf(plan.result));
  return (
    <button className={`card plan-card level-${level}`} onClick={onOpen}>
      <div className="plan-card-head">
        <b>{t(`crops.${options[0].crop}`)}</b>
        <span className="plan-verdict"><span className="dot" /> {t(`verdict.${level}`)}</span>
      </div>
      <div className="hint">{fieldName} · {plan.date}</div>
    </button>
  );
}

// The result screen: the options side by side, then the field check, the season and the evidence.
function PlanDetail({ plan, onBack, onPick, onDelete, busy, error }) {
  const { t, lang } = useI18n();
  const { result } = plan;
  const { options, planEarnsMost, doubleCrop, fieldCheck, frostTrend, snow, dryYear, message } = result;
  const shortFit = shortFitOf(result);

  return (
    <div className="screen plan-detail">
      <div className="row top">
        <button className="btn small" onClick={onBack}>← {t('plan.back')}</button>
        <button className="btn small danger" onClick={() => window.confirm(t('plan.confirmDelete')) && onDelete()}>{t('plan.delete')}</button>
      </div>
      <ErrorText code={error} />
      <MessageBox message={message} />

      <div className="options">
        {options.map((o) => (
          <OptionCard key={o.kind} option={o} shortFit={shortFit} onPick={o.kind === 'plan' ? null : onPick} busy={busy} />
        ))}
      </div>
      {planEarnsMost && <p className="verdict-note good">✓ {t('option.earnsMost')}</p>}

      {doubleCrop && (
        <section className="card">
          <h3>{t('double.title')}</h3>
          <p>{t('double.text', { second: t(`crops.${doubleCrop.second}`), date: fmtDay(doubleCrop.wheatHarvest, lang), days: doubleCrop.windowDays })}</p>
          <p className="hint">
            {t('double.water', { mm: fmtInt(doubleCrop.netNeedMm, lang) })} · {waterLeftText(doubleCrop.waterLeftM3, t, lang)}
          </p>
        </section>
      )}

      <div className="columns">
        <div className="column">
          <section className="card">
            <h3>{t('check.title')}</h3>
            <FieldCheck check={fieldCheck} />
          </section>
          <PlanShare plan={plan} />
          <a className="btn hotline" href="tel:1210">{t('verdict.hotline')}</a>
        </div>

        <div className="column">
          <section className="card">
            <h3>{t('season.title')}</h3>
            <p>
              {t('season.snow', { basin: t(`basins.${snow.basin}`), level: t(`levelsInline.${snow.level}`), pct: fmtPct(snow.anomaly), month: snow.month })}{' '}
              <Badge source={t('sources.fldas')} />
            </p>
            <p className="hint">{t('season.dryYear', { pct: fmtPct(dryYear.anomaly), years: dryYear.years.join(', ') })}</p>
            <p>{frostTrend.significant ? t('season.frostEarlier', { days: frostTrend.daysEarlier }) : t('season.frostSame')}</p>
            {snow.south && <p className="verdict-note">{t('season.south')}</p>}
            <p className="note">{t('evidence.notForecast')}</p>
          </section>
          <details className="card">
            <summary>{t('evidence.title')}</summary>
            <Evidence result={result} />
          </details>
        </div>
      </div>
    </div>
  );
}
