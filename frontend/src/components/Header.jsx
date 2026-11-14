import { useState } from 'react';
import { LANGS, useI18n } from '../i18n';
import { save } from '../lib/storage';
import Icon from './Icon';

// Logo on the left; languages, light/dark theme and the tour button on the right.
export default function Header({ user, onSignOut, showTour }) {
  const { t, lang, setLang } = useI18n();
  const [theme, setTheme] = useState(document.documentElement.dataset.theme);
  const other = theme === 'dark' ? 'light' : 'dark';

  function toggleTheme() {
    document.documentElement.dataset.theme = other;
    save('theme', other);
    setTheme(other);
  }

  return (
    <header className="header">
      <div className="brand">
        <img src="/art/logo.webp" alt="iSEED" className="logo" width="126" height="64" />
        <small>{t('app.tagline')}</small>
      </div>
      <div className="header-right">
        {user && (
          <button className="profile" onClick={() => window.confirm(t('profile.confirm')) && onSignOut()} title={t('profile.change')}>
            <Icon name="agro" size={18} />
            <span>{user.name} · {t(`role.${user.role}`)}</span>
          </button>
        )}
        <div className="lang" data-tour="lang">
          {LANGS.map((l) => (
            <button key={l} className={l === lang ? 'on' : ''} onClick={() => setLang(l)}>
              {t(`lang.${l}`)}
            </button>
          ))}
          <button className="theme" onClick={toggleTheme} title={t(`theme.${other}`)} aria-label={t(`theme.${other}`)}>
            <Icon name={other === 'light' ? 'sun' : 'moon'} size={16} />
          </button>
          {showTour && <button className="help" onClick={showTour} title={t('tour.replay')} aria-label={t('tour.replay')}>?</button>}
        </div>
      </div>
    </header>
  );
}
