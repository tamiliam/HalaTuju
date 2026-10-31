/**
 * `npm run mobile-check` — every public page and every sandbox surface, at 360 and 390 px, in
 * English, Malay and Tamil, in a real (Chromium, phone-emulated) browser. One test per cell.
 *
 * Named `*.pw.ts`, not `*.spec.ts`: Jest's default pattern would pick up a `.spec.ts` and run it.
 *
 * ⚠ READ-ONLY, ENFORCED HERE RATHER THAN HOPED FOR. It never signs in and never submits:
 *   - every request that is not GET/HEAD/OPTIONS is aborted before it leaves the browser;
 *   - Supabase auth (`/auth/v1/`) is aborted — otherwise every visit would MINT AN ANONYMOUS USER
 *     on the real project (AuthProvider does that on mount), a hundred rows per run;
 *   - the Turnstile challenge is aborted, since nothing here needs a captcha token.
 * Pages are measured as an anonymous visitor whose sign-in failed quietly, which is how they
 * render for one.
 *
 * Each cell writes its numbers to `output/results/` (run.mjs reads them afterwards to print the
 * improvements and, with `--update`, rewrite the baseline) and a screenshot to
 * `output/screenshots/`. Both are gitignored.
 */
import * as fs from 'fs'
import * as path from 'path'
import { expect, test, type Page } from '@playwright/test'
import { measurePage, type Measurement } from './measure'
import {
  BASE, EXPECTED_LANG, LOCALE_KEY, LOCALES, RESULTS_DIR, SANDBOX_ON, SHOTS_DIR, WIDTHS,
  cellKey, fileSafe, publicTargets, readBaseline, sandboxSlugs, sandboxTargets, worseThan,
  type Locale, type Target,
} from './targets'

const BASELINE = readBaseline()
const PHONE_UA = 'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) '
  + 'Chrome/120.0.0.0 Mobile Safari/537.36'

test.describe.configure({ mode: 'parallel' })

/** Blocks writes and sign-ins; returns a probe that says whether the API itself failed to answer. */
async function readOnly(page: Page): Promise<() => string[]> {
  const aborted = new Set<string>()
  await page.route('**/*', (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const write = !['GET', 'HEAD', 'OPTIONS'].includes(req.method())
    if (write || url.pathname.startsWith('/auth/v1/') || url.hostname === 'challenges.cloudflare.com') {
      aborted.add(req.url())
      return route.abort()
    }
    return route.continue()
  })
  const apiFailures: string[] = []
  page.on('requestfailed', (req) => {
    if (aborted.has(req.url())) return
    if (/\/api\/v1\//.test(req.url())) apiFailures.push(`${req.method()} ${req.url()} — ${req.failure()?.errorText}`)
  })
  return () => apiFailures
}

async function measureCell(page: Page, target: Target, locale: Locale): Promise<Measurement> {
  const apiFailures = await readOnly(page)
  await page.addInitScript(([key, value]) => {
    try { window.localStorage.setItem(key, value) } catch { /* storage blocked: the lang wait fails loudly */ }
  }, [LOCALE_KEY, locale])

  await page.goto(target.url, { waitUntil: 'networkidle', timeout: 90_000 })
  // ⚠ WAIT FOR THE WORDS, NOT THE LOAD EVENT. The server always sends English (it cannot read
  // localStorage); the chosen catalogue arrives after hydration and only then does `<html lang>`
  // change. A snapshot before that measures the English page in every column — the lesson from
  // the first live probe, where pre-hydration numbers looked fine and were not.
  await page.waitForFunction((lang) => document.documentElement.lang === lang, EXPECTED_LANG[locale],
    { timeout: 30_000 })
  await page.waitForLoadState('networkidle')
  await page.evaluate(() => document.fonts.ready.then(() => undefined))
  await page.evaluate(() => new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => r()))))

  const failures = apiFailures()
  if (target.kind === 'public' && failures.length) {
    throw new Error('The API did not answer, so this page was drawn without its data and measuring it '
      + 'would record a different screen. Run halatuju_api locally, or measure public pages from the '
      + `live site: MOBILE_PUBLIC_BASE=https://halatuju.xyz npm run mobile-check\n  ${failures.slice(0, 3).join('\n  ')}`)
  }
  // On a sandbox surface, measure the surface (inside <main>), not the sandbox's own picker chrome.
  return page.evaluate(measurePage, target.kind === 'sandbox' ? 'main' : 'body')
}

const targets = [...publicTargets(), ...sandboxTargets()]

for (const target of targets) {
  for (const width of WIDTHS) {
    for (const locale of LOCALES) {
      const key = cellKey(target.id, width, locale)
      test(key, async ({ browser }) => {
        const context = await browser.newContext({
          viewport: { width, height: 800 },
          deviceScaleFactor: 2,
          isMobile: true,
          hasTouch: true,
          userAgent: PHONE_UA,
          colorScheme: 'light',
          locale: 'en-MY',
        })
        const page = await context.newPage()
        try {
          const m = await measureCell(page, target, locale)
          const file = fileSafe(key)
          fs.mkdirSync(RESULTS_DIR, { recursive: true })
          fs.mkdirSync(SHOTS_DIR, { recursive: true })
          // A public page: what the first screen shows. A sandbox surface: the whole surface — its
          // first screen is the sandbox's own picker, which tells the owner nothing.
          const shot = path.join(SHOTS_DIR, `${file}.png`)
          if (target.kind === 'sandbox') await page.locator('main').first().screenshot({ path: shot })
          else await page.screenshot({ path: shot })
          fs.writeFileSync(path.join(RESULTS_DIR, `${file}.json`), JSON.stringify({ key, ...m }, null, 2))

          const now = { overflow: m.overflow, smallInputs: m.smallInputs, smallTargets: m.smallTargets }
          const worse = worseThan(now, BASELINE.cells[key])
          const detail = [
            m.widest ? `widest: ${m.widest}` : '',
            ...m.smallInputExamples.map((e) => `small field: ${e}`),
            ...m.smallTargetExamples.map((e) => `small target: ${e}`),
          ].filter(Boolean).join('\n  ')
          expect(worse, `${key} (${m.url}) is worse than the baseline:\n  ${worse.join('\n  ')}\n  ${detail}`)
            .toEqual([])
        } finally {
          await context.close()
        }
      })
    }
  }
}

if (SANDBOX_ON) {
  test('the sandbox index links exactly the surfaces this check measures', async ({ page }) => {
    // The slug list is read from surfaces.tsx source (targets.ts says why). This is its
    // cross-check against the running app: a surface the reader missed would show up here.
    await page.goto(`${BASE}/sandbox`, { waitUntil: 'networkidle', timeout: 90_000 })
    const linked = await page.locator('main a[href^="/sandbox/"]')
      .evaluateAll((as) => as.map((a) => (a.getAttribute('href') ?? '').replace('/sandbox/', '')))
    expect([...linked].sort()).toEqual([...sandboxSlugs()].sort())
  })
}
