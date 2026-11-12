/**
 * TD-254 DRIFT — the refusal vocabulary is the SERVER'S.
 *
 * `CLAIM_REFUSAL_COPY` (src/lib/profileClaim.ts) maps a refusal code to the sentence a student
 * reads. The codes are declared once, in Python, in `REFUSAL_CODES`. This READS the Python and
 * fails when a code gains no copy, or when copy names a code the server cannot send.
 *
 * ⚠ It also asserts it actually found the Python list, so a moved file or a renamed constant
 * fails loudly instead of quietly watching nothing.
 */
import { CLAIM_REFUSAL_COPY } from '@/lib/profileClaim'
import { readApi } from '@/test/apiSource'

// ⚠ `readApi` with a repo-relative literal, not a hand-rolled `path.resolve` (TD-276, code health
// H16): it throws a NAMED failure when the module moves instead of an `ENOENT`, and the api's own
// `test_web_guards_read_live_paths.py` extracts this literal, so a backend sprint that moves
// `profile_claim.py` goes red in its own gate rather than killing this file silently (H13).
const PY = 'apps/courses/profile_claim.py'

/** The strings inside the `REFUSAL_CODES = ( … )` tuple. */
function serverRefusalCodes(): string[] {
  const src = readApi(PY)
  const block = src.match(/REFUSAL_CODES = \(([\s\S]*?)\n\)/)
  if (!block) throw new Error(`REFUSAL_CODES not found in ${PY}`)
  return (block[1].match(/'([a-z_]+)'/g) || []).map((q) => q.slice(1, -1))
}

describe('the server owns the refusal vocabulary', () => {
  const codes = serverRefusalCodes()

  it('found a real list in the Python, not an empty match', () => {
    expect(codes.length).toBeGreaterThan(10)
    expect(codes).toContain('confirm_removed')
    expect(codes).toContain('no_verified_contact')
  })

  it('every code the server can send has copy here', () => {
    expect(codes.filter((c) => !(c in CLAIM_REFUSAL_COPY))).toEqual([])
  })

  it('and this file invents no code the server cannot send', () => {
    expect(Object.keys(CLAIM_REFUSAL_COPY).filter((c) => !codes.includes(c))).toEqual([])
  })
})
