import { defineStore } from 'pinia';
import {
  readStoredJson,
  readStoredString,
  removeStoredValue,
  writeStoredJson,
  writeStoredString
} from '../utils/storage';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: readStoredString('accessToken', ''),
    user: readStoredJson('user', null)
  }),
  actions: {
    setAuth(payload) {
      const nextToken = String(payload?.access || '');
      const nextUser = payload?.user && typeof payload.user === 'object' ? payload.user : null;

      this.accessToken = nextToken;
      this.user = nextUser;

      if (nextToken) {
        writeStoredString('accessToken', nextToken);
      } else {
        removeStoredValue('accessToken');
      }

      if (nextUser) {
        writeStoredJson('user', nextUser);
      } else {
        removeStoredValue('user');
      }
    },
    clearAuth() {
      this.accessToken = '';
      this.user = null;
      removeStoredValue('accessToken');
      removeStoredValue('user');
    },
    setUser(user) {
      const nextUser = user && typeof user === 'object' ? user : null;
      this.user = nextUser;
      if (nextUser) {
        writeStoredJson('user', nextUser);
      } else {
        removeStoredValue('user');
      }
    }
  }
});

