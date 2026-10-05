/**
 * THE APPLY PAGE AND THE APPLICATION PAGE MUST AGREE about whether the student has applied.
 *
 * They used to ask two different questions. `/scholarship/apply` sent away anyone with ANY row
 * (`applications[0]`); `/scholarship/application` showed only a LIVE one (shortlisted and later).
 * A student whose only application was `submitted` — the first status every application has — was
 * sent from the form to "You haven't applied yet", whose button sent her back to the form, which
 * sent her back again. The "received" card meant for her could not be reached at all.
 *
 * The invariant, over every real status and every pair of them: `mustLeaveApplyPage` is true
 * EXACTLY when `applicationScreen` is not 'none'. Written first, and red against the old pair of
 * rules (51 failures).
 */
import {
  applicationScreen, mustLeaveApplyPage, REAPPLY_ALLOWED_STATUSES,
} from '@/lib/applicationScreen'
import { APPLICATION_STATUSES } from '@/lib/applicationStatus'

type Row = { id: number; status: string }
const rows = (...statuses: string[]): Row[] => statuses.map((status, i) => ({ id: i + 1, status }))

// Every list worth asking about: nothing, each status alone, and every ordered pair (order matters
// to the old rule, which read position 0).
const LISTS: Row[][] = [
  [],
  ...APPLICATION_STATUSES.map((s) => rows(s)),
  ...APPLICATION_STATUSES.flatMap((a) => APPLICATION_STATUSES.map((b) => rows(a, b))),
  rows('expired', 'expired', 'expired'),
  rows('expired', 'rejected', 'withdrawn'),
  rows('submitted', 'rejected', 'expired'),
  rows('submitted', 'submitted', 'closed'),
]

describe('the invariant — no loop between the two pages', () => {
  test.each(LISTS.map((l) => [l.map((r) => r.status).join(' + ') || '(none)', l] as const))(
    '%s: sent away from the form ⇔ the application page is not "you haven\'t applied"',
    (_label, list) => {
      expect(mustLeaveApplyPage(list)).toBe(applicationScreen(list).kind !== 'none')
    },
  )
})

describe('mustLeaveApplyPage — the status list matches the server; the scope is stricter', () => {
  test('nothing at all → the form', () => {
    expect(mustLeaveApplyPage([])).toBe(false)
  })

  test('only expired rows → the form: an auto-closed application never blocks a fresh start', () => {
    expect(mustLeaveApplyPage(rows('expired'))).toBe(false)
    expect(mustLeaveApplyPage(rows('expired', 'expired'))).toBe(false)
  })

  test('every other status, alone or beside an expired one, sends the student away', () => {
    // In ANY round — the web is stricter than the server's per-round duplicate check, on purpose
    // (one application per student until roadmap M2 is approved).
    for (const s of APPLICATION_STATUSES.filter((x) => x !== 'expired')) {
      expect(mustLeaveApplyPage(rows(s))).toBe(true)
      expect(mustLeaveApplyPage(rows('expired', s))).toBe(true)
    }
  })

  test('the allow-list is exactly expired (the drift test pins it to the api)', () => {
    expect([...REAPPLY_ALLOWED_STATUSES]).toEqual(['expired'])
  })
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
