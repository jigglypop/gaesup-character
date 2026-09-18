import { defineConfig, loadEnv } from 'vite';
import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  // Server-side dev proxy only: credentials never enter the browser bundle.
  const env = loadEnv(mode, fileURLToPath(new URL('../', import.meta.url)), '');
  const headers: Record<string, string> = { 'X-User-Id': env.CHARACTER_OWNER_ID || '1' };
  if (env.API_KEY) headers['X-API-Key'] = env.API_KEY;
  // LOCAL_BACKEND_URL is the explicit workspace handoff for an already-running Vite process.
  const target = process.env.WORKSPACE_ISOLATED === '1' ? process.env.BACKEND_URL : env.LOCAL_BACKEND_URL || process.env.BACKEND_URL;
  const proxy = { '/api': { target: target || 'http://127.0.0.1:8016', headers, timeout: 65000, proxyTimeout: 65000 } };
  return { plugins: [react()], resolve: { dedupe: ['react', 'react-dom', 'three', '@react-three/fiber'] },
    server: { proxy }, preview: { proxy }, build: { chunkSizeWarningLimit: 1000,
      rollupOptions: { input: { workspace: fileURLToPath(new URL('./index.html', import.meta.url)), avatar: fileURLToPath(new URL('./avatar.html', import.meta.url)) } } } };
});
