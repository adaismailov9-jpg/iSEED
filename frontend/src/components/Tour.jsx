import { useLayoutEffect, useState } from 'react';
import { useI18n } from '../i18n';

// Each step highlights the element with data-tour="<id>".
const STEPS = [
  { id: 'field', title: 'tabs.field' },
  { id: 'plan', title: 'tabs.plan' },
  { id: 'agro', title: 'tabs.agro' },
  { id: 'canal', title: 'tabs.canal' },
  { id: 'about', title: 'tabs.about' },
  { id: 'lang', title: 'tour.langTitle' },
];
const CARD_WIDTH = 340;
const GAP = 16;

// Where the card goes: right of a side menu, above the bottom tabs, otherwise below the target.
function cardPlace(r) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const width = Math.min(CARD_WIDTH, vw - 2 * GAP);
  const left = Math.min(Math.max(r.left, GAP), vw - width - GAP);
  if (r.right + GAP + width < vw && r.left < vw / 3) return { width, left: r.right + GAP, top: Math.max(r.top - 20, GAP) };
  if (r.top > vh / 2) return { width, left, bottom: vh - r.top + GAP };
  return { width, left, top: r.bottom + GAP };
}

export default function Tour({ onClose }) {
  const { t, lang } = useI18n();
  const [steps, setSteps] = useState([]);
  const [index, setIndex] = useState(0);
  const [rect, setRect] = useState(null);
  const step = steps[index];
  const last = index === steps.length - 1;

  // Only the steps whose element is on screen (the farmer and the water manager have different tabs).
  useLayoutEffect(() => setSteps(STEPS.filter((s) => document.querySelector(`[data-tour="${s.id}"]`))), []);

  // Measure the target now and again when the window size changes.
  useLayoutEffect(() => {
    if (!step) return;
    const measure = () => setRect(document.querySelector(`[data-tour="${step.id}"]`)?.getBoundingClientRect() ?? null);
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [step, lang]);

  if (!step || !rect) return null;

  return (
    <div className="tour">
      <div className="tour-ring" style={{ left: rect.left - 6, top: rect.top - 6, width: rect.width + 12, height: rect.height + 12 }} />
      <div className="tour-card" style={cardPlace(rect)} role="dialog" aria-label={t(step.title)}>
        <div className="tour-head">
          <span className="tour-mascot" aria-hidden="true">🌱</span>
          <div>
            <small>{t('tour.step', { n: index + 1, total: steps.length })}</small>
            <h3>{t(step.title)}</h3>
          </div>
        </div>
        <p>{t(`tour.${step.id}`)}</p>
        <div className="tour-actions">
          {!last && <button className="link" onClick={onClose}>{t('tour.skip')}</button>}
          <button className="btn primary" onClick={() => (last ? onClose() : setIndex(index + 1))}>
            {t(last ? 'tour.done' : 'tour.next')}
          </button>
        </div>
      </div>
    </div>
  );
}
