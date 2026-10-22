import { defineConfig } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
const root = path.resolve(__dirname, '..');
const session = JSON.parse(fs.readFileSync(path.join(root, '.venv/e1/session.json'), 'utf8'));
export default defineConfig({
  testDir: './tests', workers: 1, retries: 0, timeout: 180_000,
  expect: { timeout: 15_000 },
  outputDir: path.join(root, 'output/playwright/e1/results'),
  reporter: [['list'], ['json', { outputFile: path.join(root, 'output/playwright/e1/results.json') }]],
  use: { baseURL: session.baseURL, viewport: { width: 1440, height: 1000 },
    browserName: 'chromium', timezoneId: 'Africa/Casablanca',
    screenshot: 'only-on-failure', trace: 'off', video: 'off' },
});
