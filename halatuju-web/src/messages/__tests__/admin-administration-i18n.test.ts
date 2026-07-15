/**
 * Guardrail — the Administration panel i18n keys (Sprint B). The flat `admin.*` namespace
 * was previously untested (only `admin.scholarship` had a guard), so new keys could ship
 * missing from ms/ta and render the raw key path. This covers the new `admin.administration`
 * namespace (static-resolve + en/ms/ta parity) and the two new `admin.role` entries.
 *
 * If this fails after you ADD a t('admin.administration.*') key: add it to all three message
 * files. If it fails after a RENAME: update both the code and the JSON.
 */
import * as fs from 'fs'
import * as path from 'path'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

const SRC_DIR = path.join(__dirname, '..', '..') // .../src
const NS = 'admin.administration'

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

// Static keys under admin.administration ending at a closing quote (dynamic template
// keys like `…staffRole.${rl}` end at `${` and are excluded — covered by parity below).
const re = new RegExp(`['"\`](admin\\.administration\\.[\\w.]+?)(?=['"\`])`, 'g')
const usedStatic = Array.from(new Set(captureGroup1(re, blob))).filter((k) => !k.endsWith('.'))

describe('admin.administration i18n hygiene', () => {
  test('every referenced admin.administration key resolves in en.json (no missing keys)', () => {
    const missing = usedStatic.filter((k) => typeof resolve(en, k) !== 'string')
    expect(missing).toEqual([])
  })

  test('en / ms / ta key sets are identical under admin.administration', () => {
    const e: string[] = []; leafPaths((resolve(en, NS) ?? {}) as Record<string, unknown>, '', e)
    const m: string[] = []; leafPaths((resolve(ms, NS) ?? {}) as Record<string, unknown>, '', m)
    const t: string[] = []; leafPaths((resolve(ta, NS) ?? {}) as Record<string, unknown>, '', t)
    expect(e.length).toBeGreaterThan(0)
    expect(m.sort()).toEqual(e.slice().sort())
    expect(t.sort()).toEqual(e.slice().sort())
  })

  test('admin.role has org_admin + qc in every locale (Administration panel roles)', () => {
    for (const loc of [en, ms, ta]) {
      expect(typeof resolve(loc, 'admin.role.org_admin')).toBe('string')
      expect(typeof resolve(loc, 'admin.role.qc')).toBe('string')
    }
  })
})
