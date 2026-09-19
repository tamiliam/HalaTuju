/**
 * THE DRIFT TEST for `clauseNumbering.ts` and `sponsorTerms.ts` — named by their `drift-test:`
 * markers (code health H10). Two documents people sign, two rules copied into the browser:
 *
 *   • **Clause numbering.** The numbers are COMPUTED, never stored, on both sides — so the editor
 *     and the PDF each derive them independently. A drift means a sponsor is shown "3.2." in the
 *     editor and signs a document that calls the same clause something else.
 *   • **`quizComplete` / `setQuizFlag`.** The first decides whether the editor lets a version
 *     publish; the server then applies its own `quiz_payload_valid` and would refuse. The second
 *     wipes the payloads when the flag is cleared, because the server's `replace_sections` does —
 *     and without it the editor shows "no checkpoint" while still holding answers that the next
 *     save silently discards.
 *
 * Characterised first (the H8 rule): the clause fixtures taken from the api's OWN test rather than
 * retyped, and the quiz rule run on the same malformed payloads (two options, four, a blank, a
 * non-string, `correct` out of range, `correct` as a string). They AGREE.
 */
import { clauseNumbers, normaliseLevels, MAX_CLAUSE_LEVEL } from '@/lib/clauseNumbering'
import { quizComplete, setQuizFlag } from '@/lib/sponsorTerms'
import type { SponsorQuizPayload, SponsorTermsSection } from '@/lib/admin-api'
import { readApi } from '@/test/apiSource'

const CONTRACTS = 'apps/scholarship/contracts.py'
const TERMS = 'apps/scholarship/sponsor_terms.py'
const contractsSrc = readApi(CONTRACTS)
const termsSrc = readApi(TERMS)
const contractsTestSrc = readApi('apps/scholarship/tests/test_contracts.py')

/**
 * The fixtures the api's own suite pins, lifted from it rather than retyped here. That is what
 * makes this a SHARED fixture instead of two lists that happen to match today: change the
 * expectation on the api side and this test fails, which is the whole point.
 */
function apiCase(name: string): { input: number[]; expected: string[] } {
  const body = contractsTestSrc.split(`def ${name}(`)[1]
  if (!body) throw new Error(`drift test: ${name} is no longer in test_contracts.py`)
  const block = body.split('\n    def ')[0]
  const lists = [...block.matchAll(/\[([^\]]*)\]/g)].map((m) => m[1])
  if (lists.length < 2) throw new Error(`drift test: ${name} no longer holds an input and an expectation`)
  return {
    input: lists[0].split(',').map((s) => Number(s.trim())).filter((n) => !Number.isNaN(n)),
    expected: [...lists[1].matchAll(/'([^']*)'/g)].map((m) => m[1]),
  }
}

describe('parse sanity — the api rules and fixtures were really found', () => {
  test('the shared clause fixture parsed as an input and an expectation', () => {
    const c = apiCase('test_clause_numbers_three_levels')
    expect(c.input).toEqual([0, 1, 1, 2, 2, 0, 1, 2])
    expect(c.expected).toHaveLength(8)
  })

  test('MAX_CLAUSE_LEVEL agrees, so "three levels" means the same thing on both sides', () => {
    expect(contractsSrc).toMatch(new RegExp(`^MAX_CLAUSE_LEVEL\\s*=\\s*${MAX_CLAUSE_LEVEL}$`, 'm'))
  })

  test('the quiz rule is still the api\'s structural contract', () => {
    const fn = termsSrc.split('def quiz_payload_valid(')[1].split('\ndef ')[0]
    expect(fn).toMatch(/len\(options\) != 3/)
    expect(fn).toMatch(/payload\.get\('correct'\) in \(0, 1, 2\)/)
  })
})

