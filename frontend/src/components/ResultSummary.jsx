import { useEffect } from 'react';
import { useI18n } from '../i18n';
import { fitLevel, fmtDec, fmtInt, fmtShare, fmtSomK, fmtSomRange } from '../lib/format';
import { CropIcon } from './Art';

// The answer first, in one sentence with big numbers: what a dry year does to his plan.
// Then the options side by side on the numbers that matter. Every number comes from POST /farmer.
export default function ResultSummary({ result, shortFit }) {
  const { t, lang } = useI18n();
  const { options, planEarnsMost, field } = result;
  const plan = options[0];
  const crop = (id) => t(`crops.${id}`);
  const level = fitLevel(plan.dry.fit, shortFit);
  const others = options.slice(1);

  useEffect(() => {
    document.querySelector('.main')?.scrollTo(0, 0); // .main is the scrolling box (styles.css)
  }, [result]); // open at the answer, not where the questions were

  // Pointers to a better choice, only when the API's numbers show one.
  const richer = others.filter((o) => o.priceKnown && (!plan.priceKnown || o.dry.income.low > plan.dry.income.low))
    .sort((a, b) => b.dry.income.low - a.dry.income.low)[0];
  const saver = options.find((o) => o.highlight && o.kind !== 'plan');

  return (
    <>
      <section className={`card answer level-${level}`}>
        <div className="eyebrow">{t('result.for', { ha: fmtDec(field.areaHa, 2, lang), basin: t(`basins.${field.basin}`) })}</div>
        <div className="answer-top">
          <CropIcon id={plan.crop} size={76} />
          <div>
            <div className="answer-if">{t('summary.eyebrow')}</div>
            <h2 className="answer-title">{t(`summary.title.${level}`, { crop: crop(plan.crop) })}</h2>
          </div>
        </div>

        <div className="answer-stats">
          <div className="stat">
            <div className="stat-big">{fmtShare(plan.dry.fit)}</div>
            <div className="meter-track"><div className="meter-fill supply" style={{ width: fmtShare(plan.dry.fit) }} /></div>
            <div className="stat-label">{t('summary.water')}</div>
          </div>
          <div className="stat">
            {plan.priceKnown ? (
              <>
                <div className="stat-big">{fmtSomK(plan.dry.income, lang)}</div>
                <div className="stat-label">{t('summary.income')}</div>
                <div className="stat-note">{t('summary.incomeNormal', { income: fmtSomRange(plan.normal.income, lang) })}</div>
              </>
            ) : (
              <div className="stat-label">{t('option.noPrice')}</div>
            )}
          </div>
        </div>

        {(richer || saver || planEarnsMost) && (
          <ul className="answer-tips">
            {planEarnsMost && <li className="good">✓ {t('option.earnsMost')}</li>}
            {richer && <li><CropIcon id={richer.crop} size={28} /> {t(richer.waterLeftM3 < 0 ? 'summary.betterThirsty' : 'summary.better', { crop: crop(richer.crop), income: fmtSomK(richer.dry.income, lang), m3: fmtInt(-richer.waterLeftM3, lang) })}</li>}
            {saver && <li><span className="tip-drop" aria-hidden="true">💧</span> {t('summary.saves', { crop: crop(saver.crop), m3: fmtInt(saver.waterLeftM3, lang) })}</li>}
          </ul>
        )}
      </section>

      <section className="card compare-options">
        <h3>{t('summary.compare')}</h3>
        {options.map((o) => (
          <a key={o.kind} href={`#option-${o.kind}`} className={`cmp-row level-${fitLevel(o.dry.fit, shortFit)}${o.highlight ? ' best' : ''}`}>
            <CropIcon id={o.crop} size={44} />
            <div className="cmp-body">
              <div className="cmp-name">
                <b>{crop(o.crop)}</b>
                <span className="eyebrow">{t(`option.${o.kind}`)}</span>
              </div>
              <div className="cmp-water">
                <div className="meter-track"><div className="meter-fill supply" style={{ width: fmtShare(o.dry.fit) }} /></div>
                <span>{t('summary.waterShort', { pct: fmtShare(o.dry.fit) })}</span>
              </div>
              <div className="cmp-facts">
                <span className="cmp-income">{o.priceKnown ? fmtSomK(o.dry.income, lang) : t('option.noPrice')}</span>
                {o.kind !== 'plan' && (
                  <span className={o.waterLeftM3 >= 0 ? 'cmp-left plus' : 'cmp-left minus'}>
                    {t(o.waterLeftM3 >= 0 ? 'summary.leftMore' : 'summary.leftLess', { m3: fmtInt(Math.abs(o.waterLeftM3), lang) })}
                  </span>
                )}
              </div>
            </div>
          </a>
        ))}
      </section>
    </>
  );
}
