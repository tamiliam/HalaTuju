/**
 * THE DRIFT TEST for the email-kind lists — `partnerComms.ts` and `sponsorComms.ts`, named by
 * their `drift-test:` markers (code health H10).
 *
 * Each list is the ORDER a panel draws its emails in, and it is also, in practice, the list of
 * emails an organisation can edit at all. A kind the server stores and the panel does not name is
 * an email that goes out to real people with **no screen anywhere to change it** — which is the
 * whole reason these panels exist (request #10 moved five reviewer emails out of hard-coded prose
 * for exactly that reason). A kind the panel names and the server does not store is an empty row.
 *
 * Characterised first (the H8 rule): each web list compared against the model's `KIND_CHOICES`,
 * both directions, on the untouched tree. They AGREE — but not in the shape the comment claimed.
 * `partner_comms.KINDS` is FIFTEEN kinds reaching THREE surfaces, not eleven reaching two; the
 * fourth group is drawn by a card that carries no list at all. See the note below.
 */
import { PARTNER_EMAIL_KINDS, REVIEWER_EMAIL_KINDS } from '@/lib/partnerComms'
import { SPONSOR_EMAIL_KINDS } from '@/lib/sponsorComms'
import { pyChoiceValues, pySeq, readApi, readApiTree } from '@/test/apiSource'

// ⚠ `models.py` became the PACKAGE `models/` at code health H15 (2026-09-20). This guard picks
// its two `KIND_CHOICES` blocks BY CONTENT and insists on exactly one match each, so it reads the
// WHOLE package, not the one module the blocks live in today — the "and there is no second one"
// half of the rule is only true if everything is still being looked at. The floor stops the walk
// silently reading nothing.
const MODELS = 'apps/scholarship/models'
const modelsSrc = readApiTree(MODELS, 15)
const partnerSrc = readApi('apps/scholarship/partner_comms.py')
const sponsorSrc = readApi('apps/scholarship/sponsor_comms.py')

/**
 * `KIND_CHOICES` is a class attribute on more than one model, so it is selected by CONTENT — the
 * block that holds the kind this list is about — rather than by position. A model reordered in
 * `models.py` must not silently repoint this test at a different table.
 */
function kindChoicesContaining(marker: string): string[] {
  const hits = [...modelsSrc.matchAll(/^\s+KIND_CHOICES\s*=\s*\[[\s\S]*?\n\s+\]/gm)]
    .map((m) => pyChoiceValues(m[0], 'KIND_CHOICES'))
    .filter((values) => values.includes(marker))
  if (hits.length !== 1) {
    throw new Error(`drift test: expected exactly one KIND_CHOICES containing '${marker}', got ${hits.length}`)
  }
  return hits[0]
}

const partnerKinds = kindChoicesContaining('weekly_summary')
const sponsorKinds = kindChoicesContaining('credit_confirmed')

describe('parse sanity — the api kind tables were really found', () => {
  test('both lists parsed, and the two are different tables', () => {
    expect(partnerKinds.length).toBe(15)
    expect(sponsorKinds.length).toBe(9)
    expect(partnerKinds.filter((k) => sponsorKinds.includes(k))).toEqual([])
  })

  test('each service module derives its KINDS from the model, not from its own copy', () => {
    // If either stops deriving, the comparison below is against the wrong thing and this says so.
    expect(partnerSrc).toMatch(/^KINDS\s*=\s*tuple\(k for k, _ in PartnerEmailTemplate\.KIND_CHOICES\)/m)
    expect(sponsorSrc).toMatch(/^KINDS\s*=\s*tuple\(k for k, _ in SponsorEmailTemplate\.KIND_CHOICES\)/m)
  })
})

