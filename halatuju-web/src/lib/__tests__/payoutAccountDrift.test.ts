/**
 * THE DRIFT TEST for the payout-account digit floor in `actionCentre.ts` — named by its
 * `drift-test:` marker (code health H9).
 *
 * The comment said the form "mirrors that floor client-side so the student sees WHICH field is
 * wrong inline, before the round-trip". The floor itself — five digits — is the api's, and it
 * exists so a fat-finger or a truncated OCR fragment can never become a **payout target**.
 *
 * Characterised first (the H8 rule). The FLOOR agrees: five on both sides. What does NOT agree is
 * the word *digit*, and that is pinned below as a disagreement, reported and NOT fixed — it is on
 * the money path, so which side moves is the owner's call (TD-264).
 */
import * as fs from 'fs'
import * as path from 'path'

import { countDigits } from '@/lib/actionCentre'
import { readApi } from '@/test/apiSource'

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
  const form = fs.readFileSync(
    path.join(__dirname, '..', '..', 'components', 'ActionCentre.tsx'), 'utf8')
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
 * ⚠ PINNED DISAGREEMENT (TD-264) — reported, not fixed, and no winner picked here. It is the
 * money path, so which side moves is the owner's.
 *
 * The two sides count different things:
 *   • api — `ch.isdigit()`, which is Unicode-aware. `'³³³³³'` and `'١٢٣٤٥'` are five digits, so a
 *     direct POST carrying either is ACCEPTED and stored as a payout target. Neither is a number
 *     anyone can pay into.
 *   • web — `/\d/g`, which is ASCII `0-9` only, so the form refuses all three.
 *
 * The web is the STRICTER side, so nothing the student's own form allows is refused by the server;
 * the exposure is the other way round, on a request that does not come from the form at all. This
 * is the same class H7 pinned in `_digits` (`re.sub(r'\D')` drops a superscript, `str.isdigit()`
 * keeps it) — now on the account a payment run reads.
 *
 * These assertions pin TODAY's behaviour on both sides. Either side changing turns one red, which
 * is what should happen: the fix must be a decision, not a drift.
 */
describe('PINNED: the two sides do not agree on what a digit is (TD-264)', () => {
  const NON_ASCII = {
    'arabic-indic': '١٢٣٤٥',
    superscript: '³³³³³',
    subscript: '₅₅₅₅₅',
  }

  test('the api still counts digits with Unicode-aware isdigit()', () => {
    expect(validator).toMatch(/ch\.isdigit\(\)/)
  })

  test('the web still counts ASCII digits only — and so refuses what the api would take', () => {
    for (const [label, value] of Object.entries(NON_ASCII)) {
      expect(`${label}: ${countDigits(value)}`).toBe(`${label}: 0`)
      // Five characters Python reads as five digits; the form reads none and blocks the save.
      expect(value.length).toBe(5)
    }
  })
})
