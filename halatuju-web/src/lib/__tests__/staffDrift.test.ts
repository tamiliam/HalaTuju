/**
 * THE DRIFT TEST for the two staff-lifecycle mirrors — `invitations.ts` and `reviewerProfile.ts`,
 * named by their `drift-test:` markers (code health H10).
 *
 *   • **`InvitationStatus`** is the vocabulary the staff table renders a word and a colour from.
 *     The server owns the value; the union here is what the screen can HANDLE. A status the
 *     server can emit and this union does not name falls through to whatever the default branch
 *     draws — and the api's own docstring is emphatic that `no_reply` is not `expired`, because
 *     telling an org_admin an invitation "expired" sends them looking for a password that never
 *     existed.
 *   • **`missingReviewerFields`** paints the `*` markers and the "still needed" banner and decides
 *     the redirect after a save. The BACKEND flag is the real gate, so a web copy that asks for
 *     LESS strands a reviewer in a redirect loop (saved, still incomplete, sent back), and one
 *     that asks for MORE marks a field compulsory that nothing enforces.
 *
 * Characterised first (the H8 rule): the status words listed on both sides, and the reviewer gate
 * run field-by-field against the api's own compulsory set. They AGREE.
 */
import { REQUIRED_REVIEWER_FIELDS, missingReviewerFields, reviewerProfileComplete } from '@/lib/reviewerProfile'
import type { ReviewerProfile } from '@/lib/admin-api'
import { pySeq, readApi } from '@/test/apiSource'
import { readWeb } from '@/test/sourceGuard'

const INVITATIONS = 'apps/scholarship/invitations.py'
const ONBOARDING = 'apps/scholarship/reviewer_onboarding.py'
const invitationsSrc = readApi(INVITATIONS)
const onboardingSrc = readApi(ONBOARDING)

/** Every status word `status_of` can return, read from the constants it returns. */
const backendStatuses = (() => {
  const names = [...invitationsSrc.matchAll(/^([A-Z_]+) = '([a-z_]+)'$/gm)]
    .filter(([, , value]) => value.length > 0)
  const byName = Object.fromEntries(names.map((m) => [m[1], m[2]]))
  const body = invitationsSrc.split('def status_of(')[1]
  if (!body) throw new Error(`drift test: status_of is no longer in ${INVITATIONS}`)
  // ⚠ NOT `return X` — one arm is a ternary (`return EXPIRED if … else NO_REPLY`), and matching
  // the keyword would have found four words where the function can produce five. Read every
  // status CONSTANT the body names instead; that is the property, not the statement shape.
  const fn = body.split('\ndef ')[0]
  const named = [...new Set([...fn.matchAll(/\b([A-Z][A-Z_]+)\b/g)].map((m) => m[1]))]
    .filter((n) => n in byName)
  if (named.length === 0) throw new Error('drift test: status_of names no status constant at all')
  return [...new Set(named.map((n) => byName[n]))]
})()

/** The union in `invitations.ts` — a TS type has no runtime, so it is read as source text. */
const webStatuses = (() => {
  // ⚠ `readWeb`, not a bare `readFileSync` (TD-276) — module scope, so an ENOENT here used to
  // take the whole file out of the run instead of naming what moved.
  const text = readWeb('src/lib/invitations.ts',
    'the `InvitationStatus` union has no runtime, so it is read as source text; it must hold '
    + 'exactly the five words the api\'s `status_of` can return')
  const m = text.match(/export type InvitationStatus\s*=\s*([^\n]+)/)
  if (!m) throw new Error('drift test: `export type InvitationStatus = …` not found')
  return [...m[1].matchAll(/'([a-z_]+)'/g)].map((x) => x[1])
})()

describe('parse sanity — the api rules were really found', () => {
  test('status_of returns five distinct words', () => {
    expect(backendStatuses.length).toBe(5)
    expect(backendStatuses).toContain('no_reply')
  })

  test('the web union parsed', () => {
    expect(webStatuses.length).toBe(5)
  })

  test('the reviewer gate\'s field lists parsed', () => {
    expect(pySeq(onboardingSrc, 'REQUIRED_TEXT_FIELDS').length).toBe(4)
    expect(pySeq(onboardingSrc, 'LANG_FIELDS').length).toBe(3)
    expect(pySeq(onboardingSrc, 'SPEAKS')).toEqual(['conversational', 'fluent'])
  })
})

