/**
 * THE DRIFT TEST for the two officer gates in `officerCockpit.ts` — named by their `drift-test:`
 * markers (code health H9). Both decide what an officer may DO, and both are irreversible or
 * near-irreversible if the screen and the server disagree:
 *
 *   • **Reject-this-student** (`ORG_REJECT_FROM` / `canOrgReject`) — immediate and irreversible,
 *     no cool-off, no cancel window. A card rendered outside the server's set is not a cosmetic
 *     bug; it is a button that looks live and answers 400.
 *   • **The assignment picker** (`assignOptions`) — offering a name the assign endpoint refuses
 *     as `bad_assignee` puts a dead option in front of somebody delegating a case.
 *
 * Characterised first (the H8 rule): each web answer was put beside the api's on the same inputs
 * — every DB status × every role for the reject gate, and every REVIEW_ROLE × super/non-super ×
 * paused × gift for the picker — on the untouched tree. They AGREE on every row, with ONE
 * documented asymmetry that is deliberate and is pinned rather than removed: the CURRENT assignee
 * is always offered, whatever their role (bug #66).
 */
import { ORG_REJECT_FROM, canOrgReject, assignOptions } from '@/lib/officerCockpit'
import { APPLICATION_STATUSES } from '@/lib/applicationStatus'
import { ROLE_NAMES } from '@/lib/navigation'
import { pySeq, readApi } from '@/test/apiSource'

const SERVICES = 'apps/scholarship/services.py'
/**
 * ⚠ `views_admin.py` became the PACKAGE `views_admin/` at code health H11/H12, and the two gates
 * this file reads landed in two different modules. The path followed the code (H13) — the rule is
 * never to delete the assertion. Both files are read and joined, so `viewBody` still asserts the
 * class appears EXACTLY once across them; a class that moves again, or is duplicated, still throws.
 */
const VIEWS = [
  'apps/scholarship/views_admin/applications.py',   // AdminOrgRejectView
  'apps/scholarship/views_admin/verdict.py',        // AdminAssignReviewerView
]
const servicesSrc = readApi(SERVICES)
const viewsSrc = VIEWS.map(readApi).join('\n')

const backendRejectFrom = pySeq(servicesSrc, 'ORG_REJECT_FROM')
const reviewRoles = pySeq(servicesSrc, 'REVIEW_ROLES')

/** The body of a view class, for reading a gate that lives in code rather than in a constant. */
function viewBody(name: string): string {
  const parts = viewsSrc.split(`\nclass ${name}(`)
  if (parts.length !== 2) throw new Error(`drift test: no single class ${name} in ${VIEWS.join(', ')}`)
  return parts[1].split('\nclass ')[0]
}

describe('parse sanity — the api rules were really found', () => {
  test('ORG_REJECT_FROM read as a non-empty tuple of statuses', () => {
    expect(backendRejectFrom.length).toBeGreaterThan(0)
    expect(backendRejectFrom.every((s) => APPLICATION_STATUSES.includes(s as never))).toBe(true)
  })

  test('REVIEW_ROLES read as real admin roles', () => {
    expect(reviewRoles.length).toBeGreaterThanOrEqual(4)
    expect(reviewRoles.filter((r) => !ROLE_NAMES.includes(r as never))).toEqual([])
  })
})

describe('the org-admin reject gate — the STATUS half', () => {
  test('the web set is services.ORG_REJECT_FROM, both directions', () => {
    expect([...ORG_REJECT_FROM].sort()).toEqual([...backendRejectFrom].sort())
  })

  test('the card is offered at exactly those statuses and nowhere else', () => {
    const offered = APPLICATION_STATUSES.filter(
      (status) => canOrgReject({ isSuper: false, role: 'org_admin', status }))
    expect([...offered].sort()).toEqual([...backendRejectFrom].sort())
  })
})

describe('the org-admin reject gate — the ROLE half', () => {
  /**
   * `AdminOrgRejectView` NARROWS `_require_app_write` (super / org_admin / qc / assigned reviewer)
   * to the two org-super roles. That narrowing is a line of code, not a constant, so it is read
   * as a line of code — and the assertion is deliberately specific, because the failure it exists
   * to catch is somebody widening it back to `_require_app_write`'s set.
   */
  const body = viewBody('AdminOrgRejectView')

  test('the view still narrows to super or org_admin', () => {
    expect(body).toMatch(/if not \(admin\.is_super or admin\.role == 'org_admin'\):/)
    expect(body).toMatch(/_deny_role\(\)/)
  })

  test('the cockpit offers the card to those two roles and refuses every other', () => {
    const status = backendRejectFrom[0]
    expect(canOrgReject({ isSuper: true, role: null, status })).toBe(true)
    for (const role of ROLE_NAMES) {
      // `super` is carried by the `isSuper` flag, never by the role string alone.
      const expected = role === 'org_admin'
      expect(canOrgReject({ isSuper: false, role, status })).toBe(expected)
    }
  })
})

