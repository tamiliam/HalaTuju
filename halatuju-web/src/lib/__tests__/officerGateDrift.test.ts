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
 *
 * ⚠ REQUEST #39 SPRINT 3: the picker's narrowing is SERVED. `AdminAssignableAdminsView` sends
 * `assignable` per row from `services.may_assign_to`, which the assign endpoint calls too, so the
 * picker no longer re-derives the rule — it reads the flag, and falls back to the old role rule only
 * for a payload without it. `REVIEW_ROLES` became `review` + `R1_SUPER_TARGET_ROLES` (the super's
 * override, roadmap R1); this file reads both from the api, as before.
 */
import { ORG_REJECT_FROM, canOrgReject, assignOptions } from '@/lib/officerCockpit'
import { APPLICATION_STATUSES } from '@/lib/applicationStatus'
import { ROLE_NAMES } from '@/lib/navigation'
import { pySeq, readApi } from '@/test/apiSource'
import { DOOR_KEYS } from '@/lib/pageDoors'

/**
 * ⚠ `services.py` became the PACKAGE `services/` at code health H15 (2026-09-20), and the two
 * constants this file reads landed in two different modules — the same shape as `VIEWS` below,
 * and the same rule: the path follows the code, the assertion is never deleted.
 */
const SERVICES = [
  'apps/scholarship/services/decline.py',      // ORG_REJECT_FROM
  'apps/scholarship/services/assignment.py',   // R1_SUPER_TARGET_ROLES, may_assign_to
]
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
const servicesSrc = SERVICES.map(readApi).join('\n')
const viewsSrc = VIEWS.map(readApi).join('\n')

const backendRejectFrom = pySeq(servicesSrc, 'ORG_REJECT_FROM')
/** Who could be given a case before #39: the `reviewer` preset (which holds `review`), a super, and
 *  the R1 override's roles — the list a super was offered, read from the api. */
const reviewRoles = ['reviewer', 'super', ...pySeq(servicesSrc, 'R1_SUPER_TARGET_ROLES')]

/** The body of a top-level api function, for reading a rule that lives in code. */
function pyFunc(src: string, name: string): string {
  const parts = src.split(`\ndef ${name}(`)
  if (parts.length !== 2) throw new Error(`drift test: no single def ${name} in ${SERVICES.join(', ')}`)
  return parts[1].split('\ndef ')[0]
}

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

  test('the review targets read as real admin roles', () => {
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
    // M3b G5: the narrowing is the `students.approve` door (`surface_gates.may_decide`), no longer a role
    // test. The role arm must NOT creep back in, and the door must be the one that opens on that key.
    expect(body).toMatch(/if not surface_gates\.may_decide\(admin\):/)
    expect(body).toMatch(/_deny_role\(\)/)
    expect(body).not.toMatch(/admin\.role == 'org_admin'/)
    expect(readApi('apps/scholarship/surface_gates.py')).toMatch(
      /def may_decide\(admin\):[\s\S]*?opens_door\(admin, 'decide'\)/)
    expect(readApi('apps/courses/staff_tables.py')).toMatch(/'decide':\s*\('students\.approve',\)/)
    expect(DOOR_KEYS.decide).toEqual(['students.approve'])
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

  test('every caller assigns only someone in Reviewers; a non-super only their own org (T1, read as written)', () => {
    // M2d A1: the endpoint's pre-check is `may_hand_to` (the T1 rule) so a person who has not signed in
    // reaches the service and is told `not_signed_in`; `may_assign_to` (what the picker serves) is
    // `may_hand_to` AND signed in, so the two still cannot disagree on anyone the picker offers.
    expect(body).toMatch(/not may_hand_to\(admin, reviewer\)/)
    expect(body).toMatch(/is_active=True/)
    expect(body).toMatch(/bad_assignee/)
    expect(pyFunc(servicesSrc, 'may_assign_to')).toMatch(/return has_signed_in\(target\) and may_hand_to\(caller, target\)/)
    const rule = pyFunc(servicesSrc, 'may_hand_to')
    expect(rule).toMatch(/staff_tables\.in_reviewers\(target\) and is_review_target\(target\)/)
    // M3b E3: nobody hands a case to themselves, a super included; M3b G5: the org admin's arm reads
    // the `assign` door (`students.edit`), not the role.
    expect(rule).toMatch(/if caller\.pk == target\.pk:\s*return False/)
    expect(rule).toMatch(/surface_gates\.may_assign\(caller\)/)
    expect(rule).not.toMatch(/caller\.role == 'org_admin'/)
    expect(readApi('apps/scholarship/surface_gates.py')).toMatch(
      /def may_assign\(admin\):[\s\S]*?opens_door\(admin, 'assign'\)/)
    expect(readApi('apps/courses/staff_tables.py')).toMatch(/'assign':\s*\('students\.edit',\)/)
    expect(DOOR_KEYS.assign).toEqual(['students.edit'])
    expect(rule).toMatch(/target\.owning_organisation_id == caller\.owning_organisation_id/)
    expect(rule).toMatch(/if caller\.is_super:/)
  })

  test('the list serves the same rule as `assignable`, so the picker reads it, not a role', () => {
    const list = readApi('apps/scholarship/views_admin/lifecycle.py')
    expect(list).toMatch(/'assignable': may_assign_to\(admin, a\)/)
    // A served flag wins over the role fallback in both directions.
    const served = [
      { id: 1, name: 'Fin + Review', role: 'finance', assignable: true },
      { id: 2, name: 'Reviewer without review', role: 'reviewer', assignable: false },
    ]
    for (const isSuper of [false, true]) {
      expect(assignOptions(served, { isSuper, currentAssigneeId: null }).map((o) => o.id)).toEqual([1])
    }
    // …and the current assignee is still unioned in (bug #66), whatever the flag says.
    expect(assignOptions(served, { isSuper: false, currentAssigneeId: 2 }).map((o) => o.id))
      .toEqual([1, 2])
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

  test('an empty gift list or an unknown case gift greys nobody — the live roster’s default', () => {
    const roster = [
      { id: 80, name: 'Every gift', role: 'reviewer', gifts: [] },
      { id: 81, name: 'Gift 7', role: 'reviewer', gifts: [{ id: 7 }] },
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
