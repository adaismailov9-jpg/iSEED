import { useState } from 'react';
import { useI18n } from '../i18n';
import { fmtDec, fmtShare, fmtSomRange } from '../lib/format';
import Icon from './Icon';

// The plan as plain text, for messengers and the clipboard.
function planText(plan, t, lang) {
  const { field, options } = plan.result;
  const lines = [
    `${t('share.heading')} · ${plan.date}`,
    `${t('field.area')}: ${fmtDec(field.areaHa, 2, lang)} ${t('units.ha')} · ${t(`basins.${field.basin}`)}`,
  ];
  for (const o of options) {
    const income = (year) => (o.priceKnown ? ` · ${fmtSomRange(o[year].income, lang)} ${t('units.som')}` : '');
    lines.push(
      '',
      `${t(`option.${o.kind}`)}: ${t(`crops.${o.crop}`)}`,
      `${t('option.normal')}: ${t('option.water', { pct: fmtShare(o.normal.fit) })}${income('normal')}`,
      `${t('option.dry')}: ${t('option.water', { pct: fmtShare(o.dry.fit) })}${income('dry')}`
    );
  }
  return lines.join('\n');
}

// Save the plan as PDF (the browser's print dialog) or send it as text.
export default function PlanShare({ plan }) {
  const { t, lang } = useI18n();
  const [copied, setCopied] = useState(false);
  const text = encodeURIComponent(planText(plan, t, lang));

  async function copy() {
    try {
      await navigator.clipboard.writeText(planText(plan, t, lang));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // no clipboard (old browser or not https): nothing to do
    }
  }

  return (
    <section className="card share">
      <h3>{t('share.title')}</h3>
      <div className="share-buttons">
        <button className="btn" onClick={() => window.print()}><Icon name="pdf" /> PDF</button>
        <a className="btn" href={`https://wa.me/?text=${text}`} target="_blank" rel="noreferrer"><Icon name="whatsapp" /> WhatsApp</a>
        <a className="btn" href={`https://t.me/share/url?url=${encodeURIComponent(location.origin)}&text=${text}`} target="_blank" rel="noreferrer"><Icon name="telegram" /> Telegram</a>
        <button className="btn" onClick={copy}><Icon name={copied ? 'check' : 'copy'} /> {t(copied ? 'share.copied' : 'share.copy')}</button>
      </div>
    </section>
  );
}
