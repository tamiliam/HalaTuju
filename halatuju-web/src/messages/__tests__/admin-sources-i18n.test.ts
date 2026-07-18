/**
 * Guardrail — the Sources module i18n keys (Contract Go-Live T2). Covers the new
 * `admin.sources.*` namespace (static-resolve + en/ms/ta parity) plus the two
 * `admin.administration.sources` card keys. A referenced key missing from ms/ta would
 * render the raw key path on a dark surface — this fails the build first.
 *
 * If this fails after ADDING a t('admin.sources.*') key: add it to all three message
 * files. After a RENAME: update both the code and the JSON.
 */
import * as fs from 'fs'
import * as path from 'path'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

const SRC_DIR = path.join(__dirname, '..', '..') // .../src
const NS = 'admin.sources'

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

const re = new RegExp(`['"\`](admin\\.sources\\.[\\w.]+?)(?=['"\`])`, 'g')
const usedStatic = Array.from(new Set(captureGroup1(re, blob))).filter((k) => !k.endsWith('.'))

describe('admin.sources i18n hygiene', () => {
  test('every referenced admin.sources key resolves in en.json (no missing keys)', () => {
    const missing = usedStatic.filter((k) => typeof resolve(en, k) !== 'string')
    expect(missing).toEqual([])
  })

  test('en / ms / ta key sets are identical under admin.sources', () => {
    const e: string[] = []; leafPaths((resolve(en, NS) ?? {}) as Record<string, unknown>, '', e)
    const m: string[] = []; leafPaths((resolve(ms, NS) ?? {}) as Record<string, unknown>, '', m)
    const t: string[] = []; leafPaths((resolve(ta, NS) ?? {}) as Record<string, unknown>, '', t)
    expect(e.length).toBeGreaterThan(0)
    expect(m.sort()).toEqual(e.slice().sort())
    expect(t.sort()).toEqual(e.slice().sort())
  })

  test('the Administration Sources card keys exist in every locale', () => {
    for (const loc of [en, ms, ta]) {
      expect(typeof resolve(loc, 'admin.administration.sources')).toBe('string')
      expect(typeof resolve(loc, 'admin.administration.sourcesSub')).toBe('string')
    }
  })
})
