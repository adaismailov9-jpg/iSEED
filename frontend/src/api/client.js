// The iSEED API (shapes in CLAUDE.md). Dev: Vite proxies /api to the backend on port 8000. Vercel: /api/*.
import { load, save } from '../lib/storage';

export class ApiError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code; // bad_input, not_signed_in, wrong_login, name_taken, no_basin, offline, …
  }
}

let token = load('session', null)?.token;

// Keep the signed-in user and token on the phone; null signs out.
export function rememberSession(session) {
  token = session?.token;
  save('session', session);
}

async function request(path, body, { auth = true } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (auth && token) headers.Authorization = `Bearer ${token}`;
  let res;
  try {
    res = await fetch(`/api${path}`, { method: body ? 'POST' : 'GET', headers, body: body && JSON.stringify(body) });
  } catch {
    throw new ApiError('offline', 'No connection to the server');
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(data.code ?? 'server', data.message);
  return data;
}

export const api = {
  register: (user) => request('/register', user, { auth: false }),
  login: (name, pin) => request('/login', { name, pin }, { auth: false }),
  health: () => request('/health'),
  basin: (lat, lon) => request(`/basin?lat=${lat}&lon=${lon}`),
  hindcast: (basin) => request(`/hindcast?basin=${basin}`),
  checkField: (geometry) => request('/fields', { geometry }, { auth: false }), // a look at the place, not saved
  farmer: (body) => request('/farmer', body),
  manager: (canal) => request('/manager', canal),
  myCanal: () => request('/manager'),
  postMessage: (text) => request('/manager/message', { text }),
  message: (village) => request(`/message?village=${encodeURIComponent(village)}`),
};
