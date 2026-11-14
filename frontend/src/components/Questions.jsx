import { useState } from 'react';
import { useI18n } from '../i18n';
import { CROP_IDS } from '../data/ids';
import { CanalDiagram, CropIcon, SoilIcon, SourceIcon } from './Art';

const drops = (n) => (
  <span className="drops" aria-hidden="true">{'💧'.repeat(n)}</span>
);
const NORMAL_YEAR_ICON = { enough: drops(3), sometimes: drops(2), often: drops(1), unknown: <b className="q-mark">?</b> };

// The questions in order, in the shape of POST /farmer. The canal question appears only for canal or pump water.
// Each answer has a small picture, so the choice is quick to read on a phone.
export function buildSteps(answers, t) {
  const crop = (id) => t(`crops.${id}`);
  const cropIcon = (id) => <CropIcon id={id} size={36} />;
  const onCanal = answers.source === 'gravity' || answers.source === 'pump';
  return [
    { key: 'previous', title: t('q.previous'), hint: t('q.previousHint'), options: [...CROP_IDS, 'none'], label: crop, icon: cropIcon, tiles: true },
    { key: 'previous2', title: t('q.previous2'), hint: t('q.previous2Hint'), options: [...CROP_IDS, 'none'], label: crop, icon: cropIcon, tiles: true },
    { key: 'plan', title: t('q.plan'), hint: t('q.planHint'), options: CROP_IDS, label: crop, icon: cropIcon, tiles: true },
    { key: 'winterWheat', title: t('q.winterWheat'), hint: t('q.winterWheatHint'), options: ['yes', 'no'], label: (id) => t(`q.${id}`), icon: (id) => <CropIcon id={id === 'yes' ? 'wheat' : 'none'} size={36} /> },
    { key: 'source', title: t('q.source'), options: ['gravity', 'pump', 'well'], label: (id) => t(`q.${id}`), icon: (id) => <SourceIcon id={id} size={40} />, tiles: true },
    ...(onCanal ? [{ key: 'position', title: t('q.position'), options: ['start', 'middle', 'end'], label: (id) => t(`position.${id}`), canal: true }] : []),
    { key: 'normalYear', title: t('q.normalYear'), options: ['enough', 'sometimes', 'often', 'unknown'], label: (id) => t(`q.${id}`), icon: (id) => NORMAL_YEAR_ICON[id] },
    { key: 'soil', title: t('q.soil'), hint: t('q.soilHint'), options: ['sandy', 'medium', 'clay', 'unknown'], label: (id) => t(`soil.${id}`), icon: (id) => <SoilIcon id={id} size={36} />, tiles: true },
  ];
}

// One question open at a time: answering it closes it and opens the next unanswered one.
export default function Questions({ answers, setAnswers, onSubmit, hasField, busy }) {
  const { t } = useI18n();
  const steps = buildSteps(answers, t);
  const firstEmpty = (list) => list.findIndex((step) => !answers[step.key]);
  const [open, setOpen] = useState(firstEmpty(steps)); // -1 = all answered
  const allAnswered = firstEmpty(steps) === -1;
  const done = steps.filter((step) => answers[step.key]).length;

  function choose(key, value) {
    const next = { ...answers, [key]: value };
    setAnswers(next);
    setOpen(buildSteps(next, t).findIndex((step) => !next[step.key]));
  }

  return (
    <div className="steps">
      <div className="q-progress" aria-label={t('q.progress', { n: done, of: steps.length })}>
        <span>{t('q.progress', { n: done, of: steps.length })}</span>
        <div className="meter-track"><div className="meter-fill" style={{ width: `${(done / steps.length) * 100}%` }} /></div>
      </div>

      {steps.map((step, i) =>
        i === open ? (
          <fieldset key={step.key} className="step open">
            <legend><span className="step-num">{i + 1}</span>{step.title}</legend>
            {step.hint && <p className="hint">{step.hint}</p>}
            {step.canal && (
              <div className="q-canal">
                <CanalDiagram you={answers.position || null} width={280} labels={{ title: step.title }} />
              </div>
            )}
            <div className={step.tiles ? 'chips tiles' : 'chips'}>
              {step.options.map((id) => (
                <button key={id} className={answers[step.key] === id ? 'chip on' : 'chip'} onClick={() => choose(step.key, id)} aria-pressed={answers[step.key] === id}>
                  {step.icon && <span className="chip-icon">{step.icon(id)}</span>}
                  <span>{step.label(id)}</span>
                </button>
              ))}
            </div>
          </fieldset>
        ) : (
          <button key={step.key} className="step closed" onClick={() => setOpen(i)} disabled={!answers[step.key]}>
            <span className={answers[step.key] ? 'step-num done' : 'step-num'}>{answers[step.key] ? '✓' : i + 1}</span>
            <span className="step-title">{step.title}</span>
            {answers[step.key] && (
              <b className="step-answer">
                {step.icon && <span className="chip-icon small">{step.icon(answers[step.key])}</span>}
                {step.label(answers[step.key])}
              </b>
            )}
          </button>
        )
      )}

      {allAnswered && (
        <div className="submit">
          {!hasField && <p className="hint strong">{t('q.needField')}</p>}
          <button className="btn clay block big-cta" onClick={onSubmit} disabled={!hasField || busy}>
            {busy ? t('common.loading') : t('q.submit')} <span className="arrow">↗</span>
          </button>
        </div>
      )}
    </div>
  );
}
