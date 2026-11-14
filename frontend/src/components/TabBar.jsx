import { useState } from 'react';
import { useI18n } from '../i18n';
import { load, save } from '../lib/storage';
import Icon from './Icon';

const TABS = ['field', 'plan', 'agro', 'about'];

// Tabs at the bottom on phones. On wide screens a menu on the left: icons only by default,
// the arrow at the bottom opens it to show the names (see styles.css).
export default function TabBar({ tab, setTab }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(load('menuOpen', false));

  function toggle() {
    setOpen(!open);
    save('menuOpen', !open);
  }

  return (
    <nav className={open ? 'tabbar open' : 'tabbar'}>
      {TABS.map((id) => (
        <button key={id} className={tab === id ? 'on' : ''} onClick={() => setTab(id)} title={t(`tabs.${id}`)}>
          <Icon name={id} />
          <span>{t(`tabs.${id}`)}</span>
        </button>
      ))}
      <button className="menu-toggle" onClick={toggle} title={t(open ? 'menu.collapse' : 'menu.expand')} aria-label={t(open ? 'menu.collapse' : 'menu.expand')}>
        <Icon name={open ? 'collapse' : 'expand'} />
      </button>
    </nav>
  );
}
