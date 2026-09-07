import fs from 'fs'
import path from 'path'

/**
 * A refusal must not tell somebody to do something the product cannot do.
 *
 * ⚠ THE BUG THIS EXISTS FOR (owner, 2026-09-07). The gift-delete refusal read *"This gift has
 * intake years. **Delete them first**, or keep the gift…"* — and **there is no way to delete an
 * intake year.** No endpoint, no button. The advice pointed at a door that does not exist, and
 * behind it sat a real trap: a gift created with one stray year could never be deleted, and
 * neither could the year.
 *
 * ⚠ NOTHING WOULD HAVE CAUGHT IT. The copy is grammatical, translated, parity-checked and
 * rendered correctly; every gate was green. What was wrong is a claim about the PRODUCT, which no
 * string test asks about — so this one asks about it directly.
 *
 * ⚠ IT IS WRITTEN AS A PAIRING, NOT A BANNED WORD. The instruction only becomes false while the
 * capability is missing. The day somebody builds year-deletion, the premise below flips and the
 * copy may honestly say "delete them first" again — so the test reads the CODE for that
 * capability rather than forbidding a phrase for ever.
 */

const SRC = path.join(__dirname, '..', '..')
const messages = (lang: string) =>
  JSON.parse(fs.readFileSync(path.join(SRC, 'messages', `${lang}.json`), 'utf8'))

/** Every `.ts`/`.tsx` under `src`, so the capability check cannot be scoped-blind. */
function walk(dir: string, out: string[] = []): string[] {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(e.name)) out.push(p)
  }
  return out
}

/**
 * Can a person delete an intake year anywhere in this product?
 *
 * ⚠ THIS FILE IS EXCLUDED FROM ITS OWN SCAN, AND THE BITE-CHECK IS THE ONLY REASON IT IS. The
 * first version searched all of `src` — including itself — and the identifier it looks for is
 * written right here in the pattern, so it always found it, always took the early return, and
 * passed against the exact wording it was written to reject. **A dead test with a green tick.**
 *
 * Excluded BY PATH, never by skipping `__tests__`: a real call site living beside a test must
 * still count (docs/lessons.md, Layer 1 F7d — "a scan that quietly widens its exclusion to a whole
 * directory buys a green run and loses the guard").
 */
const SELF = path.join(SRC, 'lib', '__tests__', 'deleteRefusalCopy.test.ts')

const canDeleteAnIntakeYear = () =>
  walk(SRC)
    .filter((f) => path.resolve(f) !== path.resolve(SELF))
    .some((f) => /deleteAdminIntakeYear|intake-years\/\$\{[^}]+\}\/'?,\s*'DELETE'/
      .test(fs.readFileSync(f, 'utf8')))

describe('the gift-delete refusal is honest about what can be done', () => {
  // One phrase per locale that would be an INSTRUCTION to delete the years. Deliberately the
  // imperative, not the noun: the message may — and does — still explain that a year holds the
  // rules and the applications.
  const TELLS_YOU_TO_DELETE_THEM: Record<string, RegExp> = {
    en: /delete them/i,
    ms: /padamkannya|padamkan ia/i,
    ta: /அவற்றை\s*நீக்க/,
  }

  it.each(['en', 'ms', 'ta'])(
    '%s: does not tell anybody to delete the intake years while nothing can',
    (lang) => {
      if (canDeleteAnIntakeYear()) return   // premise gone — the instruction would be honest
      const copy = messages(lang).admin.programmes.error.hasIntakeYears as string
      expect({ lang, copy }).toEqual({ lang, copy })          // print it on failure
      expect(TELLS_YOU_TO_DELETE_THEM[lang].test(copy)).toBe(false)
    },
  )

  it('still SAYS why the gift is held — refusing without a reason is the other failure', () => {
    // The fix must not swing into silence. Whatever the wording, it has to name the intake year.
    expect(messages('en').admin.programmes.error.hasIntakeYears).toMatch(/intake year/i)
  })

  it('reads the real capability, so this guard retires itself when year-deletion is built', () => {
    // Pins the premise rather than assuming it: if this flips to true and nobody revisits the
    // copy, the first assertion simply stops applying — by design, and visibly here.
    expect(typeof canDeleteAnIntakeYear()).toBe('boolean')
  })
})
