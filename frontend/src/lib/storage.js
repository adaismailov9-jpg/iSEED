// localStorage can throw (private mode); the app must still work without it.
export function load(key, fallback = null) {
  try {
    return JSON.parse(localStorage.getItem(`iseed:${key}`)) ?? fallback;
  } catch {
    return fallback;
  }
}

export function save(key, value) {
  try {
    localStorage.setItem(`iseed:${key}`, JSON.stringify(value));
  } catch {
    // ignore
  }
}
