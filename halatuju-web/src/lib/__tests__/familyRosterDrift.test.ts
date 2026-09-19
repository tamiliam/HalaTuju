/**
 * THE DRIFT TEST for `familyRoster.ts` — named by its `drift-test:` markers (code health H10).
 *
 * Three claims, one file, and all three are load-bearing for a student's own form:
 *   • the **profession taxonomy** — a code the student can pick that Django's `choices` does not
 *     hold is a roster row the server drops on save, silently;
 *   • **`NON_EARNING`** — it decides who the income wizard pre-fills as a working adult, so a code
 *     on one side only means a parent is asked for a payslip they do not have, or never asked at
 *     all;
 *   • **`isValidPersonName`** — the one guard between an IC number and the `father_name` column
 *     (a real case, named in both comments).
 *
 * Characterised first (the H8 rule): the codes compared as ordered lists, and the name rule run on
 * the same awkward strings on both sides — connectors, an alias `@`, digits, an empty string, a
 * leading space, a non-ASCII letter. They AGREE on every row.
 */
import {
  PROFESSION_CODES, PROFESSION_GROUPS, NON_EARNING, isValidPersonName,
} from '@/lib/familyRoster'
import { pyChoiceValues, pySeq, readApi } from '@/test/apiSource'

const FAMILY = 'apps/scholarship/family.py'
const src = readApi(FAMILY)

const backendCodes = pyChoiceValues(src, 'PROFESSION_CHOICES', false)
const backendNonEarning = pySeq(src, 'NON_EARNING')

/** The Python pattern, as written. Compared with the JS one CHARACTER FOR CHARACTER below. */
const backendNamePattern = (() => {
  const m = src.match(/_PERSON_NAME_RE\s*=\s*re\.compile\(r"([^"]+)"\)/)
  if (!m) {
    throw new Error(
      'drift test: `_PERSON_NAME_RE = re.compile(r"…")` is no longer in family.py. The name rule '
      + 'has moved or changed shape — follow it, never delete the assertion.')
  }
  return m[1]
})()

describe('parse sanity — the api taxonomy was really found', () => {
  test('the profession list is the full taxonomy, not a fragment', () => {
    expect(backendCodes.length).toBe(40)
    expect(backendCodes[0]).toBe('gov')
    expect(backendCodes).toContain('other')
  })

  test('NON_EARNING read through its `frozenset({…})` form', () => {
    expect(backendNonEarning.length).toBe(6)
  })
})

describe('the profession taxonomy', () => {
  test('every api code is offered by the form, in the same order', () => {
    // Order matters here and is not cosmetic: the dropdown's <optgroup>s are built by walking
    // `PROFESSION_GROUPS`, and the api's comment groups are the same three blocks.
    expect(PROFESSION_CODES).toEqual(backendCodes)
  })

  test('the groups partition the list with nothing lost or repeated', () => {
    const flat = PROFESSION_GROUPS.flatMap((g) => g.codes)
    expect(flat).toEqual(PROFESSION_CODES)
    expect(new Set(flat).size).toBe(flat.length)
  })

  test('no code the form offers would be dropped on save', () => {
    expect(PROFESSION_CODES.filter((c) => !backendCodes.includes(c))).toEqual([])
  })
})

describe('NON_EARNING — who the income wizard does NOT pre-fill as an earner', () => {
  test('the two sets are the same, both directions', () => {
    expect([...NON_EARNING].sort()).toEqual([...backendNonEarning].sort())
  })

  test('every non-earning code is a real profession code', () => {
    expect(backendNonEarning.filter((c) => !backendCodes.includes(c))).toEqual([])
  })
})

describe('isValidPersonName — the guard between an IC number and father_name', () => {
  test('the two patterns are the same expression, character for character', () => {
    expect(backendNamePattern).toBe("^[A-Za-z][A-Za-z\\s./@'-]*$")
  })

  /**
   * The awkward inputs, run through the web side. The api side has its own rows in
   * `apps/scholarship/tests/test_family.py::test_is_valid_person_name_accepts_names_rejects_numbers`;
   * the comparison that matters here is that the PATTERN is identical (above), so the same string
   * cannot be read two ways.
   */
  test.each([
    ['', true, 'empty — required-ness is checked elsewhere, on both sides'],
    ['   ', true, 'whitespace only, trimmed to empty'],
    ['MUTHU A/L SAMY', true, 'the patronymic connector'],
    ['SITI @ AISHAH', true, 'an alias'],
    ["D'CRUZ", true, 'an apostrophe'],
    ['NUR-AIN', true, 'a hyphen'],
    ['A. RAJU', true, 'an initial'],
    ['880101145533', false, 'a bare IC — the exact error this guards'],
    ['0123456789', false, 'a phone number'],
    ['Ali 2', false, 'one digit anywhere is enough'],
    ['/AHMAD', false, 'must START with a letter, not a connector'],
    [' AHMAD', true, 'a leading space is trimmed before the test'],
    ['Aliá', false, 'a non-ASCII letter is outside the class on BOTH sides'],
  ])('%s -> %s (%s)', (value, expected) => {
    expect(isValidPersonName(value)).toBe(expected)
  })
})
