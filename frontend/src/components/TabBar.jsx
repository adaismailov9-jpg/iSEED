import { useI18n } from '../i18n';

const ICONS = {
  field: 'M3 7l6-3 6 3 6-3v13l-6 3-6-3-6 3zM9 4v13M15 7v13',
  plan: 'M12 21v-9M12 12c0-4 3-6 7-6 0 4-3 6-7 6zM12 15c0-3-2-5-6-5 0 3 2 5 6 5zM5 21h14',
  about: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
};

// Bottom tabs on phones, top navigation on wide screens (see styles.css).
export default function TabBar({ tab, setTab }) {
  const { t } = useI18n();
  return (
    <nav className="tabbar">
      {Object.entries(ICONS).map(([id, path]) => (
        <button key={id} className={tab === id ? 'on' : ''} onClick={() => setTab(id)}>
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d={path} />
          </svg>
          {t(`tabs.${id}`)}
        </button>
      ))}
    </nav>
  );
}
