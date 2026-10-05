/**
 * THE DRIFT TEST for the two student-facing rules in `scholarship.ts` — named by their
 * `drift-test:` markers (code health H10).
 *
 *   • **`LIVE_APPLICATION_STATES`** decides which application the student's own screen is about.
 *     Its comment already called itself a KEEP-IN-SYNC PAIR with the backend's
 *     `POST_SHORTLIST_EDITABLE + _FUNDED_STATES`, and nothing kept it: a status added on the api
 *     side and missed here makes the screen say the student has no live application at all, and
 *     one added only here makes it show two and pick one.
 *   • **`docFileLayout`'s "no doc type is exempt"** — every type is single-instance, so an upload
 *     REPLACES whatever sits in the slot. A per-type exemption list survived in this file until
 *     2026-07-26, seven weeks after the backend rule it mirrored had been retired, and the mother's
 *     STR and salary-slip cards alone kept the wrong layout for those seven weeks.
 *   • **`REAPPLY_ALLOWED_STATUSES`** (applyGate.ts) — the STATUS LIST the apply form treats
 *     as "does not block a fresh application", which must equal the statuses the server's duplicate
 *     check `.exclude()`s (2026-10-05, "apply gift clarity"). ⚠ ONLY THE LIST is guarded. The SCOPE
 *     deliberately differs — the server's check is per round, the web's is across every round — and
 *     nothing here asserts or excuses that; `applyGate.ts` says why.
 *
 * Characterised first (the H8 rule): the state lists compared as sets both ways, and the
 * single-instance rule read from the view that enforces it. They AGREE.
 */
import { LIVE_APPLICATION_STATES, liveApplications } from '@/lib/scholarship'
import { applicationScreen, REAPPLY_ALLOWED_STATUSES } from '@/lib/applicationScreen'
import { APPLICATION_STATUSES } from '@/lib/applicationStatus'
import { pySeq, readApi } from '@/test/apiSource'

// ⚠ `services.py` became the PACKAGE `services/` at code health H15 (2026-09-20).
// `POST_SHORTLIST_EDITABLE` is a cross-cutting status tuple and lives in `services/status_constants.py`
// (renamed from `services/constants.py` by TD-279, 2026-10-04 — one `constants.py` per app);
// the path follows the code, and `readApi` throws if it moves again.
const SERVICES = 'apps/scholarship/services/status_constants.py'
const VIEWS = 'apps/scholarship/views.py'
const servicesSrc = readApi(SERVICES)
const viewsSrc = readApi(VIEWS)

const postShortlistEditable = pySeq(servicesSrc, 'POST_SHORTLIST_EDITABLE')
const fundedStates = pySeq(viewsSrc, '_FUNDED_STATES')
const backendLive = [...postShortlistEditable, ...fundedStates]

describe('parse sanity — both halves of the pair were really found', () => {
  test('the editable funnel and the funded states read as tuples of real statuses', () => {
    expect(postShortlistEditable.length).toBe(4)
    expect(fundedStates.length).toBe(3)
    expect(backendLive.filter((s) => !APPLICATION_STATUSES.includes(s as never))).toEqual([])
  })

  test('the two halves do not overlap — editable and funded are different phases', () => {
    expect(postShortlistEditable.filter((s) => fundedStates.includes(s))).toEqual([])
  })
})