describe('the assignment picker vs the api\'s bad_assignee rule', () => {
  const body = viewBody('AdminAssignReviewerView')

  test('a non-super may still assign only an own-org `reviewer` (the api side, read as written)', () => {
    expect(body).toMatch(/reviewer\.role != 'reviewer'/)
    expect(body).toMatch(/reviewer\.owning_organisation_id != admin\.owning_organisation_id/)
    expect(body).toMatch(/is_active=True/)
    expect(body).toMatch(/bad_assignee/)
  })

  /**
   * The org fence and `is_active` are the LIST endpoint's job (`AdminAssignableAdminsView` filters
   * both), so the picker never sees a cross-org or revoked name to offer. What the picker itself
   * must get right is the ROLE narrowing, because the list is deliberately wider than the write:
   * it returns every REVIEW_ROLE so a super can pick any of them.
   */
  const staff = reviewRoles.map((role, i) => ({ id: i + 1, name: `Staff ${role}`, role }))

  test('the list endpoint is wider than the write — which is why the picker must narrow', () => {
    expect(reviewRoles.length).toBeGreaterThan(1)
    expect(reviewRoles).toContain('reviewer')
  })

  test('a non-super is offered only reviewers', () => {
    const offered = assignOptions(staff, { isSuper: false, currentAssigneeId: null })
    expect(offered.map((o) => o.role)).toEqual(['reviewer'])
  })

  test('a super is offered every review-capable role, and no more', () => {
    const offered = assignOptions(staff, { isSuper: true, currentAssigneeId: null })
    expect([...offered.map((o) => o.role)].sort()).toEqual([...reviewRoles].sort())
  })

  /**
   * ⚠ PINNED ASYMMETRY, deliberate (bug #66, and the module says so): the CURRENT assignee is
   * unioned in whatever their role, so a case assigned to a qc who was later promoted does not
   * read "Unassigned". A non-super re-selecting that person would be refused `bad_assignee` — but
   * re-selecting the value a `<select>` already holds fires no change, so no request is made.
   * Pinned, not removed: dropping them is the bug this rule exists to prevent.
   */
  test('the current assignee is offered even where the write endpoint would refuse them', () => {
    const nonReviewer = staff.find((s) => s.role !== 'reviewer')
    expect(nonReviewer).toBeDefined()
    const offered = assignOptions(staff, {
      isSuper: false, currentAssigneeId: nonReviewer!.id,
    })
    expect(offered.map((o) => o.id)).toContain(nonReviewer!.id)
    // …and they are never disabled: a select whose current value is disabled cannot show its state.
    expect(offered.find((o) => o.id === nonReviewer!.id)!.disabled).toBe(false)
  })

  test('a paused reviewer is greyed, never removed — the same #66 reason', () => {
    const withPaused = [
      { id: 90, name: 'Active', role: 'reviewer', paused: false },
      { id: 91, name: 'Paused', role: 'reviewer', paused: true },
    ]
    const offered = assignOptions(withPaused, { isSuper: false, currentAssigneeId: null })
    expect(offered.map((o) => o.id)).toEqual([90, 91])
    expect(offered.map((o) => o.disabled)).toEqual([false, true])
    expect(offered[1].reason).toBe('paused')
  })

  test('a blank gift on either side greys nobody — the permissive default the live roster carries', () => {
    const roster = [
      { id: 80, name: 'Every gift', role: 'reviewer', programme_id: null },
      { id: 81, name: 'Gift 7', role: 'reviewer', programme_id: 7 },
    ]
    for (const applicationProgrammeId of [null, undefined]) {
      const offered = assignOptions(roster, {
        isSuper: false, currentAssigneeId: null, applicationProgrammeId,
      })
      expect(offered.map((o) => o.disabled)).toEqual([false, false])
    }
    // Only a KNOWN mismatch on both sides greys, and even then it greys, never removes.
    const scoped = assignOptions(roster, {
      isSuper: false, currentAssigneeId: null, applicationProgrammeId: 9,
    })
    expect(scoped.map((o) => o.disabled)).toEqual([false, true])
    expect(scoped[1].reason).toBe('otherGift')
  })
})
