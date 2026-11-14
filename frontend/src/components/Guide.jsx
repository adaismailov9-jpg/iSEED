import { useState } from 'react';
import { useI18n } from '../i18n';
import { load, save } from '../lib/storage';

const FACE = { farmer: '/art/farmer-face.webp', manager: '/art/mirab-face.webp' };

// The farmer or the mirab, depending on the user's role, with a tip for what is on screen now.
// Tips can be hidden; the face stays as a small button to bring them back.
export default function Guide({ role, tip, vars }) {
  const { t } = useI18n();
  const [hidden, setHidden] = useState(load('guideHidden', false));

  function toggle(next) {
    setHidden(next);
    save('guideHidden', next);
  }

  if (hidden) {
    return (
      <button className="guide-mini" onClick={() => toggle(false)} title={t('guide.show')} aria-label={t('guide.show')}>
        <img src={FACE[role]} alt="" />
      </button>
    );
  }
  return (
    <aside className={`guide guide-${role}`} aria-live="polite">
      <img src={FACE[role]} alt="" className="guide-face" />
      <div className="guide-bubble">
        <b className="guide-name">{t(`guide.name.${role}`)}</b>
        <p key={tip}>{t(`guide.${tip}`, vars)}</p>
      </div>
      <button className="guide-close" onClick={() => toggle(true)} title={t('guide.hide')} aria-label={t('guide.hide')}>×</button>
    </aside>
  );
}
