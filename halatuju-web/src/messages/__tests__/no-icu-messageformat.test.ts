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

describe('no ICU MessageFormat in message catalogues (the custom t is flat-only)', () => {
  LOCALES.forEach((file) => {
    test(`${file} has no ICU select/plural constructs`, () => {
      const json = JSON.parse(fs.readFileSync(path.join(MSG_DIR, file), 'utf8'))
      const out: Array<[string, string]> = []
      leaves(json, '', out)
      const offenders = out.filter(([, v]) => ICU_RE.test(v)).map(([k]) => k)
      expect(offenders).toEqual([])
    })
  })
})
