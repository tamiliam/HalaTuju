/**
 * Guardrail (TD-120): keep the `admin.scholarship.*` i18n namespace clean.
 *
 * 1. No ORPHANED keys — every leaf must be referenced in production source, either by its
 *    full dotted path `t('admin.scholarship.<path>')` or under a dynamically-built prefix
 *    (e.g. `t('admin.scholarship.anomaly.' + code + '.fact')`). The scan is dynamic-aware so
 *    it does NOT flag keys addressed by concatenation/template — exactly the trap that made a
 *    naive bulk-delete dangerous during the TD-120 cleanup.
 * 2. PARITY — en / ms / ta must hold the identical key set under this namespace.
 *
 * If this fails after you ADD a key: reference it in code (or delete it). If it fails after you
 * RENAME a key: update the JSON in all three languages. Scope is admin.scholarship only.
 */
import * as fs from 'fs'
import * as path from 'path'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

const SRC_DIR = path.join(__dirname, '..', '..') // .../src

// All production .ts/.tsx under src, excluding tests (test-only references don't count as live).
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

function leafPaths(obj: Record<string, unknown>, prefix: string, out: string[]): void {
  Object.keys(obj).forEach((k) => {
    const p = prefix ? `${prefix}.${k}` : k
    const v = obj[k]
    if (v !== null && typeof v === 'object') leafPaths(v as Record<string, unknown>, p, out)
    else out.push(p)
  })
}

// Collect capture-group 1 of every match of a global regex, without iterators or RegExp.exec.
function captureGroup1(re: RegExp, s: string): string[] {
  const out: string[] = []
  s.replace(re, (_full: string, g1: string): string => {
    out.push(g1)
    return _full
  })
  return out
}

const adminScholarship = (m: { admin: { scholarship: Record<string, unknown> } }) => m.admin.scholarship

const files: string[] = []
collectSource(SRC_DIR, files)
const blob = files.map((f) => fs.readFileSync(f, 'utf8')).join('\n')

// Dynamically-built prefixes: `admin.scholarship.<X>.` immediately before a closing quote or `${`.
const dynPrefixes: string[] = []
captureGroup1(/admin\.scholarship\.((?:\w+\.)+)(?=['"`]|\$\{)/g, blob).forEach((p) => {
  if (dynPrefixes.indexOf(p) < 0) dynPrefixes.push(p)
})
// Also capture a prefix that ends just before `${` even when it ends in a NON-dot word char
// (e.g. `recordVerdict.noAmountReason_${disqualifier}` — the verdict-aware no-amount reason codes).
// The first regex only matches `.`-terminated prefixes, so an underscore-suffixed dynamic key
// would otherwise read as an orphan.
captureGroup1(/admin\.scholarship\.([\w.]+?)(?=\$\{)/g, blob).forEach((p) => {
  if (dynPrefixes.indexOf(p) < 0) dynPrefixes.push(p)
})
const topLevelDynamic = /admin\.scholarship\.(?=['"`]|\$\{)/.test(blob)

// Statically-used full paths: `admin.scholarship.<path>` ending right at a closing quote.
const staticPaths: string[] = []
captureGroup1(/admin\.scholarship\.([\w.]+?)(?=['"`])/g, blob).forEach((p) => {
  if (!p.endsWith('.') && staticPaths.indexOf(p) < 0) staticPaths.push(p)
})

function isDynamic(rel: string): boolean {
  if (topLevelDynamic) return true
  return dynPrefixes.some((p) => rel === p.slice(0, -1) || rel.indexOf(p) === 0)
}

describe('admin.scholarship i18n hygiene', () => {
  test('no orphaned keys (dynamic-aware)', () => {
    const leaves: string[] = []
    leafPaths(adminScholarship(en as never), '', leaves)
    const orphans = leaves.filter((rel) => staticPaths.indexOf(rel) < 0 && !isDynamic(rel))
    expect(orphans).toEqual([])
  })

  test('en / ms / ta key sets are identical', () => {
    const e: string[] = []; leafPaths(adminScholarship(en as never), '', e)
    const m: string[] = []; leafPaths(adminScholarship(ms as never), '', m)
    const t: string[] = []; leafPaths(adminScholarship(ta as never), '', t)
    expect(m.sort()).toEqual(e.slice().sort())
    expect(t.sort()).toEqual(e.slice().sort())
  })
})
