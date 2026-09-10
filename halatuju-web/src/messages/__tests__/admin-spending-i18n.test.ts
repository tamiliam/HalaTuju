/**
 * Guardrail — the `admin.spending.*` namespace (sponsor spending S4).
 *
 * ⚠ **PARITY IS NOT EXISTENCE, AND THAT IS WHY THIS FILE EXISTS.** en/ms/ta parity proves the
 * three locales agree; it says nothing about whether a key a page ACTUALLY CALLS was ever added.
 * The sponsor redesign referenced ~47 keys that existed in no locale and rendered raw dotted
 * strings for FOUR SPRINTS, undetected — because parity passed (all three equally missing) and
 * nobody was looking at the surface yet. That is exactly this page's situation: nothing about
 * spending is live, so there is no user to notice.
 *
 * ⚠ **THIS PAGE BUILDS MOST OF ITS KEYS DYNAMICALLY**, which a static scan cannot see:
 * `admin.spending.stat.${key}`, `admin.spending.by.${decided_by || 'none'}` and
 * `admin.spending.error.${code}`. A plain "does every literal resolve?" test would check almost
 * nothing here, so each dynamic family is enumerated below against the values the code can
 * actually produce — the ten sorter rungs, the four figures, the three refusal codes.
 */
import * as fs from 'fs'
import * as path from 'path'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

const SRC_DIR = path.join(__dirname, '..', '..') // .../src
const NS = 'admin.spending'

function collectSource(dir: string, acc: string[]): void {
  fs.readdirSync(dir, { withFileTypes: true }).forEach((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === '__tests__' || entry.name === 'node_modules') return
      collectSource(full, acc)
    } else if (/\.tsx?$/.test(entry.name)) {
      acc.push(full)
    }
  })
}

function captureGroup1(re: RegExp, s: string): string[] {
  const out: string[] = []
  s.replace(re, (_full: string, g1: string): string => { out.push(g1); return _full })
  return out
}

function leafPaths(obj: Record<string, unknown>, prefix: string, out: string[]): void {
  Object.keys(obj).forEach((k) => {
    const p = prefix ? `${prefix}.${k}` : k
    const v = obj[k]
    if (v !== null && typeof v === 'object') leafPaths(v as Record<string, unknown>, p, out)
    else out.push(p)
  })
}

function resolve(obj: unknown, key: string): unknown {
  return key.split('.').reduce<unknown>((cur, part) => {
    if (cur && typeof cur === 'object' && part in (cur as Record<string, unknown>)) {
      return (cur as Record<string, unknown>)[part]
    }
    return undefined
  }, obj)
}

const files: string[] = []
collectSource(SRC_DIR, files)
const blob = files.map((f) => fs.readFileSync(f, 'utf8')).join('\n')

const re = /['"`](admin\.spending\.[\w.]+?)(?=['"`])/g
const usedStatic = Array.from(new Set(captureGroup1(re, blob))).filter((k) => !k.endsWith('.'))

// ⚠ Every value each dynamic key family can actually take. These are not a wish list — they are
// the sorter's `SPEND_DECIDED_BY_CHOICES` (plus `none` for a row nothing has decided), the four
// figures the strip draws, and the three codes `spend_report.set_owner_category` can return.
// If a rung or a refusal code is added on the Python side, this list is where the missing
// translation surfaces.
const DYNAMIC = [
  ...['spent', 'sorted', 'unsorted', 'toCheck'].map((k) => `${NS}.stat.${k}`),
  ...['none', 'duitnow', 'rule', 'inferred', 'ai', 'owner'].map((k) => `${NS}.by.${k}`),
  ...['unknown_merchant', 'unknown_category', 'merchant_required'].map((k) => `${NS}.error.${k}`),
]

describe('admin.spending i18n hygiene', () => {
  test('the page is actually scanned (the floor)', () => {
    // ⚠ A path change that silently matched nothing would make every assertion below vacuous.
    expect(usedStatic.length).toBeGreaterThan(5)
    expect(usedStatic).toContain('admin.spending.title')
  })

  test('every literal admin.spending key resolves in en.json', () => {
    const missing = usedStatic.filter((k) => typeof resolve(en, k) !== 'string')
    expect(missing).toEqual([])
  })

  test('every DYNAMICALLY built key resolves in all three locales', () => {
    // The half a static scan is blind to, and the half this page is mostly made of.
    const missing: string[] = []
    for (const key of DYNAMIC) {
      for (const [name, loc] of [['en', en], ['ms', ms], ['ta', ta]] as const) {
        if (typeof resolve(loc, key) !== 'string') missing.push(`${name}: ${key}`)
      }
    }
    expect(missing).toEqual([])
  })

  test('en / ms / ta key sets are identical under admin.spending', () => {
    const e: string[] = []; leafPaths((resolve(en, NS) ?? {}) as Record<string, unknown>, '', e)
    const m: string[] = []; leafPaths((resolve(ms, NS) ?? {}) as Record<string, unknown>, '', m)
    const t: string[] = []; leafPaths((resolve(ta, NS) ?? {}) as Record<string, unknown>, '', t)
    expect(e.length).toBeGreaterThan(0)
    expect(m.sort()).toEqual(e.slice().sort())
    expect(t.sort()).toEqual(e.slice().sort())
  })

  test('the navigation label exists in every locale', () => {
    // The row is in the registry by `labelKey`, which no page-level scan would ever reach.
    for (const loc of [en, ms, ta]) {
      expect(typeof resolve(loc, 'admin.spending.nav')).toBe('string')
    }
  })
})
