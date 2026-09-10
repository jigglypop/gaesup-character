import { defineConfig, loadEnv } from 'vite';
import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  // Server-side dev proxy only: credentials never enter the browser bundle.
  const env = loadEnv(mode, fileURLToPath(new URL('../', import.meta.url)), '');
  const headers: Record<string, string> = { 'X-User-Id': env.CHARACTER_OWNER_ID || '1' };
  if (env.API_KEY) headers['X-API-Key'] = env.API_KEY;
  const proxy = { '/api': { target: process.env.BACKEND_URL || 'http://127.0.0.1:8000', headers } };
  return { plugins: [react()], resolve: { dedupe: ['react', 'react-dom', 'three', '@react-three/fiber'] },
    server: { proxy }, preview: { proxy }, build: { chunkSizeWarningLimit: 1000 } };
});
