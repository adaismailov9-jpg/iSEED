// VITE_USE_MOCK=false → real FastAPI backend at /api (same JSON as the mock).
import { mockApi } from './mock';

export const isMock = import.meta.env.VITE_USE_MOCK !== 'false';

async function request(path, body) {
  const res = await fetch(`/api${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: body && JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.message);
  return data;
}

const realApi = {
  getBasin: (lat, lon) => request(`/basin?lat=${lat}&lon=${lon}`),
  getHindcast: (basin) => request(`/hindcast?basin=${basin}`),
  check: (body, lang) => request('/check', { ...body, lang }),
};

export const api = isMock ? mockApi : realApi;
