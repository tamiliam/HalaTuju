/**
 * THE DRIFT TEST for `requestStatus.ts` — named by its `drift-test:` marker (code health H9).
 *
 * The module said "KEEP IN STEP with org_requests.py" and nothing kept it. What it decides is
 * which BUTTONS an officer is offered: an action offered outside the server's window is a control
 * that looks live and answers `bad_transition`, and an action the server allows but nobody offers
 * is a road out of a status that no screen has.
 *
 * Characterised first (the H8 rule): every status × role × kind × question-state was put through
 * `requestActionsFor` and compared with `org_requests.TRANSITIONS` on the untouched tree.
 * They agree on every row but ONE, which is pinned below as a disagreement, not merged — see
 * `requote`, and TD-263.
 *
 * What is read from the api, not restated here: the status list, the transition table, the
 * terminal set and the shaping window. What IS restated is the NAME MAP, because the two sides
 * genuinely use different words for the same action and no file holds both.
 */
import {
  REQUEST_STATUSES, REQUEST_TERMINAL, REQUEST_OPEN_FOR_SHAPING,
  requestActionsFor, canComment, canAttach,
  type RequestAction, type RequestRole,
} from '@/lib/requestStatus'
import { pyChoiceValues, pySeq, pyTransitionTable, readApi } from '@/test/apiSource'

const SERVICE = 'apps/scholarship/org_requests.py'
const serviceSrc = readApi(SERVICE)
const modelsSrc = readApi('apps/scholarship/models.py')

const TRANSITIONS = pyTransitionTable(serviceSrc, 'TRANSITIONS')
const TERMINAL = pySeq(serviceSrc, 'TERMINAL_STATUSES')
const OPEN_FOR_SHAPING = pySeq(serviceSrc, 'OPEN_FOR_SHAPING')
// `STATUS_CHOICES` appears on several models; OrgRequest's is the one whose members are the eight
// request statuses. Selecting by CONTENT rather than by position survives a model being reordered.
const backendStatuses = (() => {
  const all = [...modelsSrc.matchAll(/^\s+STATUS_CHOICES\s*=\s*\[[\s\S]*?\n\s+\]/gm)]
    .map((m) => pyChoiceValues(m[0], 'STATUS_CHOICES'))
  const hit = all.filter((s) => s.includes('triaged') && s.includes('quoted'))
  if (hit.length !== 1) {
    throw new Error(`drift test: expected exactly one OrgRequest-shaped STATUS_CHOICES, got ${hit.length}`)
  }
  return hit[0]
})()

/**
 * The web's action name → the api's. They differ for two, and both differences are deliberate:
 *   • `accept` is what the requesting organisation calls agreeing to a quote; the service calls
 *     the transition `approve`.
 *   • `withdraw` is the same `decline` transition performed BY the requester — one status change,
 *     two words, distinguished on the api side by `declined_by_role`, not by a second action.
 * `comment` is not a transition at all (it changes no status) and is checked against `can_comment`.
 */
const API_ACTION: Record<Exclude<RequestAction, 'comment'>, string> = {
  answer: 'answer', accept: 'approve', defer: 'defer', modify: 'modify', withdraw: 'decline',
  triage: 'triage', quote: 'quote', requote: 'requote', schedule: 'schedule', done: 'done',
  decline: 'decline', ai_rerun: 'ai_rerun', ask: 'ask',
}

const ROLES: RequestRole[] = ['super', 'org_admin']
const KINDS = ['', 'bug', 'feature']

/** Every offer the two screens can make, as `{role, status, kind, questions, actions}` rows. */
const offers = ROLES.flatMap((role) => REQUEST_STATUSES.flatMap((status) => KINDS.flatMap(
  (kind) => [true, false].map((questions) => ({
    role, status, kind, questions, actions: requestActionsFor(role, status, kind, questions),
  })))))

describe('the parse found the real api rules (parse sanity)', () => {
  test('the transition table has every action the web can name', () => {
    expect(Object.keys(TRANSITIONS).sort())
      .toEqual([...new Set(Object.values(API_ACTION))].sort())
  })

  test('every from-status in the table is a real request status', () => {
    const unknown = Object.values(TRANSITIONS).flat().filter((s) => !backendStatuses.includes(s))
    expect(unknown).toEqual([])
  })

  test('the rows were built (the cartesian sweep is not empty)', () => {
    expect(offers.length).toBe(2 * 8 * 3 * 2)
  })
})

describe('REQUEST_STATUSES vs OrgRequest.STATUS_CHOICES', () => {
  test('the eight statuses agree, in the same order', () => {
    // Unlike the application funnel, these two lists are written in the same order on both sides,
    // so the stronger assertion is the honest one.
    expect([...REQUEST_STATUSES]).toEqual(backendStatuses)
  })
})

