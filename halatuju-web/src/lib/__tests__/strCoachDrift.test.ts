/**
 * THE DRIFT TEST for the STR coach states in `documentHelp.ts` — named by its `drift-test:`
 * marker (code health H9).
 *
 * The module carried a private `STR_COACH_STATES` set saying "keep in step with income_engine.py /
 * help_engine.py". The two sides answer the same question — *does a student's STR need a word from
 * Gopal?* — and a student is the one who pays for a drift: the server decides she has a fixable
 * STR problem, her own screen says nothing, and she never re-uploads.
 *
 * Characterised first (the H8 rule): every state on the STR-currency ladder was put through both
 * sides on the untouched tree — all seven, including the two that must stay QUIET. They AGREE on
 * all seven.
 *
 * The web set is module-private on purpose, so this reads it the way a student does: through
 * `shouldShowCoach`. That also means the guard survives the set being renamed or inlined.
 */
import { shouldShowCoach } from '@/lib/documentHelp'
import type { ApplicantDocument, StrCheck } from '@/lib/api'
import { pySeq, readApi } from '@/test/apiSource'

const ENGINE = 'apps/scholarship/income_engine.py'
const engineSrc = readApi(ENGINE)

const coachStates = pySeq(engineSrc, 'STR_COACH_STATES')
const redStates = pySeq(engineSrc, 'STR_RED_STATES')

/**
 * The whole ladder, from the `StrCheck.current_status` union in `api.ts` — which is itself the
 * shape the serializer emits. Taking the states from the TYPE rather than listing them here is
 * what makes the "must stay quiet" half of this test real: a new state added to the union and to
 * the api's coach band, but not to the other, shows up as a row that answers differently.
 */
const LADDER: StrCheck['current_status'][] = [
  'current', 'stale', 'rejected', 'unconfirmed', 'unknown', 'wrong_type', 'unreadable',
]

function strDoc(currentStatus: StrCheck['current_status'], icPresent: boolean): ApplicantDocument {
  const str_check: StrCheck = {
    name: 'Test Parent', nric: '700101-14-5555', status: 'Lulus', year: '2026', member: 'father',
    name_status: 'match', nric_status: 'match', current_status: currentStatus,
    ic_present: icPresent,
  }
  // Only the fields `shouldShowCoach` reads on the way to the STR arm; everything earlier in the
  // chain is deliberately absent so the STR branch is the one under test.
  return { id: 1, doc_type: 'str', str_check } as unknown as ApplicantDocument
}

describe('parse sanity — the api bands were really found', () => {
  test('STR_COACH_STATES resolved through its `STR_RED_STATES + (…)` concatenation', () => {
    // If `pySeq` ever stopped resolving the named half it would read 2 states, not 5, and this
    // test — not a silently narrowed guard — is what says so.
    expect(coachStates.length).toBe(5)
    expect(redStates.length).toBe(3)
    expect(redStates.every((s) => coachStates.includes(s))).toBe(true)
  })

  test('every api coach state is a real rung of the ladder the serializer emits', () => {
    expect(coachStates.filter((s) => !LADDER.includes(s as StrCheck['current_status']))).toEqual([])
  })
})

describe('the student\'s STR coach appears exactly where the backend says it should', () => {
  test.each(LADDER)('%s', (state) => {
    // `ic_present: true` isolates the currency rule — the STR arm also coaches when no earner IC
    // has been uploaded yet, which is a different nudge and is pinned separately below.
    expect(shouldShowCoach(strDoc(state, true))).toBe(coachStates.includes(state))
  })

  test('the two green-band states stay quiet — the half a one-directional mirror never checks', () => {
    const quiet = LADDER.filter((s) => !coachStates.includes(s))
    expect([...quiet].sort()).toEqual(['current', 'unknown'])
    for (const state of quiet) expect(shouldShowCoach(strDoc(state, true))).toBe(false)
  })

  test('a missing earner IC coaches whatever the currency says (the separate nudge)', () => {
    for (const state of LADDER) expect(shouldShowCoach(strDoc(state, false))).toBe(true)
  })
})
