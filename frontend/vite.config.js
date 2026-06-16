import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const backendOrigin = (env.VITE_BACKEND_ORIGIN || 'http://127.0.0.1:8000').trim();
  const base = (env.VITE_BASE || '/').trim() || '/';

  return {
    plugins: [vue()],
    base,
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: backendOrigin,
          changeOrigin: true
        },
        '/media': {
          target: backendOrigin,
          changeOrigin: true
        }
      }
    }
  };
});

