/**
 * The walks' safety rails (audit sprint A4.6). Read by the config and every walk.
 *
 * Two modes:
 *  - HERMETIC (default). The app is told its API lives at FAKE_API and its Supabase at FAKE_SUPABASE —
 *    made-up local ports nothing listens on. `seal()` answers the API calls a walk names with its
 *    own made-up JSON, answers every other API call 404, and ABORTS every request to anywhere that is
 *    not this machine's walk server. Nothing can reach the live site, a real account or an inbox.
 *  - FULL STACK (opt-in, for sign-in walks). WALK_SUPABASE_URL / WALK_SUPABASE_ANON_KEY / WALK_API_URL
 *    name a LOCAL Supabase and a LOCAL API. `fullStack()` is true only when all three are set AND each
 *    is a localhost address; `seal()` then lets localhost through and still aborts everything else.
 */
import * as fs from 'fs'
import * as path from 'path'
import type { BrowserContext, Route } from '@playwright/test'

export const WALK_PORT = 3200
export const WALK_BASE = `http://localhost:${WALK_PORT}`
const FAKE_API = 'http://127.0.0.1:8799'
const FAKE_SUPABASE = 'http://127.0.0.1:54399'
const FAKE_ANON_KEY = 'walk-local-dummy-key'

const isLocalUrl = (u: string | undefined): boolean => {
  if (!u) return false
  try {
    const { hostname, protocol } = new URL(u)
    return protocol === 'http:' && (hostname === 'localhost' || hostname === '127.0.0.1')
  } catch {
    return false
  }
}

/** True only when a LOCAL Supabase and a LOCAL API are named. A remote address never counts. */
export function fullStack(): boolean {
  const { WALK_SUPABASE_URL, WALK_SUPABASE_ANON_KEY, WALK_API_URL } = process.env
  return Boolean(WALK_SUPABASE_ANON_KEY) && isLocalUrl(WALK_SUPABASE_URL) && isLocalUrl(WALK_API_URL)
}

export const FULL_STACK_SKIP_REASON =
  'needs a real sign-in: set WALK_SUPABASE_URL, WALK_SUPABASE_ANON_KEY and WALK_API_URL to a LOCAL ' +
  'Supabase (supabase start) and a LOCAL API (manage.py runserver, development settings) with made-up ' +
  'accounts. Never the live project, never real accounts.'

export const appApiUrl = () => (fullStack() ? process.env.WALK_API_URL! : FAKE_API)
export const appSupabaseUrl = () => (fullStack() ? process.env.WALK_SUPABASE_URL! : FAKE_SUPABASE)
export const appSupabaseKey = () => (fullStack() ? process.env.WALK_SUPABASE_ANON_KEY! : FAKE_ANON_KEY)

/** A walk's made-up API answers: path (from `/api/v1/…`) → JSON body. */
export type ApiMocks = Record<string, unknown>

const corsHeaders = (route: Route) => ({
  'access-control-allow-origin': route.request().headers()['origin'] || WALK_BASE,
  'access-control-allow-credentials': 'true',
  'access-control-allow-headers': '*',
  'access-control-allow-methods': 'GET,POST,PUT,PATCH,DELETE,OPTIONS',
})

/**
 * Seal a browser context. Returns the list of addresses it blocked, so a walk can show them.
 * In hermetic mode `mocks` answer the API; in full-stack mode they are ignored (the local API answers).
 */
export async function seal(context: BrowserContext, mocks: ApiMocks = {}): Promise<string[]> {
  const blocked: string[] = []
  const api = new URL(appApiUrl())
  await context.route('**/*', async (route) => {
    const url = new URL(route.request().url())
    if (url.origin === WALK_BASE) return route.continue()
    if (fullStack()) {
      if (isLocalUrl(url.href)) return route.continue()
    } else if (url.origin === api.origin) {
      if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers: corsHeaders(route) })
      const hit = Object.keys(mocks).find((p) => url.pathname === p)
      return route.fulfill({
        status: hit ? 200 : 404,
        contentType: 'application/json',
        headers: corsHeaders(route),
        body: JSON.stringify(hit ? mocks[hit] : { detail: 'not_found' }),
      })
    }
    blocked.push(url.origin)
    return route.abort()
  })
  return blocked
}

export type Locale = 'en' | 'ms' | 'ta'
export const LOCALES: Locale[] = ['en', 'ms', 'ta']

/** The app's own words for a dotted key in a locale, read from the message files the app ships —
 *  so a walk follows the copy instead of pinning it. `vars` fills `{name}` slots as `t()` does. */
export function say(locale: Locale, key: string, vars: Record<string, string> = {}): string {
  const file = path.resolve(__dirname, '..', 'src', 'messages', `${locale}.json`)
  let node: unknown = JSON.parse(fs.readFileSync(file, 'utf8'))
  for (const part of key.split('.')) node = (node as Record<string, unknown> | undefined)?.[part]
  if (typeof node !== 'string') throw new Error(`no ${locale} string for ${key}`)
  return Object.entries(vars).reduce((s, [k, v]) => s.split(`{${k}}`).join(v), node)
}

/** The locale key the app reads (lib/storage.ts KEY_LOCALE), set before the first script runs. */
export async function useLocale(context: BrowserContext, locale: Locale) {
  await context.addInitScript((l) => {
    try { window.localStorage.setItem('halatuju_locale', l) } catch { /* private mode: English */ }
  }, locale)
}