describe('LIVE_APPLICATION_STATES = POST_SHORTLIST_EDITABLE + _FUNDED_STATES', () => {
  test('the same states, both directions', () => {
    expect([...LIVE_APPLICATION_STATES].sort()).toEqual([...backendLive].sort())
  })

  test('a row in every live state is kept, and every other status dropped', () => {
    const apps = APPLICATION_STATUSES.map((status) => ({ status }))
    expect(liveApplications(apps).map((a) => a.status).sort()).toEqual([...backendLive].sort())
  })

  test('`submitted` is NOT live — the funnel opens at shortlisted on both sides', () => {
    // The one boundary worth naming: a submitted-but-not-shortlisted student has no editable
    // application, and the api's own constant is named for that.
    expect(backendLive).not.toContain('submitted')
    expect(liveApplications([{ status: 'submitted' }])).toEqual([])
  })

  test('two live applications show neither — a screen that cannot say which must not show one', () => {
    const two = [{ status: backendLive[0] }, { status: backendLive[1] }]
    expect(applicationScreen(two)).toEqual({ kind: 'several', count: 2 })
    expect(liveApplications(two)).toHaveLength(2)
    expect(applicationScreen([{ status: backendLive[0] }]).kind).toBe('one')
    expect(applicationScreen([]).kind).toBe('none')
  })
})

describe('REAPPLY_ALLOWED_STATUSES = the status list the server duplicate check excludes', () => {
  /**
   * The rule is a LINE OF CODE in `ApplicationListCreateView.post`, not a constant, so it is read
   * as one (the `_is_single_instance` pattern below). The regex finds the check by its shape; what
   * is ASSERTED is only that exactly one exists and that the statuses it `.exclude()`s equal the
   * web's allow-list.
   *
   * ⚠ NOT ASSERTED, AND DIFFERENT ON PURPOSE: the scope. The server refuses a duplicate per round
   * (`filter(cohort=cohort, profile=profile)`); the web's `mustLeaveApplyPage` refuses on a standing
   * application in ANY round — one application per student until roadmap M2 is approved.
   */
  const post = (() => {
    const view = viewsSrc.split('\nclass ApplicationListCreateView(')[1]
    if (!view) throw new Error(`drift test: ApplicationListCreateView is no longer in ${VIEWS}`)
    const body = view.split('\nclass ')[0].split('\n    def post(')[1]
    if (!body) throw new Error('drift test: ApplicationListCreateView.post is no longer where it was')
    return body
  })()
  const checks = [...post.matchAll(
    /ScholarshipApplication\.objects\.filter\(\s*cohort=cohort,\s*profile=profile\s*\)((?:\s*\.exclude\([^)]*\))*)\s*\.exists\(\)/g,
  )]

  test('parse sanity — exactly one duplicate check, and it excludes something', () => {
    expect(checks).toHaveLength(1)
    expect(checks[0][1]).toMatch(/\.exclude\(/)
  })

  test('the server excludes exactly the statuses the web allow-list holds (the list, not the scope)', () => {
    const excluded = [...checks[0][1].matchAll(/\.exclude\(\s*status\s*=\s*'([a-z_]+)'\s*\)/g)].map((m) => m[1])
    // Every .exclude() must be a plain `status='…'` — anything else (status__in, Q objects) is a
    // shape this guard cannot read, and must turn it red rather than pass on a partial reading.
    expect(excluded).toHaveLength((checks[0][1].match(/\.exclude\(/g) ?? []).length)
    expect(excluded.sort()).toEqual([...REAPPLY_ALLOWED_STATUSES].sort())
    expect(excluded.every((s) => APPLICATION_STATUSES.includes(s as never))).toBe(true)
  })
})

describe('every document type is single-instance — no exemption list may come back', () => {
  /**
   * `_is_single_instance` is a method that returns a bare `True` for everything. The rule is a
   * LINE OF CODE rather than a constant, so it is read as one — and the assertion is deliberately
   * specific, because the failure it exists to catch is somebody reintroducing a per-type branch.
   */
  const method = (() => {
    const body = viewsSrc.split('def _is_single_instance(')[1]
    if (!body) throw new Error(`drift test: _is_single_instance is no longer in ${VIEWS}`)
    return body.split('\n\n')[0]
  })()

  test('the backend answers True for every type, with no branch on doc_type', () => {
    expect(method).toMatch(/self, doc_type, member\):\s*\n\s+return True/)
    expect(method).not.toMatch(/\bif\b/)
    expect(method).not.toMatch(/'str'|'salary_slip'|'epf'/)
  })
})
