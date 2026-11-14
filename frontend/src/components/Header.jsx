import { LANGS, useI18n } from '../i18n';
import { isMock } from '../api/client';

// Logo on the left, navigation (children) in the middle, languages on the right.
export default function Header({ children }) {
  const { t, lang, setLang } = useI18n();
  return (
    <header className="header">
      <div className="brand">
        <img src="/icon.svg" alt="" width="34" height="34" />
        <div>
          <b>iSEED.</b>
          <small>{isMock ? t('app.demo') : t('app.tagline')}</small>
        </div>
      </div>
      {children}
      <div className="lang">
        {LANGS.map((l) => (
          <button key={l} className={l === lang ? 'on' : ''} onClick={() => setLang(l)}>
            {t(`lang.${l}`)}
          </button>
        ))}
      </div>
    </header>
  );
}
