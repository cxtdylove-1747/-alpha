export const readStoredString = (key, fallback = '') => {
  if (typeof window === 'undefined') {
    return fallback;
  }
  try {
    const value = window.localStorage.getItem(key);
    return typeof value === 'string' ? value : fallback;
  } catch (_) {
    return fallback;
  }
};

export const readStoredJson = (key, fallback = null) => {
  if (typeof window === 'undefined') {
    return fallback;
  }
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) {
      return fallback;
    }
    return JSON.parse(raw);
  } catch (_) {
    window.localStorage.removeItem(key);
    return fallback;
  }
};

export const writeStoredString = (key, value) => {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(key, String(value || ''));
};

export const writeStoredJson = (key, value) => {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(key, JSON.stringify(value));
};

export const removeStoredValue = (key) => {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.removeItem(key);
};
