/**
 * Guardrail: the app's custom i18n `t` (src/lib/i18n.tsx) does FLAT `{var}` substitution only —
 * it has NO ICU MessageFormat engine. So an ICU `{x, select, …}` / `{x, plural, …}` /
 * `{x, selectordinal, …}` message would render its raw template to the user (the #13/#102 bug:
 * the STR-not-current `select` copy printed verbatim on the officer cockpit).
 *
 * This fails the build if any message value carries ICU syntax. The fix for such a case is the
 * same one applied to `str_not_current`: split into flat per-value keys and pick the key in code.
 */
import * as fs from 'fs'
import * as path from 'path'

const MSG_DIR = path.join(__dirname, '..')
const LOCALES = ['en.json', 'ms.json', 'ta.json']

// `{ <ident> , (select|plural|selectordinal) ,` — the ICU argument forms `t` cannot format.
const ICU_RE = /\{\s*\w+\s*,\s*(select|plural|selectordinal)\s*,/

function leaves(obj: Record<string, unknown>, prefix: string, out: Array<[string, string]>): void {
  Object.keys(obj).forEach((k) => {
    const p = prefix ? `${prefix}.${k}` : k
    const v = obj[k]
    if (v !== null && typeof v === 'object') leaves(v as Record<string, unknown>, p, out)
    else if (typeof v === 'string') out.push([p, v])
  })
}

/** ~3,900 string leaves per catalogue on 2026-09-20. A MINIMUM — copy is added every sprint. */
const LEAF_FLOOR = 3_000

describe('no ICU MessageFormat in message catalogues (the custom t is flat-only)', () => {
  LOCALES.forEach((file) => {
    test(`${file} has no ICU select/plural constructs`, () => {
      const full = path.join(MSG_DIR, file)
      // ⚠ NAMED, not a bare ENOENT (TD-276, code health H16).
      if (!fs.existsSync(full)) {
        throw new Error(
          `SOURCE GUARD: ${file} is not in src/messages. The catalogue has MOVED or been renamed `
          + '— follow it and re-point LOCALES, never delete the assertion.')
      }
      const json = JSON.parse(fs.readFileSync(full, 'utf8'))
      const out: Array<[string, string]> = []
      leaves(json, '', out)
      // ⚠ THE FLOOR (TD-276). A catalogue that parsed to `{}`, or a `leaves` walk that stopped
      // recursing, yields an empty list — and an empty list has no ICU in it, so this guard
      // would report "no offenders" for ever while reading nothing. This arc has met that shape
      // four times; the number is here so it cannot happen a fifth.
      expect(out.length).toBeGreaterThanOrEqual(LEAF_FLOOR)
      const offenders = out.filter(([, v]) => ICU_RE.test(v)).map(([k]) => k)
      expect(offenders).toEqual([])
    })
  })
})
