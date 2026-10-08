/**
 * THE DRIFT TEST for the IC place-of-birth codes the browser accepts — `VALID_STATE_CODES` in
 * `lib/ic-utils.ts` (named by its `drift-test:` marker) against the server's own list in
 * `halatuju_api/apps/courses/profile_claim.py`. Request #31 review, 2026-10-08.
 *
 * ⚠ BOTH COPIES WERE WRONG THE SAME WAY: they stopped at 24, so an IC born in Sabah under 47-49
 * (or anywhere under 25-59) was refused at the profile step and could never reach an intake's
 * "Born in" rule. The server copy is held to `birth_state.CODE_TO_STATE` by `test_birth_state.py`;
 * this holds the browser to the server.
 */
import { VALID_STATE_CODES, validateIc } from '@/lib/ic-utils'
import { pySeq, readApi } from '@/test/apiSource'

const apiCodes = pySeq(readApi('apps/courses/profile_claim.py'), 'VALID_STATE_CODES')

test('parse sanity — the server list was really found', () => {
  expect(apiCodes.length).toBeGreaterThanOrEqual(58)
  expect(apiCodes).toEqual(expect.arrayContaining(['12', '47', '59', '82']))
})

test('the browser accepts exactly the codes the server accepts', () => {
  expect([...VALID_STATE_CODES].sort()).toEqual([...apiCodes].sort())
})

test("Sabah's later codes pass; 00, 17-20 and other foreign codes still do not", () => {
  for (const code of ['47', '48', '49', '58', '59']) {
    expect(validateIc(`080505-${code}-1234`)).toBeNull()
  }
  for (const code of ['00', '17', '20', '60', '99']) {
    expect(validateIc(`080505-${code}-1234`)).toBe('Invalid state code in IC number')
  }
})
