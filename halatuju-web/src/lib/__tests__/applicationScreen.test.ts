/**
 * What `/scholarship/application` shows, over every status and every pair.
 *
 * Until 2026-10-05 this file also held the web's own "must she leave the apply form?" rule and the
 * invariant between the two. Since the owner's ruling on TD-337 the apply page asks the SERVER
 * (`services/apply_gate.py`) and keeps no rule; the invariant that remains — whenever the server says
 * `application_in_progress`, this screen is neither 'none' nor the closed card — is asserted against
 * the server's own status lists in `studentScreenDrift.test.ts`.
 */
import { applicationScreen } from '@/lib/applicationScreen'
import { APPLICATION_STATUSES } from '@/lib/applicationStatus'

type Row = { id: number; status: string }
const rows = (...statuses: string[]): Row[] => statuses.map((status, i) => ({ id: i + 1, status }))

describe('every list has an answer, and position never picks one', () => {
  const lists: Row[][] = [
    [],
    ...APPLICATION_STATUSES.map((s) => rows(s)),
    ...APPLICATION_STATUSES.flatMap((a) => APPLICATION_STATUSES.map((b) => rows(a, b))),
  ]
  test.each(lists.map((l) => [l.map((r) => r.status).join(' + ') || '(none)', l] as const))(
    '%s: the same answer in either order',
    (_label, list) => {
      const kind = applicationScreen(list).kind
      expect(['one', 'finished', 'several', 'none']).toContain(kind)
      expect(applicationScreen([...list].reverse()).kind).toBe(kind)
    },
  )
})

describe('applicationScreen — what the application screen shows', () => {
  const shown = (list: Row[]) => {
    const s = applicationScreen(list)
    if (s.kind === 'one') return s.app.id
    if (s.kind === 'finished') return `finished:${s.app?.id ?? '-'}`
    if (s.kind === 'several') return `several:${s.count}`
    return 'none'
  }

  test('one live application → that one, whatever else sits beside it', () => {
    expect(shown(rows('submitted', 'shortlisted'))).toBe(2)
    expect(shown(rows('rejected', 'interviewing', 'expired'))).toBe(2)
  })

  test('two live → neither, with the count (M1: never pick by position)', () => {
    expect(shown(rows('shortlisted', 'active'))).toBe('several:2')
  })

  test('a lone submitted application → shown (the "received" card, not "haven\'t applied")', () => {
    expect(shown(rows('submitted'))).toBe(1)
  })

  test('a lone rejected / withdrawn / closed application → the neutral "closed" card, with it', () => {
    expect(shown(rows('rejected'))).toBe('finished:1')
    expect(shown(rows('withdrawn'))).toBe('finished:1')
    expect(shown(rows('closed'))).toBe('finished:1')
    expect(shown(rows('expired', 'rejected'))).toBe('finished:2')
  })

  test('several standing, none submitted → the "closed" card, naming no single one', () => {
    expect(shown(rows('rejected', 'withdrawn'))).toBe('finished:-')
    expect(shown(rows('rejected', 'withdrawn', 'expired'))).toBe('finished:-')
  })

  test('several standing, exactly one submitted → the submitted one', () => {
    expect(shown(rows('rejected', 'submitted', 'withdrawn'))).toBe(2)
  })

  test('two or more submitted → the "more than one" message, counting the submitted', () => {
    expect(shown(rows('submitted', 'submitted'))).toBe('several:2')
    expect(shown(rows('submitted', 'submitted', 'closed'))).toBe('several:2')
  })

  test('expired rows are history, not an application on screen', () => {
    expect(shown(rows('expired'))).toBe('none')
    expect(shown([])).toBe('none')
  })
})

describe('one application per organisation (TD-337) — the newly reachable combinations', () => {
  // A finished application in one gift no longer stops her applying to another (or to a later
  // round of the same organisation), so these lists now happen in production.
  const gift = (id: number, status: string, cohort_name: string) => ({ id, status, cohort_name })

  test('finished in gift A + newly submitted in gift B → the submitted one, not the closed card', () => {
    for (const done of ['rejected', 'withdrawn', 'closed']) {
      const s = applicationScreen([gift(1, done, 'A 2026'), gift(2, 'submitted', 'B 2026')])
      expect(s).toEqual({ kind: 'one', app: gift(2, 'submitted', 'B 2026') })
    }
  })

  test('finished + live → the live one', () => {
    for (const live of ['shortlisted', 'profile_complete', 'interviewing', 'interviewed', 'awarded', 'active', 'maintenance']) {
      const s = applicationScreen([gift(1, 'rejected', 'A 2026'), gift(2, live, 'B 2026')])
      expect(s).toEqual({ kind: 'one', app: gift(2, live, 'B 2026') })
    }
  })

  test('finished in an earlier round + submitted in the later round of the SAME gift → the submitted one', () => {
    const s = applicationScreen([gift(1, 'rejected', 'A 2026'), gift(2, 'submitted', 'A 2027')])
    expect(s).toEqual({ kind: 'one', app: gift(2, 'submitted', 'A 2027') })
  })
})
