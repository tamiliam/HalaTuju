/**
 * Guardrail — the `admin.programmeOverview.*` namespace (Programme Overview, 2026-09-15).
 *
 * ⚠ **PARITY IS NOT EXISTENCE.** en/ms/ta parity proves the three locales agree; it says nothing
 * about whether a key the page actually CALLS was ever added. The sponsor redesign referenced ~47
 * keys that existed in no locale and rendered raw dotted strings for four sprints, undetected,
 * because parity passed (all three equally missing) and nobody was looking at the surface yet.
 *
 * ⚠ **THIS PAGE BUILDS MOST OF ITS KEYS DYNAMICALLY**, which a static scan cannot see — the
 * funnel's thirteen statuses through `statusLabelKey()`, the donut's eleven category codes, the
 * three verdict bands, and the intake's open/closed pair. Each family is enumerated below against
 * the values the SERVER can actually send: `STATUS_CHOICES`, `SPEND_CATEGORY_CHOICES` plus the
 * `none` the blank category travels as, and `review_sla.review_band`'s three answers. Add a status
 * or a category on the Python side and the missing translation surfaces HERE.
 */
import * as fs from 'fs'
import * as path from 'path'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import { APPLICATION_STATUSES, statusLabelKey } from '@/lib/applicationStatus'

const SRC_DIR = path.join(__dirname, '..', '..') // .../src
const NS = 'admin.programmeOverview'

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

// ⚠ The page writes its keys as `${K}.money.paid` with `K = 'admin.programmeOverview'`, so a scan
// for the full literal would find almost nothing. Both spellings are gathered.
const full = /['"`](admin\.programmeOverview\.[\w.]+?)(?=['"`])/g
const templated = /\$\{K\}\.([\w.]+?)(?=['"`}])/g
const usedStatic = Array.from(new Set([
  ...captureGroup1(full, blob),
  ...captureGroup1(templated, blob).map((k) => `${NS}.${k}`),
])).filter((k) => !k.endsWith('.'))

/** The ELEVEN slices `by_category` always sends: the ten `SPEND_CATEGORY_CHOICES`, plus the `none`
 *  the blank category travels as. `unsorted` and `none` are DIFFERENT states and both stay named. */
const CATEGORY_CODES = [
  'food', 'groceries', 'transport', 'study', 'phone', 'hostel',
  'health', 'clothing', 'transfer', 'unsorted', 'none',
]

/** `review_sla.review_band`'s three answers, and no fourth. */
const BANDS = ['open', 'due_soon', 'overdue']

/** The intake's two states — `is_open` is the switch, and the page chooses one of these. */
const INTAKE_STATES = ['open', 'closed']

/** The five bands the attention strip draws, built as `${K}.attention.${key}` — a template the
 *  static scan above cannot resolve, and the strip is the whole section. */
const ATTENTION_KEYS = ['unassigned', 'withReviewer', 'dueSoon', 'overdue', 'awaitingQc']

const DYNAMIC = [
  ...ATTENTION_KEYS.map((k) => `${NS}.attention.${k}`),
  ...CATEGORY_CODES.map((c) => `${NS}.category.${c}`),
  ...BANDS.map((b) => `${NS}.band.${b}`),
  ...INTAKE_STATES.map((s) => `${NS}.intake.${s}`),
]

describe('admin.programmeOverview i18n hygiene', () => {
  test('the page is actually scanned (the floor)', () => {
    // ⚠ A path change that silently matched nothing would make every assertion below vacuous.
    expect(usedStatic.length).toBeGreaterThan(20)
    expect(usedStatic).toContain('admin.programmeOverview.money.committed')
  })

  test('every literal admin.programmeOverview key resolves in en.json', () => {
    const missing = usedStatic.filter((k) => typeof resolve(en, k) !== 'string')
    expect(missing).toEqual([])
  })

  test('every DYNAMICALLY built key resolves in all three locales', () => {
    const missing: string[] = []
    for (const key of DYNAMIC) {
      for (const [name, loc] of [['en', en], ['ms', ms], ['ta', ta]] as const) {
        if (typeof resolve(loc, key) !== 'string') missing.push(`${name}: ${key}`)
      }
    }
    expect(missing).toEqual([])
  })

  test('the funnel names all THIRTEEN statuses in all three locales', () => {
    // ⚠ Through `statusLabelKey()`, in a namespace this file does not own — which is exactly why
    // it is asserted here: the funnel is zero-filled to all thirteen, so a status with no label
    // renders a raw dotted string in a tile that reads "0".
    expect(APPLICATION_STATUSES.length).toBe(13)
    const missing: string[] = []
    for (const status of APPLICATION_STATUSES) {
      for (const [name, loc] of [['en', en], ['ms', ms], ['ta', ta]] as const) {
        if (typeof resolve(loc, statusLabelKey(status)) !== 'string') {
          missing.push(`${name}: ${statusLabelKey(status)}`)
        }
      }
    }
    expect(missing).toEqual([])
  })

  test('every CHART has an accessible name in all three locales', () => {
    // ⚠ An `aria-label` is invisible twice over: it is never drawn, so no screenshot shows it
    // missing, and parity cannot see it either — an invented key is absent from all three
    // locales identically. Five keys of exactly this shape shipped unresolved on 2026-09-08.
    const keys = ['applicationsLabel', 'awardsLabel', 'moneyLabel',
                  'averageLabel', 'purchasesLabel', 'categoryLabel']
      .map((k) => `${NS}.chart.${k}`)
    const missing: string[] = []
    for (const key of keys) {
      for (const [name, loc] of [['en', en], ['ms', ms], ['ta', ta]] as const) {
        if (typeof resolve(loc, key) !== 'string') missing.push(`${name}: ${key}`)
      }
    }
    expect(missing).toEqual([])
  })

  test('en / ms / ta key sets are identical under admin.programmeOverview', () => {
    const e: string[] = []; leafPaths((resolve(en, NS) ?? {}) as Record<string, unknown>, '', e)
    const m: string[] = []; leafPaths((resolve(ms, NS) ?? {}) as Record<string, unknown>, '', m)
    const t: string[] = []; leafPaths((resolve(ta, NS) ?? {}) as Record<string, unknown>, '', t)
    expect(e.length).toBeGreaterThan(60)
    expect(m.sort()).toEqual(e.slice().sort())
    expect(t.sort()).toEqual(e.slice().sort())
  })

  test('the navigation label is REUSED, not duplicated', () => {
    // ⚠ `admin.nav.programmeOverview` already existed in all three locales — an orphaned
    // "Overview" from an earlier arc. The registry points at it rather than minting a second key
    // that says the same word, which is how two menu rows end up disagreeing about their name.
    for (const loc of [en, ms, ta]) {
      expect(typeof resolve(loc, 'admin.nav.programmeOverview')).toBe('string')
    }
    expect(resolve(en, 'admin.nav.programmeOverview')).toBe('Overview')
  })
})