describe('InvitationStatus vs invitations.status_of', () => {
  test('the same five words, both directions', () => {
    expect([...webStatuses].sort()).toEqual([...backendStatuses].sort())
  })

  test('`no_reply` and `expired` are BOTH there — they are not the same thing', () => {
    // The api's docstring is explicit: a Google or already-registered invitee had no credential
    // issued, so nothing of theirs has expired. Collapsing the two is the bug this pair guards.
    expect(webStatuses).toContain('no_reply')
    expect(webStatuses).toContain('expired')
    expect(invitationsSrc).toMatch(/EXPIRED if inv\.credential_issued else NO_REPLY/)
  })
})

describe('missingReviewerFields vs reviewer_onboarding.reviewer_profile_complete', () => {
  const textFields = pySeq(onboardingSrc, 'REQUIRED_TEXT_FIELDS')
  const langFields = pySeq(onboardingSrc, 'LANG_FIELDS')
  const speaks = pySeq(onboardingSrc, 'SPEAKS')

  /** A profile the api would call COMPLETE: every compulsory text field filled, one language. */
  const completeProfile = (): ReviewerProfile => ({
    ...Object.fromEntries(textFields.map((f) => [f, 'filled'])),
    ...Object.fromEntries(langFields.map((f) => [f, ''])),
    [langFields[0]]: speaks[0],
    graduation_year: 2015,
  } as unknown as ReviewerProfile)

  test('the web\'s compulsory list is the api\'s, plus the two it says it adds', () => {
    // `name` lives on PartnerAdmin, not ReviewerProfile; `languages` is the web's single key for
    // the api's "at least one of three". `graduation_year` is checked on its own on both sides.
    expect([...REQUIRED_REVIEWER_FIELDS].sort())
      .toEqual([...textFields, 'graduation_year', 'name', 'languages'].sort())
  })

  test('a profile the api calls complete is complete here too', () => {
    expect(missingReviewerFields('A Reviewer', completeProfile())).toEqual([])
    expect(reviewerProfileComplete('A Reviewer', completeProfile())).toBe(true)
  })

  test.each(['', '   '])('a blank name (%p) is incomplete, as `admin.name.strip()` is', (name) => {
    expect(missingReviewerFields(name, completeProfile())).toEqual(['name'])
  })

  test.each(pySeq(onboardingSrc, 'REQUIRED_TEXT_FIELDS'))(
    'emptying `%s` makes it incomplete on both sides', (field) => {
      const rp = { ...completeProfile(), [field]: '   ' } as ReviewerProfile
      expect(missingReviewerFields('A Reviewer', rp)).toEqual([field])
    })

  test('no ReviewerProfile at all is incomplete', () => {
    expect(reviewerProfileComplete('A Reviewer', null)).toBe(false)
  })

  test('a missing graduation year is incomplete — the api checks it on its own', () => {
    const rp = { ...completeProfile(), graduation_year: null } as unknown as ReviewerProfile
    expect(missingReviewerFields('A Reviewer', rp)).toEqual(['graduation_year'])
    expect(onboardingSrc).toMatch(/if not rp\.graduation_year:\s*\n\s+return False/)
  })

  test('BREADTH, not all three: one spoken language is enough, none is not', () => {
    const none = {
      ...completeProfile(),
      ...Object.fromEntries(langFields.map((f) => [f, ''])),
    } as unknown as ReviewerProfile
    expect(missingReviewerFields('A Reviewer', none)).toEqual(['languages'])
    for (const field of langFields) {
      for (const level of speaks) {
        const one = { ...none, [field]: level } as unknown as ReviewerProfile
        expect(missingReviewerFields('A Reviewer', one)).toEqual([])
      }
    }
    // …and a level BELOW the bar does not count, on either side.
    const weak = { ...none, [langFields[0]]: 'basic' } as unknown as ReviewerProfile
    expect(missingReviewerFields('A Reviewer', weak)).toEqual(['languages'])
  })
})
