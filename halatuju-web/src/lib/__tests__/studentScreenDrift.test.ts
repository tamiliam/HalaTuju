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
 *   • **The apply gate's status lists vs `applicationScreen`** (2026-10-05, TD-337). The web keeps
 *     NO apply rule any more — the apply page obeys the server's verdict (`services/apply_gate.py`).
 *     What the web still owns is the APPLICATION screen, and a student the server has just sent there
 *     as `application_in_progress` must land on THE application the gate named: `kind: 'one'`, same
 *     id — not "you haven't applied", not the closed card, not "several", not another one. This reads
 *     the server's `IN_PLAY_STATUSES` / `FINISHED_STATUSES` and asserts it over every list the rule
 *     can produce: one in-play row (each served in-play status) beside any finished ones, at every
 *     position. The api half (`test_apply_gate.py`, `TestTheServedListOfABlockedStudent`) builds real
 *     rows for every in-play status and embargoed shape and proves her served list has exactly that
 *     shape: the gate's `application_id` carries an in-play status (never 'recommended', which no
 *     student is shown) and every other row a finished one. ⚠ WHAT IT DOES NOT SEE: legacy data
 *     holding two in-play rows (the submit refuses the second), and an admin reopening a finished
 *     application beside a live one.
 *
 * Characterised first (the H8 rule): the state lists compared as sets both ways, and the
 * single-instance rule read from the view that enforces it. They AGREE.
 */
import { LIVE_APPLICATION_STATES, liveApplications } from '@/lib/scholarship'
import { applicationScreen } from '@/lib/applicationScreen'
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

describe('the apply gate (server) vs the application screen (web) — TD-337', () => {
  const GATE = 'apps/scholarship/services/apply_gate.py'
  const gateSrc = readApi(GATE)
  const inPlay = pySeq(gateSrc, 'IN_PLAY_STATUSES')
  const finished = pySeq(gateSrc, 'FINISHED_STATUSES')
  // 'recommended' is in play but never reaches a student: `student_facing_status` shows it as
  // 'interviewed' (proved on the api side, `test_apply_gate.py`). What her LIST can carry is the rest.
  const servedInPlay = inPlay.filter((s) => s !== 'recommended')

  test('parse sanity — the two lists partition every real status', () => {
    expect(inPlay.length).toBeGreaterThanOrEqual(9)
    expect(finished.length).toBeGreaterThanOrEqual(4)
    expect(inPlay.filter((s) => finished.includes(s))).toEqual([])
    expect([...inPlay, ...finished].sort()).toEqual([...APPLICATION_STATUSES].sort())
    expect(inPlay).toContain('recommended')
  })

  test('the gate refuses `submitted` too — the funnel opens at submit, not at shortlist', () => {
    expect(inPlay).toContain('submitted')
  })

  // Every list the RULE can produce when the gate says `application_in_progress`: exactly ONE row
  // with an in-play (served) status — the one the gate names, `application_id` — beside any number
  // of finished / expired rows, at every position. (Two in play cannot be filed: the submit refuses
  // the second. The api half proves her served list has exactly this shape.)
  const companionSets: string[][] = [
    [], ...finished.map((f) => [f]), ...finished.map((f) => [f, f]), finished, [...finished].reverse(),
  ]
  const lists = servedInPlay.flatMap((s) => companionSets.flatMap((others) =>
    Array.from({ length: others.length + 1 }, (_, at) => {
      const statuses = [...others.slice(0, at), s, ...others.slice(at)]
      return { statuses, blocked: at }
    })))
  test.each(lists.map((l) => [l.statuses.join(' + '), l] as const))(
    '%s: the application screen shows THE application the gate named — kind one, same id',
    (_label, { statuses, blocked }) => {
      const rows = statuses.map((status, i) => ({ id: 100 + i, status }))
      expect(applicationScreen(rows)).toEqual({ kind: 'one', app: rows[blocked] })
    },
  )
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