describe('clause numbering — the web computes what the api computes', () => {
  test('the three-level fixture, taken from the api\'s own test', () => {
    const c = apiCase('test_clause_numbers_three_levels')
    expect(clauseNumbers(c.input)).toEqual(c.expected)
  })

  test('normalise forbids skipping and forces the first to zero — the api\'s own rows', () => {
    const body = contractsTestSrc
      .split('def test_normalise_forbids_skipping_and_forces_first_zero(')[1]
      .split('\n    def ')[0]
    const rows = [...body.matchAll(/normalise_levels\(\[([^\]]*)\]\), \[([^\]]*)\]/g)]
    expect(rows.length).toBe(2)          // parse sanity: both rows found
    for (const row of rows) {
      const nums = (s: string) => s.split(',').map((x) => Number(x.trim()))
      expect(normaliseLevels(nums(row[1]))).toEqual(nums(row[2]))
    }
  })

  test('roman resets under each new parent, and runs past V', () => {
    expect(clauseNumbers([0, 2, 2, 0, 2])).toEqual(['1.', 'I.', 'II.', '2.', 'I.'])
    expect(clauseNumbers([0, ...Array(6).fill(2)]))
      .toEqual(['1.', 'I.', 'II.', 'III.', 'IV.', 'V.', 'VI.'])
  })

  test('a level deeper than the maximum is clamped, not carried', () => {
    expect(normaliseLevels([0, 1, 9])).toEqual([0, 1, 2])
    expect(clauseNumbers([0, 1, 9])).toEqual(['1.', '1.1.', 'I.'])
  })
})

describe('the sponsor-terms checkpoint rule', () => {
  const ok = (over: Partial<SponsorQuizPayload> = {}) =>
    ({ options: ['a', 'b', 'c'], correct: 0, ...over } as SponsorQuizPayload)

  test('a well-formed payload is complete', () => {
    expect(quizComplete(ok())).toBe(true)
    expect(quizComplete(ok({ correct: 2 }))).toBe(true)
  })

  test.each([
    ['null', null],
    ['undefined', undefined],
    ['two options', { options: ['a', 'b'], correct: 0 }],
    ['four options', { options: ['a', 'b', 'c', 'd'], correct: 0 }],
    ['a blank option', { options: ['a', '   ', 'c'], correct: 0 }],
    ['a non-string option', { options: ['a', 3, 'c'], correct: 0 }],
    ['options not a list', { options: 'abc', correct: 0 }],
    ['correct out of range', { options: ['a', 'b', 'c'], correct: 3 }],
    ['correct missing', { options: ['a', 'b', 'c'] }],
    ['correct as a string', { options: ['a', 'b', 'c'], correct: '0' }],
  ])('%s is NOT complete — the same answer the server gives', (_label, payload) => {
    expect(quizComplete(payload as SponsorQuizPayload)).toBe(false)
  })

  test('`correct: 0` is complete — a falsy index is a real answer', () => {
    // The row a `if (!payload.correct)` implementation would get wrong, on either side.
    expect(quizComplete(ok({ correct: 0 }))).toBe(true)
    expect(termsSrc).toMatch(/in \(0, 1, 2\)/)
  })

  test('clearing the flag wipes all three payloads, as replace_sections does', () => {
    const section = {
      order: 1, heading_en: 'H', body_en: 'B', is_quiz_candidate: true,
      quiz_en: ok(), quiz_ms: ok(), quiz_ta: ok(), quiz_generated_model: 'gemini-2.5-pro',
    } as unknown as SponsorTermsSection
    const off = setQuizFlag(section, false)
    expect(off.quiz_en).toEqual({})
    expect(off.quiz_ms).toEqual({})
    expect(off.quiz_ta).toEqual({})
    expect(off.quiz_generated_model).toBe('')
    // The api side, read as written: the payload survives only while the flag is on.
    expect(termsSrc).toMatch(/payload if \(flagged and isinstance\(payload, dict\)\) else \{\}/)
    expect(termsSrc).toMatch(/if flagged else ''/)
  })

  test('setting the flag ON keeps whatever is there — only clearing wipes', () => {
    const section = {
      order: 1, heading_en: 'H', body_en: 'B', is_quiz_candidate: false,
      quiz_en: ok(), quiz_ms: {}, quiz_ta: {}, quiz_generated_model: '',
    } as unknown as SponsorTermsSection
    expect(setQuizFlag(section, true).quiz_en).toEqual(ok())
  })
})
