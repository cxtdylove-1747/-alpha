import axios from 'axios';

const normalizeOrigin = (value) => String(value || '').trim().replace(/\/+$/, '');
const backendOrigin = normalizeOrigin(import.meta.env.VITE_BACKEND_ORIGIN);
const apiBase = String(import.meta.env.VITE_API_BASE || '').trim()
  || (backendOrigin ? `${backendOrigin}/api` : '/api');

const request = axios.create({
  baseURL: apiBase,
  timeout: 300000
});

const notifyError = (message) => {
  if (typeof window === 'undefined') {
    return;
  }
  window.dispatchEvent(new CustomEvent('app:notify', {
    detail: {
      type: 'error',
      message
    }
  }));
};

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

request.interceptors.response.use(
  (res) => {
    const payload = res.data;
    if (payload && typeof payload === 'object' && Object.prototype.hasOwnProperty.call(payload, 'code') && Object.prototype.hasOwnProperty.call(payload, 'data')) {
      return payload.data;
    }
    return payload;
  },
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem('accessToken');
      localStorage.removeItem('user');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }

    const message = !error?.response
      ? '网络请求失败'
      : (error?.response?.data?.message || error?.response?.data?.detail || '出了些小问题');

    notifyError(message);
    return Promise.reject(error);
  }
);

export default request;

