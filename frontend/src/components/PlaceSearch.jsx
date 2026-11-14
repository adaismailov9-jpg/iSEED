import { useState } from 'react';
import { useI18n } from '../i18n';

// Place search with OpenStreetMap Nominatim, limited to Kyrgyzstan.
// Searches only on submit (Nominatim allows at most 1 request per second, no autocomplete).
export default function PlaceSearch({ onPick }) {
  const { t, lang } = useI18n();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [message, setMessage] = useState('');

  async function search(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setMessage(t('common.loading'));
    try {
      const url = `https://nominatim.openstreetmap.org/search?format=json&countrycodes=kg&limit=5&accept-language=${lang}&q=${encodeURIComponent(query)}`;
      const found = await (await fetch(url)).json();
      setResults(found);
      setMessage(found.length ? '' : t('search.empty'));
    } catch {
      setMessage(t('search.error'));
    }
  }

  function pick(place) {
    onPick([Number(place.lat), Number(place.lon)]);
    setQuery(place.display_name.split(',')[0]);
    setResults([]);
  }

  return (
    <form className="search" onSubmit={search}>
      <div className="search-row">
        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('search.placeholder')} />
        <button className="btn small primary">{t('search.go')}</button>
      </div>
      {message && <p className="search-message">{message}</p>}
      {results.length > 0 && (
        <ul className="search-results">
          {results.map((place) => (
            <li key={place.place_id}>
              <button type="button" onClick={() => pick(place)}>{place.display_name}</button>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}
