import { useState } from 'react';
import { useI18n } from '../i18n';
import { load, save } from '../lib/storage';
import Icon from './Icon';

// Tabs at the bottom on phones. On wide screens a menu on the left: icons only by default,
// the arrow at the bottom opens it to show the names (see styles.css).
export default function TabBar({ tabs, tab, setTab }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(load('menuOpen', false));

  function toggle() {
    setOpen(!open);
    save('menuOpen', !open);
  }

  return (
    <nav className={open ? 'tabbar open' : 'tabbar'}>
      {tabs.map((id) => (
        <button key={id} className={tab === id ? 'on' : ''} onClick={() => setTab(id)} data-tour={id} title={t(`tabs.${id}`)}>
          <Icon name={id} />
          <span>{t(`tabs.${id}`)}</span>
        </button>
      ))}
      <button className="menu-toggle" onClick={toggle} title={t(open ? 'menu.collapse' : 'menu.expand')} aria-label={t(open ? 'menu.collapse' : 'menu.expand')}>
        <Icon name={open ? 'collapse' : 'expand'} />
        <span>{t('menu.collapse')}</span>
      </button>
    </nav>
  );
}