describe('the two windows are the api\'s, not a copy of it', () => {
  test('REQUEST_TERMINAL is org_requests.TERMINAL_STATUSES', () => {
    expect([...REQUEST_TERMINAL]).toEqual(TERMINAL)
  })

  test('REQUEST_OPEN_FOR_SHAPING is org_requests.OPEN_FOR_SHAPING', () => {
    expect([...REQUEST_OPEN_FOR_SHAPING]).toEqual(OPEN_FOR_SHAPING)
  })

  test('canAttach and canComment answer those two windows exactly', () => {
    for (const status of REQUEST_STATUSES) {
      expect(canAttach(status)).toBe(OPEN_FOR_SHAPING.includes(status))
      // `can_comment` in org_requests.py is literally "not terminal"; the web must not be narrower,
      // because a request parked at `deferred` is exactly where the discussion still matters.
      expect(canComment(status)).toBe(!TERMINAL.includes(status))
    }
  })
})

describe('no button is offered outside the server\'s window', () => {
  test.each(offers)('$role · $status · kind=$kind · questions=$questions', (row) => {
    const outside = row.actions
      .filter((a): a is Exclude<RequestAction, 'comment'> => a !== 'comment')
      .filter((a) => !TRANSITIONS[API_ACTION[a]].includes(row.status))
    expect(outside).toEqual([])
  })
})

describe('no road out of a status is left without a button', () => {
  // The reverse direction, which is the one a mirror never catches: the api gains a transition and
  // the screen that should offer it is never touched.
  test.each([...REQUEST_STATUSES])('%s', (status) => {
    const roads = Object.entries(TRANSITIONS)
      .filter(([, from]) => from.includes(status))
      .map(([action]) => action)
      .sort()
    const offered = [...new Set(
      offers.filter((o) => o.status === status)
        .flatMap((o) => o.actions)
        .filter((a): a is Exclude<RequestAction, 'comment'> => a !== 'comment')
        .map((a) => API_ACTION[a]),
    )].sort()
    expect(offered).toEqual(roads)
  })
})

describe('the kind gates: a bug is free, so it is never quoted', () => {
  // `quote` and `requote` both raise `bug_is_free` unless the effective kind is 'feature'. The
  // transition table cannot express that, so these read the guard itself — if the api ever drops
  // it, the web's kind conditions become a narrowing nobody asked for and this goes red.
  test.each(['quote', 'requote'])('%s still refuses a non-feature', (fn) => {
    const body = serviceSrc.split(`\ndef ${fn}(`)[1]
    expect(body).toBeDefined()
    expect(body.slice(0, 1200)).toMatch(/_effective_kind\(req\) != 'feature'[\s\S]{0,80}bug_is_free/)
  })

  test('quote is offered only for a feature; schedule-from-triaged only for a bug', () => {
    expect(requestActionsFor('super', 'triaged', 'feature', false)).toContain('quote')
    expect(requestActionsFor('super', 'triaged', 'bug', false)).not.toContain('quote')
    expect(requestActionsFor('super', 'triaged', 'bug', false)).toContain('schedule')
    expect(requestActionsFor('super', 'triaged', 'feature', false)).not.toContain('schedule')
    // The api's own rule at `schedule`: only `triaged` carries the kind gate, `approved` does not.
    expect(requestActionsFor('super', 'approved', 'bug', false)).toContain('schedule')
    expect(requestActionsFor('super', 'approved', 'feature', false)).toContain('schedule')
  })

  /**
   * ⚠ PINNED DISAGREEMENT (TD-263) — not merged, not fixed, and no winner picked here.
   *
   * `requote` is offered at `deferred` for ANY kind; the service refuses a non-feature requote
   * with `bug_is_free`. It is unreachable today, and this test is what says so: the only road
   * into `deferred` is `defer`, whose only road in is `quoted`, which a bug can never reach. Add
   * a second road into `deferred` — or a way to re-triage a quoted request to a bug — and the
   * button becomes a 400. This assertion goes red at exactly that moment.
   */
  test('a bug cannot reach `deferred` today, which is why the missing kind gate is harmless', () => {
    // The chain, read off the table's DESTINATIONS (which the from-sets alone cannot show):
    // the only way to land on `deferred` is `defer`; the only way to land on `quoted` is `quote`
    // or `requote`; and both of those refuse anything but a feature (the test above).
    const landingOn = (status: string) => [
      ...serviceSrc.matchAll(new RegExp(`'([a-z_]+)':\\s*\\(\\([^)]*\\),\\s*'${status}'\\)`, 'g')),
    ].map((m) => m[1]).sort()
    expect(landingOn('deferred')).toEqual(['defer'])
    expect(TRANSITIONS.defer).toEqual(['quoted'])
    expect(landingOn('quoted')).toEqual(['quote', 'requote'])
    // The offer itself, pinned as it is today — kind-blind, and therefore wider than the service.
    expect(requestActionsFor('super', 'deferred', 'bug', false)).toContain('requote')
  })
})
