import { defineConfig } from '@playwright/test';

const apiPort = Number(process.env.WORKSPACE_TEST_API_PORT || 8012);
const apiUrl = `http://127.0.0.1:${apiPort}`;

export default defineConfig({
  testDir: './tests', workers: 1, timeout: 45000,
  use: { channel: process.env.WORKSPACE_TEST_BROWSER || 'chromium', baseURL: 'http://127.0.0.1:5274', viewport: { width: 1440, height: 1000 },
    screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  webServer: [
    { command: `${process.env.WORKSPACE_TEST_SYSTEM_PYTHON === '1' ? 'python' : 'uv run python'} tests/serve_workspace.py`, cwd: '../backend',
      url: `${apiUrl}/health`, timeout: 30000 },
    { command: 'npx vite --host 127.0.0.1 --port 5274 --strictPort',
      env: { BACKEND_URL: apiUrl, WORKSPACE_ISOLATED: '1' },
      url: 'http://127.0.0.1:5274', timeout: 30000 },
  ],
});
