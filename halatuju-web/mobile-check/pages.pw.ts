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
 *   - the Turnstile challenge is aborted, since nothing here needs a captcha token;
 *   - locally, API READS are proxied to the live API (GET/HEAD only — the write rule above runs
 *     first), so this branch's pages are drawn with real data. See targets.ts.
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
  APP_API, BASE, EXPECTED_LANG, LOCALE_KEY, LOCALES, PROXY_API, PUBLIC_BASE, RESULTS_DIR, SANDBOX_ON,
  SHOTS_DIR, WIDTHS, cellKey, fileSafe, liveApi, publicTargets, readBaseline, sandboxSlugs, sandboxTargets, worseThan,
  type Locale, type Target,
} from './targets'

const BASELINE = readBaseline()
const PHONE_UA = 'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) '
  + 'Chrome/120.0.0.0 Mobile Safari/537.36'

test.describe.configure({ mode: 'parallel' })

/**
 * Blocks writes and sign-ins, proxies the local app's API reads to the live API (targets.ts says
 * why), and returns a probe listing any API call that failed to answer.
 */
async function readOnly(page: Page): Promise<() => string[]> {
  const aborted = new Set<string>()
  const apiFailures: string[] = []
  const appApi = new URL(APP_API)
  const live = PROXY_API ? liveApi() : ''
  await page.route('**/*', async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const write = !['GET', 'HEAD', 'OPTIONS'].includes(req.method())
    if (write || url.pathname.startsWith('/auth/v1/') || url.hostname === 'challenges.cloudflare.com') {
      aborted.add(req.url())
      return route.abort()
    }
    if (PROXY_API && url.origin === appApi.origin && url.pathname.startsWith('/api/')) {
      const origin = req.headers().origin ?? new URL(page.url() || PUBLIC_BASE).origin
      const cors = {
        'access-control-allow-origin': origin,
        'access-control-allow-credentials': 'true',
        'access-control-allow-methods': 'GET, HEAD, OPTIONS',
        'access-control-allow-headers': req.headers()['access-control-request-headers'] ?? '*',
        vary: 'Origin',
      }
      if (req.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors })
      try {
        const response = await route.fetch({ url: `${live}${url.pathname}${url.search}` })
        // The body arrives decoded, so the encoding and length the live server sent no longer apply.
        const headers = { ...response.headers() }
        delete headers['content-encoding']
        delete headers['content-length']
        return route.fulfill({ response, headers: { ...headers, ...cors } })
      } catch (err) {
        aborted.add(req.url())
        apiFailures.push(`${req.method()} ${url.pathname} via ${live} — ${(err as Error).message}`)
        return route.abort()
      }
    }
    return route.continue()
  })
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
  // ⚠ …AND FOR THE DATA. For English the wait above is VACUOUS — the server's HTML is already
  // `lang="en"` — and `networkidle` can fire before a client fetch has even started, so one run
  // measured /course/[id] as its "Loading course details…" spinner (0 targets instead of 32). So:
  // the app must have booted (`window.next` is set by Next's client at hydration), no spinner or
  // `aria-busy` box may be showing, and the DOM must have stopped changing for 800 ms.
  await page.waitForFunction(() => 'next' in window, null, { timeout: 30_000 })
  await page.waitForLoadState('networkidle')
  await page.waitForFunction(() => {
    const w = window as unknown as { __mcSig?: string; __mcAt?: number }
    const busy = Array.from(document.querySelectorAll('.animate-spin, [aria-busy="true"]')).some((e) => {
      const r = e.getBoundingClientRect()
      return r.width > 0 && r.height > 0
    })
    const sig = `${document.body.innerHTML.length}:${document.getElementsByTagName('*').length}`
    const now = Date.now()
    if (busy || w.__mcSig !== sig) { w.__mcSig = sig; w.__mcAt = now; return false }
    return now - (w.__mcAt ?? now) > 800
  }, null, { timeout: 30_000, polling: 200 })
  await page.evaluate(() => document.fonts.ready.then(() => undefined))
  await page.evaluate(() => new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => r()))))

  const failures = apiFailures()
  if (target.kind === 'public' && failures.length) {
    throw new Error('The API did not answer, so this page was drawn without its data and measuring it '
      + 'would record a different screen. Is the live API reachable from this machine? (Locally its '
      + `reads are proxied there — see mobile-check/targets.ts.)\n  ${failures.slice(0, 3).join('\n  ')}`)
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
