/**
 * The reviewers table's sort rules (request #10, 2026-08-02).
 *
 * These are the judgements — what a column MEANS when you point it — so they are tested apart from
 * the page. The mechanics they sit on (`sortRows`, the comparators) have their own tests.
 */
import type { AdminReviewer } from '@/lib/admin-api'
import {
  DEFAULT_SORT, REVIEWER_SORT_KEYS, REVIEWER_SORT_LABEL, ROLE_ORDER,
  firstDirFor, sortReviewers, statusRank,
} from '@/lib/reviewerTable'
import en from '@/messages/en.json'

const R = (over: Partial<AdminReviewer> = {}): AdminReviewer => ({
  id: 1, name: 'Aisha', email: 'a@example.org', role: 'reviewer', languages: ['en'],
  open_now: 0, completed: 0, turnaround_days: null, paused: false, paused_at: null, ...over,
})

const resolve = (key: string) =>
  key.split('.').reduce<unknown>(
    (cur, part) => (cur && typeof cur === 'object' && part in cur
      ? (cur as Record<string, unknown>)[part] : undefined),
    en as Record<string, unknown>,
  )

describe('the column labels', () => {
  it('has a label key for every sortable column, and each resolves', () => {
    for (const key of REVIEWER_SORT_KEYS) {
      expect(typeof resolve(REVIEWER_SORT_LABEL[key])).toBe('string')
    }
  })
})

describe('the default sort', () => {
  it('opens on who is carrying the most RIGHT NOW', () => {
    // The page is opened before handing out the next case, not to browse a staff list.
    expect(DEFAULT_SORT).toEqual({ key: 'openNow', dir: 'desc' })
  })

  it('puts the fullest caseload at the top', () => {
    const rows = [R({ id: 1, open_now: 1 }), R({ id: 2, open_now: 5 }), R({ id: 3, open_now: 0 })]
    expect(sortReviewers(rows, 'openNow', 'desc').map((r) => r.id)).toEqual([2, 1, 3])
  })
})

describe('first click direction', () => {
  it('opens the three figures at their INTERESTING end', () => {
    expect(firstDirFor('openNow')).toBe('desc')
    expect(firstDirFor('completed')).toBe('desc')
    // Slowest first: a fast turnaround needs nobody's attention.
    expect(firstDirFor('turnaround')).toBe('desc')
  })

  it('opens text and state columns ascending', () => {
    expect(firstDirFor('name')).toBe('asc')
    expect(firstDirFor('role')).toBe('asc')
    expect(firstDirFor('status')).toBe('asc')
  })
})

describe('turnaround, where the trap is', () => {
  const rows = [
    R({ id: 1, turnaround_days: 9.4 }),
    R({ id: 2, turnaround_days: null }),   // never decided a case
    R({ id: 3, turnaround_days: 2.5 }),
  ]

  it('keeps "no measurement" at the BOTTOM whichever way the column points', () => {
    // The whole point: null is not zero. Sorted fastest-first it must not crown the volunteer
    // who has never decided anything.
    expect(sortReviewers(rows, 'turnaround', 'asc').map((r) => r.id)).toEqual([3, 1, 2])
    expect(sortReviewers(rows, 'turnaround', 'desc').map((r) => r.id)).toEqual([1, 3, 2])
  })

  it('does not treat a null as a fast reviewer', () => {
    const fastest = sortReviewers(rows, 'turnaround', 'asc')[0]
    expect(fastest.turnaround_days).toBe(2.5)
  })
})

describe('the role column', () => {
  it('orders by what the person may do to a case, not alphabetically', () => {
    expect(ROLE_ORDER.super).toBeLessThan(ROLE_ORDER.qc)
    expect(ROLE_ORDER.qc).toBeLessThan(ROLE_ORDER.reviewer)
  })

  it('sorts an unknown role last rather than crashing', () => {
    const rows = [R({ id: 1, role: 'something_new' }), R({ id: 2, role: 'super' })]
    expect(sortReviewers(rows, 'role', 'asc').map((r) => r.id)).toEqual([2, 1])
  })
})

describe('the status column', () => {
  it('finds the exception — paused first', () => {
    expect(statusRank(R({ paused: true }))).toBeLessThan(statusRank(R({ paused: false })))
    const rows = [R({ id: 1 }), R({ id: 2, paused: true }), R({ id: 3 })]
    expect(sortReviewers(rows, 'status', 'asc')[0].id).toBe(2)
  })
})

describe('the name column', () => {
  it('sorts a blank name last, not first', () => {
    const rows = [R({ id: 1, name: '' }), R({ id: 2, name: 'Zulkifli' }), R({ id: 3, name: 'Anand' })]
    expect(sortReviewers(rows, 'name', 'asc').map((r) => r.id)).toEqual([3, 2, 1])
  })
})

describe('sorting never mutates', () => {
  it('leaves the caller\'s array alone', () => {
    const rows = [R({ id: 1, open_now: 1 }), R({ id: 2, open_now: 9 })]
    sortReviewers(rows, 'openNow', 'desc')
    expect(rows.map((r) => r.id)).toEqual([1, 2])
  })
})
