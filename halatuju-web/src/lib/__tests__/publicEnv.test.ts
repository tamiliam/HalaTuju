/**
 * TD-470 (2026-11-03): every `process.env.NEXT_PUBLIC_*` the app reads has a build-time value.
 *
 * Next inlines a NEXT_PUBLIC_ variable only when the build has a value for it — and it SKIPS a
 * falsy `env` value in next.config.js, so `X || ''` there defines nothing. A name left undefined
 * stays a live `process.env.X` read, and webpack ships its `process` polyfill (~0.8 kB gzipped,
 * copied into 73 chunks: 89 of 102 routes and the root layout). `NEXT_PUBLIC_ORG_CODE` is unset on
 * Cloud Run on purpose, so production paid it; the Turnstile key and the app version are set only by
 * the Dockerfile, so the deploy gate's budget build paid it too — `/scholarship/apply` sat inside its
 * near-line margin on the polyfill's weight.
 *
 * Defined = the committed `.env.production` sets it, OR `next.config.js` `env` gives it a NON-EMPTY
 * value, OR the config's webpack hook defines it when the variable is unset. Measured here with every
 * NEXT_PUBLIC_ name the app reads deleted from the environment — the deploy gate's worst case.
 * `.env.local` never counts: it is gitignored, and the gate never has it.
 */
import * as fs from 'fs'
import * as path from 'path'

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..')
const SRC = path.join(WEB_ROOT, 'src')
const READ = /process\.env\.(NEXT_PUBLIC_[A-Z0-9_]+)/g
const SET = /^\s*(NEXT_PUBLIC_[A-Z0-9_]+)\s*=\s*\S/

function sources(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name)
    if (e.isDirectory()) return e.name === '__tests__' || e.name === 'sandbox' ? [] : sources(full)
    return /\.(ts|tsx)$/.test(e.name) && !/\.test\.(ts|tsx)$/.test(e.name) ? [full] : []
  })
}

function readsInApp(): Map<string, string[]> {
  const out = new Map<string, string[]>()
  for (const file of sources(SRC)) {
    for (const m of fs.readFileSync(file, 'utf8').matchAll(READ)) {
      out.set(m[1], [...(out.get(m[1]) ?? []), path.relative(WEB_ROOT, file)])
    }
  }
  return out
}

type Config = {
  env?: Record<string, unknown>
  webpack: (c: { module: { rules: unknown[] }; plugins?: unknown[] }, o?: unknown) => { plugins?: unknown[] }
}

class FakeDefine { constructor(public definitions: Record<string, string>) {} }

/** What a build with NONE of `names` in its environment would define. */
function definedWithNothingSet(names: string[]): Set<string> {
  const saved = Object.fromEntries(names.map((n) => [n, process.env[n]]))
  for (const n of names) delete process.env[n]
  try {
    let config: Config
    jest.isolateModules(() => { config = jest.requireActual(path.join(WEB_ROOT, 'next.config.js')) as Config })
    const defined = new Set<string>()
    for (const [k, v] of Object.entries(config!.env ?? {})) if (v) defined.add(k)
    const out = config!.webpack({ module: { rules: [] }, plugins: [] }, { webpack: { DefinePlugin: FakeDefine } })
    for (const p of out.plugins ?? []) {
      if (p instanceof FakeDefine) {
        for (const [k, v] of Object.entries(p.definitions)) {
          expect(v).toBe('""')   // only ever the empty string — never a value invented here
          defined.add(k.replace(/^process\.env\./, ''))
        }
      }
    }
    for (const line of fs.readFileSync(path.join(WEB_ROOT, '.env.production'), 'utf8').split(/\r?\n/)) {
      const m = line.match(SET)
      if (m) defined.add(m[1])
    }
    return defined
  } finally {
    for (const n of names) if (saved[n] === undefined) delete process.env[n]; else process.env[n] = saved[n]
  }
}

describe('public env (TD-470)', () => {
  test('the scan finds the reads it must guard (it is not watching an empty room)', () => {
    const reads = readsInApp()
    for (const n of ['NEXT_PUBLIC_TURNSTILE_SITE_KEY', 'NEXT_PUBLIC_ORG_CODE', 'NEXT_PUBLIC_APP_VERSION', 'NEXT_PUBLIC_API_URL']) {
      expect(reads.has(n)).toBe(true)
    }
  })

  test('every NEXT_PUBLIC_ name the app reads is defined even when the environment sets none of them', () => {
    const reads = readsInApp()
    const defined = definedWithNothingSet([...reads.keys()])
    const missing = [...reads].filter(([name]) => !defined.has(name))
      .map(([name, files]) => `${name} (read in ${[...new Set(files)].join(', ')})`)
    expect(missing).toEqual([])
  })

  test('a name the environment DOES set is left to Next (never defined twice, never overwritten with "")', () => {
    const saved = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = 'site-key-for-test'
    try {
      let config: Config
      jest.isolateModules(() => { config = jest.requireActual(path.join(WEB_ROOT, 'next.config.js')) as Config })
      const out = config!.webpack({ module: { rules: [] }, plugins: [] }, { webpack: { DefinePlugin: FakeDefine } })
      const keys = (out.plugins ?? []).flatMap((p) => (p instanceof FakeDefine ? Object.keys(p.definitions) : []))
      expect(keys).not.toContain('process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY')
    } finally {
      if (saved === undefined) delete process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY
      else process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY = saved
    }
  })
})
