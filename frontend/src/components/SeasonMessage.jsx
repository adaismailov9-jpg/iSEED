import { useEffect, useState } from 'react';
import { useI18n } from '../i18n';
import { api } from '../api/client';

// The water manager's season message for the farmer's village (GET /message).
export default function SeasonMessage({ village }) {
  const [message, setMessage] = useState(null);

  useEffect(() => {
    api.message(village).then((res) => setMessage(res.message)).catch(() => {});
  }, [village]);

  return <MessageBox message={message} />;
}

// A message already known, e.g. the one in the POST /farmer answer. Nothing when null.
export function MessageBox({ message }) {
  const { t } = useI18n();
  if (!message) return null;
  return (
    <section className="season-message">
      <div className="eyebrow">{t('message.fromManager', { name: message.manager, date: message.date })}</div>
      <p>{message.text}</p>
    </section>
  );
}