/**
 * ⚠ THREE SURFACES, NOT TWO — and the comment used to say otherwise.
 *
 * `partner_comms.KINDS` is FIFTEEN kinds. Characterising it found that the two hard-coded web
 * lists name eleven of them; the other four (`INVITE_KINDS`) are drawn by
 * `InvitationEmailsCard.tsx`, which carries **no list at all** and renders whatever the endpoint
 * sends. That card is the GOOD pattern — the very thing this arc converts the others into — so
 * the four are deliberately absent here, and this suite asserts that they stay absent rather than
 * being "helpfully" added to a list that would then need maintaining.
 *
 * So the invariant is not "two lists = the table". It is: **every stored kind reaches a screen**,
 * by being named on one of the two lists or by belonging to the server-driven group.
 */
describe('partner_comms.KINDS reaches a screen — across THREE surfaces', () => {
  const listed = [...PARTNER_EMAIL_KINDS, ...REVIEWER_EMAIL_KINDS] as string[]
  const inviteKinds = pySeq(modelsSrc, 'INVITE_KINDS', true)
  const reviewerKinds = pySeq(modelsSrc, 'REVIEWER_KINDS', true)
  const studentKinds = pySeq(modelsSrc, 'STUDENT_KINDS', true)

  test('parse sanity: the api\'s own groupings were found', () => {
    expect(inviteKinds.length).toBe(4)
    expect(reviewerKinds.length).toBe(5)
    expect(studentKinds).toEqual(['student_assigned'])
  })

  test('every stored kind reaches a screen — listed, or server-driven', () => {
    expect(partnerKinds.filter((k) => !listed.includes(k) && !inviteKinds.includes(k))).toEqual([])
  })

  test('neither list names a kind the server cannot store', () => {
    expect(listed.filter((k) => !partnerKinds.includes(k))).toEqual([])
  })

  test('the reviewer list is exactly the api\'s REVIEWER_KINDS', () => {
    expect([...REVIEWER_EMAIL_KINDS].sort()).toEqual([...reviewerKinds].sort())
  })

  test('the two lists do not overlap — a reviewer template on the Sources page is the bug', () => {
    const shared = (PARTNER_EMAIL_KINDS as readonly string[])
      .filter((k) => (REVIEWER_EMAIL_KINDS as readonly string[]).includes(k))
    expect(shared).toEqual([])
    expect(listed.length).toBe(partnerKinds.length - inviteKinds.length)
  })

  test('the four invitation kinds stay OFF both lists — that card needs no list', () => {
    expect(listed.filter((k) => inviteKinds.includes(k))).toEqual([])
  })

  test('`student_assigned` is a partner-screen kind and is last there', () => {
    // The one row whose recipient is the student, and the reason the card reads `to_student` from
    // the server rather than from this list.
    expect(partnerKinds).toContain('student_assigned')
    expect(PARTNER_EMAIL_KINDS[PARTNER_EMAIL_KINDS.length - 1]).toBe('student_assigned')
  })

  test('the weekly cron\'s two kinds are both on the partner screen', () => {
    const weekly = pySeq(partnerSrc, 'WEEKLY_KINDS')
    expect(weekly.length).toBe(2)
    expect(weekly.filter((k) => !(PARTNER_EMAIL_KINDS as readonly string[]).includes(k))).toEqual([])
  })
})

describe('sponsor_comms.KINDS vs the Emails panel', () => {
  test('the same nine, in both directions', () => {
    expect([...SPONSOR_EMAIL_KINDS].sort()).toEqual([...sponsorKinds].sort())
  })

  test('`referral_invite` is stored and named — the one kind sent to a non-account holder', () => {
    expect(sponsorKinds).toContain('referral_invite')
    expect(SPONSOR_EMAIL_KINDS).toContain('referral_invite')
    expect(pySeq(sponsorSrc, 'NON_ACCOUNT_KINDS')).toEqual(['referral_invite'])
  })

  test('every kind has a placeholder allowlist — an unnamed kind supplies no tokens at all', () => {
    // `PLACEHOLDERS` is the privacy control: a kind missing from it resolves to an empty set, so a
    // template saved against it would refuse every token rather than fail loudly.
    const declared = [...sponsorSrc.matchAll(/^\s{4}'([a-z_]+)':\s*\{/gm)].map((m) => m[1])
    expect(sponsorKinds.filter((k) => !declared.includes(k))).toEqual([])
  })
})
