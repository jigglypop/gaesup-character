import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests', workers: 1, timeout: 45000,
  use: { channel: 'chromium', baseURL: 'http://127.0.0.1:5274', viewport: { width: 1440, height: 1000 },
    screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  webServer: [
    { command: 'uv run python tests/serve_workspace.py', cwd: '../backend',
      url: 'http://127.0.0.1:8012/health', timeout: 30000 },
    { command: 'npx vite --host 127.0.0.1 --port 5274 --strictPort',
      env: { BACKEND_URL: 'http://127.0.0.1:8012' },
      url: 'http://127.0.0.1:5274', timeout: 30000 },
  ],
});
