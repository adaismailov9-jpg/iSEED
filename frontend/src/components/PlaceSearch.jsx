import { useEffect, useState } from 'react';
import { useI18n } from '../i18n';

// Place search with suggestions while typing. Photon (OpenStreetMap data) allows search-as-you-type;
// Nominatim does not. Results are limited to Kyrgyzstan and to 3 suggestions.
const KYRGYZSTAN_BOX = '69.2,39.1,80.3,43.3';
const MAX_SUGGESTIONS = 3;

const placeName = (p) => [p.name, p.county ?? p.state].filter(Boolean).join(', ');

export default function PlaceSearch({ onPick }) {
  const { t, lang } = useI18n();
  const [query, setQuery] = useState('');
  const [picked, setPicked] = useState(''); // text of the chosen place: don't search it again
  const [results, setResults] = useState([]);
  const [message, setMessage] = useState('');

  // Search 300 ms after the last key press; a newer search cancels the older one.
  useEffect(() => {
    setResults([]);
    setMessage('');
    if (query.trim().length < 2 || query === picked) return;

    const request = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const url = `https://photon.komoot.io/api/?limit=8&bbox=${KYRGYZSTAN_BOX}&lang=${lang === 'en' ? 'en' : 'default'}&q=${encodeURIComponent(query)}`;
        const { features } = await (await fetch(url, { signal: request.signal })).json();
        const names = new Set();
        const places = features
          .filter((f) => f.properties.countrycode === 'KG')
          .filter((f) => !names.has(placeName(f.properties)) && names.add(placeName(f.properties))) // drop duplicates
          .slice(0, MAX_SUGGESTIONS);
        setResults(places);
        if (places.length === 0) setMessage(t('search.empty'));
      } catch (e) {
        if (e.name !== 'AbortError') setMessage(t('search.error'));
      }
    }, 300);

    return () => {
      clearTimeout(timer);
      request.abort();
    };
  }, [query, picked, lang]); // eslint-disable-line react-hooks/exhaustive-deps

  function pick(place) {
    const [lon, lat] = place.geometry.coordinates;
    const name = placeName(place.properties);
    onPick([lat, lon]);
    setPicked(name);
    setQuery(name);
  }

  return (
    <form
      className="search"
      onSubmit={(e) => {
        e.preventDefault();
        if (results[0]) pick(results[0]); // Enter picks the first suggestion
      }}
    >
      <label className="search-row">
        <svg className="search-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
          <circle cx="11" cy="11" r="7" />
          <path d="M20 20l-4-4" />
        </svg>
        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('search.placeholder')} aria-label={t('search.placeholder')} />
      </label>

      {message && <p className="search-message">{message}</p>}
      {results.length > 0 && (
        <ul className="search-results">
          {results.map((place) => (
            <li key={place.properties.osm_id}>
              <button type="button" onClick={() => pick(place)}>
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z" />
                  <circle cx="12" cy="10" r="2.5" />
                </svg>
                {placeName(place.properties)}
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}
