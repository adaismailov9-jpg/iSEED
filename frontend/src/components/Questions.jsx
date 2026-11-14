import { useState } from 'react';
import { useI18n } from '../i18n';
import { CROPS } from '../data/crops';

const PREVIOUS_CROPS = [...CROPS.map((c) => c.id), 'wheat', 'none'];
const PLANNED_CROPS = [...CROPS.map((c) => c.id), 'unknown'];

// The questions in order. The canal question appears only for canal or pump water.
function buildSteps(answers, t) {
  const crop = (id) => t(id === 'unknown' ? 'q.notSure' : `crops.${id}`);
  const onCanal = answers.source === 'river' || answers.source === 'pump';
  return [
    { key: 'previous', title: t('q.previous'), hint: t('q.previousHint'), options: PREVIOUS_CROPS, label: crop },
    { key: 'plan', title: t('q.plan'), hint: t('q.planHint'), options: PLANNED_CROPS, label: crop },
    { key: 'source', title: t('q.source'), options: ['river', 'pump', 'well', 'rain'], label: (id) => t(`q.${id}`) },
    ...(onCanal ? [{ key: 'canal', title: t('q.canal'), options: ['start', 'middle', 'end'], label: (id) => t(`q.canal_${id}`) }] : []),
    { key: 'usual', title: t('q.usual'), options: ['enough', 'sometimes', 'often', 'unknown'], label: (id) => t(id === 'unknown' ? 'q.notSure' : `q.${id}`) },
    { key: 'soil', title: t('q.soil'), options: ['sandy', 'medium', 'clay', 'unknown'], label: (id) => t(`soil.${id}`) },
    { key: 'priority', title: t('q.priority'), options: ['water', 'income', 'soil'], label: (id) => t(`priority.${id}`) },
  ];
}

// One question open at a time: answering it closes it and opens the next unanswered one.
export default function Questions({ answers, setAnswers, onSubmit, hasField, busy }) {
  const { t } = useI18n();
  const steps = buildSteps(answers, t);
  const firstEmpty = (list) => list.findIndex((step) => !answers[step.key]);
  const [open, setOpen] = useState(firstEmpty(steps)); // -1 = all answered
  const allAnswered = firstEmpty(steps) === -1;

  function choose(key, value) {
    const next = { ...answers, [key]: value };
    setAnswers(next);
    setOpen(buildSteps(next, t).findIndex((step) => !next[step.key]));
  }

  return (
    <div className="steps">
      {steps.map((step, i) =>
        i === open ? (
          <fieldset key={step.key} className="step open">
            <legend><span className="step-num">{i + 1}</span>{step.title}</legend>
            {step.hint && <p className="hint">{step.hint}</p>}
            <div className="chips">
              {step.options.map((id) => (
                <button key={id} className={answers[step.key] === id ? 'chip on' : 'chip'} onClick={() => choose(step.key, id)}>
                  {step.label(id)}
                </button>
              ))}
            </div>
          </fieldset>
        ) : (
          <button key={step.key} className="step closed" onClick={() => setOpen(i)} disabled={!answers[step.key]}>
            <span className={answers[step.key] ? 'step-num done' : 'step-num'}>{answers[step.key] ? '✓' : i + 1}</span>
            <span className="step-title">{step.title}</span>
            {answers[step.key] && <b>{step.label(answers[step.key])}</b>}
          </button>
        )
      )}

      {allAnswered && (
        <div className="submit">
          {!hasField && <p className="hint strong">{t('q.needField')}</p>}
          <button className="btn clay block" onClick={onSubmit} disabled={!hasField || busy}>
            {busy ? t('common.loading') : t('q.submit')} <span className="arrow">↗</span>
          </button>
          <p className="hint">{t('q.springOnly')}</p>
        </div>
      )}
    </div>
  );
}
