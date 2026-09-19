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
 *
 * Characterised first (the H8 rule): the state lists compared as sets both ways, and the
 * single-instance rule read from the view that enforces it. They AGREE.
 */
import { LIVE_APPLICATION_STATES, liveApplications, soleLiveApplication } from '@/lib/scholarship'
import { APPLICATION_STATUSES } from '@/lib/applicationStatus'
import { pySeq, readApi } from '@/test/apiSource'

const SERVICES = 'apps/scholarship/services.py'
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

  test('two live applications answer null — a screen that cannot say which must not show one', () => {
    const two = [{ status: backendLive[0] }, { status: backendLive[1] }]
    expect(soleLiveApplication(two)).toBeNull()
    expect(liveApplications(two)).toHaveLength(2)
    expect(soleLiveApplication([{ status: backendLive[0] }])).not.toBeNull()
    expect(soleLiveApplication([])).toBeNull()
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
