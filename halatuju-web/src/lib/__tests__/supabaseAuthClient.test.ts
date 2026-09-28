/**
 * @jest-environment jsdom
 */
import * as fs from 'fs'
import * as path from 'path'
import { createClient } from '@supabase/supabase-js'
import { createAuthOnlyClient, SUPABASE_JS_VERSION } from '../supabaseAuthClient'

/**
 * TD-300 (2026-09-28): the app's three Supabase clients are built by `createAuthOnlyClient`, which
 * constructs ONLY the auth client, instead of supabase-js's `createClient`, which constructs
 * Realtime, PostgREST, Storage and Functions as well and so cannot tree-shake. Measured on a real
 * `next build`: the median route 256 kB -> 227 kB of first-load JS, 73 routes lighter, none heavier.
 *
 * The saving is only honest if the auth client is THE SAME auth client. So this file builds both
 * — the real `createClient(url, key, { auth })` and ours — for each of the three option sets the
 * app uses, and compares what the auth client was constructed with. It runs under jsdom, because
 * the browser is where the app builds them (and where supabase-js stamps `X-Client-Info` "web").
 *
 * It is also the drift test that `supabaseAuthClient.ts` names: a Supabase upgrade that changes
 * the default storage key, a header, or any constructor default turns this file red.
 */

const URL_ = 'https://abcdefghijkl.supabase.co'
const KEY = 'anon-key-for-tests'

/** The three option sets, exactly as lib/supabase.ts, admin-supabase.ts, sponsor-supabase.ts pass
 *  them (the student client leaves storageKey to the default — see the storage-key test). */
const CLIENTS = [
  ['student', { flowType: 'pkce' as const }],
  ['admin', { storageKey: 'halatuju_admin_session', flowType: 'pkce' as const }],
  ['sponsor', { storageKey: 'halatuju_sponsor_session', flowType: 'pkce' as const }],
] as const

type Loose = Record<string, unknown>
const built: Array<{ auth: { stopAutoRefresh?: () => Promise<void> } }> = []

beforeAll(() => {
  // Two GoTrueClients per storage key is the point of the comparison; auth-js warns about it.
  jest.spyOn(console, 'warn').mockImplementation(() => {})
})

afterAll(async () => {
  for (const c of built) await c.auth.stopAutoRefresh?.()
  jest.restoreAllMocks()
})

function pair(options: { storageKey?: string; flowType: 'pkce' }) {
  const real = createClient(URL_, KEY, { auth: options })
  const ours = createAuthOnlyClient(URL_, KEY, options)
  built.push(real as never, ours as never)
  return { real: real.auth as unknown as Loose, ours: ours.auth as unknown as Loose }
}

/** Every setting GoTrueClient stores as a plain value, minus the per-instance counter. A new
 *  constructor default in a future auth-js lands here without anyone listing it. */
function primitives(auth: Loose): Loose {
  const out: Loose = {}
  for (const [k, v] of Object.entries(auth)) {
    if (k === 'instanceID') continue
    if (v === null || ['string', 'number', 'boolean', 'undefined'].includes(typeof v)) out[k] = v
  }
  return out
}

describe.each(CLIENTS)('the %s auth client is the one createClient builds', (_name, options) => {
  test('every plain setting is identical (url, storage key, flow, refresh, persistence, …)', () => {
    const { real, ours } = pair(options)
    expect(Object.keys(primitives(real)).length).toBeGreaterThan(8)
    expect(primitives(ours)).toEqual(primitives(real))
  })

  test('the headers are identical, in the same order', () => {
    const { real, ours } = pair(options)
    expect(Object.entries(ours.headers as Loose)).toEqual(Object.entries(real.headers as Loose))
    const admin = (x: Loose) => x.admin as Loose
    expect(Object.entries(admin(ours).headers as Loose))
      .toEqual(Object.entries(admin(real).headers as Loose))
    expect(admin(ours).url).toBe(admin(real).url)
  })

  test('the same lock, the same storage, the same user storage', () => {
    const { real, ours } = pair(options)
    expect(ours.lock).toBe(real.lock)
    expect(ours.storage).toBe(real.storage)
    expect(ours.userStorage).toBe(real.userStorage)
  })

  test('the same fetch — no custom transport smuggled in on one side', () => {
    // `primitives()` skips functions, so a custom `fetch` passed to the auth-only client went
    // unseen (adversarial review, 2026-09-29). And it CANNOT be seen on the built client: GoTrue
    // wraps a custom fetch and the default one in the same `resolveFetch` wrapper, so their
    // source, type and name are identical either way — a first draft of this test compared
    // `String(fetch)` and stayed green under a smuggled transport. So the guard is on the
    // SOURCE: the auth-only module passes `fetch: undefined` — field for field what createClient
    // passes — and nothing else. Any other value is a transport createClient does not use.
    const { real, ours } = pair(options)
    expect(typeof ours.fetch).toBe(typeof real.fetch)
    const src = fs.readFileSync(path.join(__dirname, '..', 'supabaseAuthClient.ts'), 'utf8')
    const passed = [...src.matchAll(/\bfetch\s*:\s*([^,\n]+)/g)].map((m) => m[1].trim())
    expect(passed.length).toBeGreaterThan(0)          // the option is spelled out, not omitted
    expect(passed).toEqual(passed.map(() => 'undefined'))
  })
})

