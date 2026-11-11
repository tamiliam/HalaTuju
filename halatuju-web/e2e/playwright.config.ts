/**
 * Playwright config for the browser WALKS (audit sprint A4.6: TD-070, TD-092, TD-112).
 *
 *   npx playwright test -c e2e/playwright.config.ts
 *
 * ⛔ LOCAL ONLY. The base address is fixed to this machine (port 3200) and cannot be pointed at the
 * live site: there is no environment variable for it on purpose. Playwright starts its own
 * `next dev` here and never reuses a server already on the port (another checkout's branch would be
 * walked instead of this one).
 *
 * ⛔ NO SECRETS, NO REAL ACCOUNTS, NO EMAIL. `next dev` gets made-up addresses for the API and for
 * Supabase (nothing listens on either), and `hermetic.ts` answers or blocks every request the page
 * sends that is not for this server. A walk that needs a real sign-in (TD-070, TD-112) runs only in
 * the full-stack mode below, against a LOCAL Supabase and a LOCAL API — otherwise it is skipped and
 * says why.
 *
 * Full-stack mode (optional, for the sign-in walks): set WALK_SUPABASE_URL + WALK_SUPABASE_ANON_KEY
 * to a local `supabase start` stack and WALK_API_URL to a local `manage.py runserver` (development
 * settings: email goes to the console). Each must be a localhost address or the walks refuse to run.
 * ⚠ `next dev` writes `.next/`: do not run `next build` or a second `next dev` in this folder meanwhile.
 */
import * as path from 'path'
import { defineConfig } from '@playwright/test'
import { WALK_BASE, WALK_PORT, appApiUrl, appSupabaseUrl, appSupabaseKey } from './hermetic'

export default defineConfig({
  testDir: __dirname,
  testMatch: /.*\.walk\.ts$/,
  outputDir: path.join(__dirname, 'output', 'test-results'),
  timeout: 240_000,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: { browserName: 'chromium', baseURL: WALK_BASE, trace: 'off' },
  webServer: {
    command: `npx next dev -p ${WALK_PORT}`,
    cwd: path.resolve(__dirname, '..'),
    url: `${WALK_BASE}/sponsor`,
    reuseExistingServer: false,
    timeout: 240_000,
    // Process env wins over any .env file Next would load, so these made-up (or local) addresses
    // are the only ones the page can know.
    env: {
      NEXT_PUBLIC_API_URL: appApiUrl(),
      NEXT_PUBLIC_SUPABASE_URL: appSupabaseUrl(),
      NEXT_PUBLIC_SUPABASE_ANON_KEY: appSupabaseKey(),
      NEXT_PUBLIC_TURNSTILE_SITE_KEY: '',
    },
    stdout: 'ignore',
    stderr: 'pipe',
  },
})
