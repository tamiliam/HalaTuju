/**
 * Playwright config for `npm run mobile-check` (Mobile M0). Run it through `npm run mobile-check`,
 * not `npx playwright test` directly: `run.mjs` clears the old results first and reads them after.
 *
 * ⚠ LOCAL ONLY, NOT IN CLOUD BUILD. A full run is ~200 browser visits; inside the deploy gate it
 * would cost build minutes on every push. It runs on the dev box before a UI change is pushed
 * (the sprint-close and small-change workflows say so), and the Jest static guards — which DO run
 * in the gate — hold the line between runs.
 *
 * When MOBILE_BASE is local (the default), Playwright starts `next dev` on that port with the
 * design sandbox on, or reuses a server already listening there. ⚠ `next dev` writes `.next/`:
 * do not run `next build` in this folder while it is up, and stop a second `next dev` in the same
 * folder first — two servers sharing `.next/` corrupt each other's output.
 */
import * as path from 'path'
import { defineConfig } from '@playwright/test'
import { BASE, isLocal, OUTPUT_DIR, WEB_ROOT } from './targets'

const port = new URL(BASE).port || '80'

export default defineConfig({
  testDir: __dirname,
  testMatch: /.*\.pw\.ts$/,
  outputDir: path.join(OUTPUT_DIR, 'test-results'),
  // The first visit to each route makes `next dev` compile it, which can take a while.
  timeout: 180_000,
  fullyParallel: true,
  workers: Number(process.env.MOBILE_WORKERS || 3),
  retries: 0,
  reporter: [['list']],
  use: { browserName: 'chromium', trace: 'off' },
  webServer: isLocal(BASE)
    ? {
      command: `npx next dev -p ${port}`,
      cwd: WEB_ROOT,
      url: `${BASE}/sandbox`,
      reuseExistingServer: true,
      timeout: 240_000,
      env: { NEXT_PUBLIC_SANDBOX: '1' },
      stdout: 'ignore',
      stderr: 'pipe',
    }
    : undefined,
})
