/**
 * Playwright `globalSetup` for `npm run mobile-check` (Mobile M1b): visit every page ONCE, one at
 * a time, before anything is measured.
 *
 * WHY. `next dev` compiles a route the first time it is asked for. With three workers asking for
 * three cold routes at once on a busy machine, the compiles starve the pages' main threads and a
 * cell could time out waiting for `<html lang>` — with no page snapshot to say why (reported by the
 * Profiles session, 2026-10-31). Visiting each URL serially first pays every compile up front; the
 * measured visits then hit warm routes. Nothing is measured or recorded here.
 *
 * Read-only like the spec: every non-GET request, Supabase auth and Turnstile are aborted. A page
 * that fails to load here is not an error — the measured visit will report it properly.
 * Only a LOCAL base is warmed: a deployed site has nothing to compile.
 */
import { chromium } from '@playwright/test'
import { BASE, isLocal, publicTargets, PUBLIC_BASE, sandboxTargets } from './targets'

export default async function warmUp(): Promise<void> {
  const urls = [
    ...(isLocal(PUBLIC_BASE) ? publicTargets().map((t) => t.url) : []),
    ...(isLocal(BASE) ? sandboxTargets().map((t) => t.url) : []),
  ]
  if (urls.length === 0) return
  const started = Date.now()
  const browser = await chromium.launch()
  const page = await browser.newPage()
  await page.route('**/*', (route) => {
    const req = route.request()
    const url = new URL(req.url())
    if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method()) || url.pathname.startsWith('/auth/v1/')
      || url.hostname === 'challenges.cloudflare.com') return route.abort()
    return route.continue()
  })
  for (const url of urls) {
    try {
      await page.goto(url, { waitUntil: 'load', timeout: 180_000 })
    } catch {
      // The measured visit reports a page that will not load; warming it is best effort.
    }
  }
  await browser.close()
  console.log(`mobile-check: warmed ${urls.length} page(s) in ${Math.round((Date.now() - started) / 1000)} s`)
}
