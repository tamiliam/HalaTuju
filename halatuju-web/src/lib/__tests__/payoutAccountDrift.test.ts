/**
 * THE DRIFT TEST for the payout-account digit floor in `actionCentre.ts` — named by its
 * `drift-test:` marker (code health H9).
 *
 * The comment said the form "mirrors that floor client-side so the student sees WHICH field is
 * wrong inline, before the round-trip". The floor itself — five digits — is the api's, and it
 * exists so a fat-finger or a truncated OCR fragment can never become a **payout target**.
 *
 * Characterised first (the H8 rule). The FLOOR agrees: five on both sides. The word *digit* did
 * NOT agree, and was pinned here as a disagreement (TD-264) rather than fixed, because it is the
 * money path. The owner ruled on 2026-09-19: narrow the api to ASCII 0-9, the form's reading.
 * Both sides now count the same characters, and the block below pins the agreement.
 */
import { countDigits } from '@/lib/actionCentre'
import { readApi } from '@/test/apiSource'
import { readWeb } from '@/test/sourceGuard'

const SERIALIZERS = 'apps/scholarship/serializers.py'
const src = readApi(SERIALIZERS)

/** The validator body, so the floor is read from the rule itself rather than restated here. */
const validator = (() => {
  const body = src.split('def validate_account_number(')[1]
  if (!body) {
    throw new Error(
      `drift test: no validate_account_number in ${SERIALIZERS}. The payout-account floor has `
      + 'moved — follow it, never delete the assertion.')
  }
  return body.split('\n\n')[0]
})()

/** The number the api refuses BELOW, read out of its own comparison. */
const apiFloor = (() => {
  const m = validator.match(/if\s+len\(digits\)\s*<\s*(\d+)\s*:/)
  if (!m) throw new Error('drift test: the account-number floor is no longer a `len(digits) < N` test')
  return Number(m[1])
})()

/** The form's floor, from `ActionCentre.tsx`'s one comparison, so the two are read the same way. */
const webFloor = (() => {
  // ⚠ `readWeb`, not a bare `readFileSync` (TD-276). This runs at module scope, so a moved
  // component used to kill the file at import with an `ENOENT` rather than say what had moved.
  const form = readWeb('src/components/ActionCentre.tsx',
    'the form must refuse a payout account at EXACTLY the api\'s digit floor, and both floors are '
    + 'read out of their own comparison rather than restated here')
  const m = form.match(/countDigits\(accountNumber\)\s*<\s*(\d+)/)
  if (!m) throw new Error('drift test: the form no longer compares countDigits against a floor')
  return Number(m[1])
})()

describe('the payout-account floor', () => {
  test('the api still refuses below five digits (parse sanity + the rule itself)', () => {
    expect(apiFloor).toBe(5)
    expect(validator).toMatch(/account_number_invalid/)
  })

  test('the form refuses at exactly the api\'s floor — not one digit wider or narrower', () => {
    expect(webFloor).toBe(apiFloor)
  })

  test('the form\'s inline error lands exactly where the api would 400', () => {
    for (const [value, digits] of [['1234', 4], ['12345', 5], ['1234-5678', 8], ['', 0]] as const) {
      expect(countDigits(value)).toBe(digits)
      expect(countDigits(value) < webFloor).toBe(digits < apiFloor)
    }
  })
})

/**
 * RESOLVED (TD-264, owner ruling 2026-09-19) — the api was narrowed to the form's reading, and
 * these assertions pin the agreement so it cannot drift apart again.
 *
 * Both sides now count ASCII `0-9` only:
 *   • api — a plain `ch in '0123456789'` membership test. `str.isdigit()` is Unicode-aware and
 *     read `'³³³³³'` and `'١٢٣٤٥'` as five digits, so a direct POST of either was ACCEPTED and
 *     stored as a payout target. Neither is a number anyone can be paid through.
 *   • web — `/\d/g`, which is ASCII `0-9` in JavaScript.
 *
 * A digit-LIKE character is NOT a new error on either side: it is simply not counted, so an
 * account that has fewer than five real digits left falls through the existing floor with the
 * existing `account_number_invalid`. This is the same class H7 pinned in `_digits`, which is a
 * different reader on the NRIC OCR path and was deliberately left alone.
 */
describe('RESOLVED: both sides read a digit as ASCII 0-9 (TD-264)', () => {
  const NON_ASCII = {
    'arabic-indic': '١٢٣٤٥',
    superscript: '³³³³³',
    subscript: '₅₅₅₅₅',
  }

  test('the api no longer counts with Unicode-aware isdigit()', () => {
    expect(validator).not.toMatch(/isdigit\(\)/)
    expect(validator).toMatch(/ch in '0123456789'/)
  })

  test('neither side counts a digit-like character — five of them stay below the floor', () => {
    for (const [label, value] of Object.entries(NON_ASCII)) {
      expect(`${label}: ${countDigits(value)}`).toBe(`${label}: 0`)
      // Five characters Python's isdigit() once read as five digits; both sides now read none.
      expect(value.length).toBe(5)
      expect(countDigits(value) < webFloor).toBe(true)
    }
  })

  test('not counted is not the same as refused — five real digits still pass', () => {
    // Exactly the form's rule, so the api may not be stricter: the stray superscript is
    // ignored and the five ASCII digits carry the account over the floor.
    expect(countDigits('³12345')).toBe(5)
    expect(countDigits('12-3456 7890')).toBe(10)
  })
})