describe('the facts the comparison rests on', () => {
  test('the STUDENT client keeps the default storage key — where every student is signed in', () => {
    const { ours } = pair({ flowType: 'pkce' })
    expect(ours.storageKey).toBe('sb-abcdefghijkl-auth-token')
  })

  test('X-Client-Info says supabase-js, web, and the installed version', () => {
    const { ours } = pair({ flowType: 'pkce' })
    expect((ours.headers as Loose)['X-Client-Info']).toBe(`supabase-js-web/${SUPABASE_JS_VERSION}`)
  })

  const pkg = (name: string) => JSON.parse(fs.readFileSync(
    path.join(__dirname, '..', '..', '..', 'node_modules', name, 'package.json'), 'utf8'))

  test('SUPABASE_JS_VERSION is the installed supabase-js', () => {
    expect(SUPABASE_JS_VERSION).toBe(pkg('@supabase/supabase-js').version)
  })

  test('the auth-js we import is the one supabase-js itself pins', () => {
    // If they diverge, npm installs two copies and this client stops being createClient's.
    expect(pkg('@supabase/auth-js').version)
      .toBe(pkg('@supabase/supabase-js').dependencies['@supabase/auth-js'])
  })

  test('the same URL validation, with the same messages', () => {
    for (const bad of ['', '   ', 'ftp://x.supabase.co', 'http://']) {
      let real = '', ours = ''
      try { createClient(bad, KEY) } catch (e) { real = (e as Error).message }
      try { createAuthOnlyClient(bad, KEY, { flowType: 'pkce' }) } catch (e) { ours = (e as Error).message }
      expect(real).not.toBe('')
      expect(ours).toBe(real)
    }
    let real = '', ours = ''
    try { createClient(URL_, '') } catch (e) { real = (e as Error).message }
    try { createAuthOnlyClient(URL_, '', { flowType: 'pkce' }) } catch (e) { ours = (e as Error).message }
    expect(ours).toBe(real)
  })
})

describe('no value is imported from @supabase/supabase-js in src/', () => {
  /** The 29 kB cut is undone by ONE `import { createClient } from '@supabase/supabase-js'`
   *  anywhere a route can reach. `import type` is erased at build and stays allowed. */
  const SRC = path.join(__dirname, '..', '..')
  const files: string[] = []
  const walk = (dir: string) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name)
      if (e.isDirectory()) { if (e.name !== '__tests__') walk(p) } else if (/\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name)) files.push(p)
    }
  }
  walk(SRC)

  test('the scan sees the app', () => {
    expect(files.length).toBeGreaterThan(200)
  })

  test('every import from @supabase/supabase-js is `import type`', () => {
    const offenders: string[] = []
    // `[^'"]` keeps one match inside one statement: this codebase has no semicolons to stop at,
    // and the previous import's closing quote is what ends it. `export … from` and `export *
    // from` are re-exports and bring the value in just the same (adversarial review, 2026-09-29).
    const IMPORT = /(?:import|export)\s+(type\s+)?[^'"]*?from\s+['"]@supabase\/supabase-js['"]/g
    for (const f of files) {
      const text = fs.readFileSync(f, 'utf8')
      for (const m of text.matchAll(IMPORT)) if (!m[1]) offenders.push(path.relative(SRC, f))
      if (/require\(\s*['"]@supabase\/supabase-js['"]\s*\)|import\(\s*['"]@supabase\/supabase-js['"]\s*\)/.test(text)) {
        offenders.push(path.relative(SRC, f))
      }
    }
    expect(offenders).toEqual([])
  })
})
