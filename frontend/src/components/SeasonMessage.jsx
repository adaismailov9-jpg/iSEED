import { useI18n } from '../i18n';
import { load } from '../lib/storage';

// The water manager's message for the season, shown to farmers (same phone until there is a server).
export default function SeasonMessage() {
  const { t } = useI18n();
  const message = load('seasonMessage', null);
  if (!message) return null;
  return (
    <section className="season-message">
      <div className="eyebrow">{t('message.fromManager', { name: message.from, date: message.date })}</div>
      <p>{message.text}</p>
    </section>
  );
}
