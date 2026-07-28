import {
  DEFAULT_SORT, SPONSOR_SORT_KEYS, SPONSOR_SORT_LABEL, STATUS_ORDER, firstDirFor, sortSponsors,
} from '../sponsorTable'
import type { AdminSponsor } from '../admin-api'

const s = (over: Partial<AdminSponsor>): AdminSponsor => ({
  id: 1, name: 'Someone', email: '', phone: '', source: '', organisation: '', note: '',
  status: 'approved', reviewed_at: null, reviewed_by: '',
  created_at: '2026-07-01T00:00:00Z', given: '0.00', students: 0, last_seen_at: null,
  ...over,
} as AdminSponsor)

/** The nine production sponsors, near enough — the figures are the real ones. */
const PROD = [
  s({ id: 3, name: 'Suresh Thiru', given: '100000.00', students: 38, status: 'approved',
      created_at: '2026-06-25T00:00:00Z' }),
  s({ id: 4, name: 'Chong Lee Min', given: '20000.00', students: 6, status: 'approved',
      created_at: '2026-07-08T00:00:00Z' }),
  s({ id: 6, name: 'chong lee ai', given: '20000.00', students: 1, status: 'approved',
      created_at: '2026-07-17T00:00:00Z' }),
  s({ id: 8, name: 'Goban Arasu', given: '10000.00', students: 1, status: 'approved',
      created_at: '2026-07-21T00:00:00Z' }),
  s({ id: 2, name: 'Kalaiyarasi a/p Gurusamy', given: '0.00', students: 0, status: 'rejected',
      created_at: '2026-06-15T00:00:00Z' }),
  s({ id: 1, name: 'Ve. Elanjelian', given: '2000.00', students: 0, status: 'approved',
      created_at: '2026-05-31T00:00:00Z', last_seen_at: '2026-07-28T00:00:00Z' }),
]

const names = (rows: AdminSponsor[]) => rows.map((r) => r.name)

describe('the column set', () => {
  it('covers every header except Actions, and each has a label', () => {
    expect(SPONSOR_SORT_KEYS).toEqual(
      ['name', 'status', 'given', 'students', 'lastSeen', 'registered'])
    for (const k of SPONSOR_SORT_KEYS) {
      expect(SPONSOR_SORT_LABEL[k]).toMatch(/^admin\.sponsors\./)
    }
  })

  it('defaults to newest registration first — what the list did before it was sortable', () => {
    expect(DEFAULT_SORT).toEqual({ key: 'registered', dir: 'desc' })
    expect(names(sortSponsors(PROD, 'registered', 'desc'))[0]).toBe('Goban Arasu')
  })
})

describe('given', () => {
  it('sorts as money, so 100,000 leads and 9,000 does not beat 20,000', () => {
    expect(names(sortSponsors(PROD, 'given', 'desc'))[0]).toBe('Suresh Thiru')
    expect(names(sortSponsors(PROD, 'given', 'asc'))[0]).toBe('Kalaiyarasi a/p Gurusamy')
  })
})

describe('students', () => {
  it('puts the sponsor funding most students at the top', () => {
    const top = sortSponsors(PROD, 'students', 'desc')
    expect(top[0].students).toBe(38)
    expect(top[1].students).toBe(6)
  })
})

describe('status', () => {
  it('leads with the ones waiting on you, not with "approved" (owner, 2026-07-28)', () => {
    const rows = [s({ name: 'A', status: 'approved' }), s({ name: 'P', status: 'pending' }),
                  s({ name: 'R', status: 'rejected' }), s({ name: 'S', status: 'suspended' })]
    expect(names(sortSponsors(rows, 'status', 'asc'))).toEqual(['P', 'A', 'S', 'R'])
  })

  it('orders pending, approved, suspended, rejected', () => {
    expect(STATUS_ORDER.pending).toBeLessThan(STATUS_ORDER.approved)
    expect(STATUS_ORDER.approved).toBeLessThan(STATUS_ORDER.suspended)
    expect(STATUS_ORDER.suspended).toBeLessThan(STATUS_ORDER.rejected)
  })

  it('does not throw on a status it has never seen', () => {
    const rows = [s({ name: 'weird', status: 'something_new' as AdminSponsor['status'] }),
                  s({ name: 'pending', status: 'pending' })]
    expect(names(sortSponsors(rows, 'status', 'asc'))).toEqual(['pending', 'weird'])
  })
})

describe('last seen', () => {
  it('keeps the eight with no sign-in recorded at the bottom, both directions', () => {
    // Only Ve. Elanjelian has a stamp; the column started recording on 2026-07-27, so the rest
    // are UNKNOWN rather than dormant-since-forever.
    expect(names(sortSponsors(PROD, 'lastSeen', 'desc'))[0]).toBe('Ve. Elanjelian')
    expect(names(sortSponsors(PROD, 'lastSeen', 'asc'))[0]).toBe('Ve. Elanjelian')
    expect(names(sortSponsors(PROD, 'lastSeen', 'asc')).slice(-1)[0]).not.toBe('Ve. Elanjelian')
  })
})

describe('name', () => {
  it('files "chong lee ai" with the other Chongs rather than after the capitals', () => {
    expect(names(sortSponsors(PROD, 'name', 'asc')).slice(0, 2))
      .toEqual(['chong lee ai', 'Chong Lee Min'])
  })
})

describe('firstDirFor', () => {
  it('opens the money and count columns at their interesting end', () => {
    expect(firstDirFor('given')).toBe('desc')
    expect(firstDirFor('students')).toBe('desc')
    expect(firstDirFor('lastSeen')).toBe('desc')
    expect(firstDirFor('registered')).toBe('desc')
  })

  it('opens the text columns ascending', () => {
    expect(firstDirFor('name')).toBe('asc')
    expect(firstDirFor('status')).toBe('asc')
  })
})

describe('sorting never mutates or drops rows', () => {
  it('returns a new array of the same length', () => {
    const before = names(PROD)
    const out = sortSponsors(PROD, 'given', 'asc')
    expect(out).toHaveLength(PROD.length)
    expect(names(PROD)).toEqual(before)          // the caller's array is untouched
  })
})
