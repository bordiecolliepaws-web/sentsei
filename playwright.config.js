import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests',
  timeout: 60000,
  retries: 1,
  use: {
    baseURL: 'http://localhost:8847',
    headless: true,
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium', channel: 'chromium', launchOptions: { args: ['--no-sandbox'] } } }],
});
