import { useI18n } from '../i18n';
import { fmtM3, fmtRatio } from '../lib/format';
import { SOURCES } from '../data/rules';
import Badge from './Badge';

// The verdict text comes from the API; this component only styles it.
export default function Verdict({ result }) {
  const { t, lang } = useI18n();
  const { verdict, chosen, tip, evidence, input } = result;
  const max = Math.max(chosen.needM3, chosen.supplyM3, 1);
  const label = input.crop ? t('verdict.yourChoice') : input.previous && t('verdict.recommended', { previous: t(`crops.${input.previous}`) });

  const bar = (label, value, className) => (
    <div className="meter-row">
      <span>{label}</span>
      <div className="meter-track">
        <div className={`meter-fill ${className}`} style={{ width: `${(value / max) * 100}%` }} />
      </div>
      <b>{fmtM3(value, lang)} {t('units.m3')}</b>
    </div>
  );

  return (
    <section className={`card verdict level-${verdict.level}`}>
      {label && <div className="eyebrow">{label}</div>}
      <h2 className="verdict-crop">{t(`crops.${chosen.id}`)}</h2>
      <div className="verdict-head">
        <span className="dot" />
        <strong>{t(`verdict.${verdict.level}`)}</strong>
        <small>{t('verdict.ratio')} {fmtRatio(chosen.ratio, lang)}</small>
      </div>
      <p className="sentence">{verdict.sentence}</p>
      <p>{verdict.reason}</p>

      <div className="meter">
        {bar(t('verdict.need'), chosen.needM3, 'need')}
        {bar(t('verdict.supply'), chosen.supplyM3, 'supply')}
        <Badge source={`${SOURCES.cropNeed}; ${SOURCES.base}`} />
      </div>

      <p className="hint">{t('verdict.season', { year: evidence.basin.year })}</p>
      {result.notes?.map((note) => (
        <p key={note.text} className={`verdict-note ${note.kind}`}>{note.kind === 'good' ? '✓' : '⚠'} {note.text}</p>
      ))}
      <p className="tip">
        <b>{t('verdict.tip')}:</b> {tip}
      </p>
    </section>
  );
}
