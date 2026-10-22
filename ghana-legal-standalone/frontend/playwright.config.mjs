import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 45000,
  workers: 1,
  reporter: 'list',
  outputDir: '../test-results/browser',
  use: { baseURL: 'http://127.0.0.1:5176', browserName: 'chromium', screenshot: 'only-on-failure' },
  webServer: [
    {
      command: `"${process.env.LEGAL_TEST_PYTHON || 'python'}" -m uvicorn legal_app.main:app --app-dir ../backend --host 127.0.0.1 --port 8012`,
      url: 'http://127.0.0.1:8012/api/health',
      env: { LEGAL_DATA_DIR: process.env.LEGAL_TEST_DATA_DIR || '../test-results/workspace', GROQ_API_KEY: '', LEGAL_CORS_ORIGINS: 'http://127.0.0.1:5176' },
    },
    {
      command: 'npm run dev -- --port 5176',
      url: 'http://127.0.0.1:5176',
      env: { VITE_API_BASE_URL: 'http://127.0.0.1:8012' },
    },
  ],
});
