import {
  canVoid, creditChain, hasNoMoney, pendingTotal, seenBand, studentStage,
} from '../sponsorDetail'
import type { AdminSponsorCredit, AdminSponsorDetail } from '../admin-api'

const credit = (over: Partial<AdminSponsorCredit> = {}): AdminSponsorCredit => ({
  id: 1,
  programme_id: 1,
  programme_name: 'BrightPath Bursary',
  amount: '10000.00',
  source: 'admin_recorded',
  external_reference: 'TRF-1',
  status: 'draft',
  is_spendable: false,
  recorded_by: 'Poongulali Veeran',
  recorded_at: '2026-07-27T02:00:00Z',
  finance_checked_by: '',
  finance_checked_at: null,
  confirmed_by: '',
  confirmed_at: null,
  created_at: '2026-07-27T02:00:00Z',
  ...over,
})

describe('seenBand', () => {
  const now = new Date('2026-07-27T12:00:00Z')

  it('reads never when nothing was ever recorded — the gap this field closed', () => {
    expect(seenBand(null, now)).toBe('never')
  })

  it('reads today within the day', () => {
    expect(seenBand('2026-07-27T06:00:00Z', now)).toBe('today')
  })

  it('reads recent inside a month', () => {
    expect(seenBand('2026-07-20T06:00:00Z', now)).toBe('recent')
  })

  it('reads dormant at 30 days and beyond', () => {
    expect(seenBand('2026-06-27T06:00:00Z', now)).toBe('dormant')
    expect(seenBand('2026-01-01T06:00:00Z', now)).toBe('dormant')
  })
})

describe('creditChain', () => {
  it('draws two steps when no finance admin is appointed', () => {
    expect(creditChain(credit(), false).map((s) => s.key)).toEqual(['recorded', 'approved'])
  })

  it('draws the finance step for a credit still in flight once finance is armed', () => {
    expect(creditChain(credit({ status: 'admin_signed' }), true).map((s) => s.key))
      .toEqual(['recorded', 'checked', 'approved'])
  })

  it('keys a SETTLED credit on its signatures, not on the current setting', () => {
    // The regression that matters: a credit confirmed before finance existed must not
    // suddenly render a missing middle step, implying somebody skipped it.
    const done = credit({
      status: 'confirmed',
      confirmed_by: 'Suresh Thirugnanam',
      confirmed_at: '2026-07-27T03:00:00Z',
    })
    expect(creditChain(done, true).map((s) => s.key)).toEqual(['recorded', 'approved'])
  })

  it('keeps a finance signature that WAS collected, whatever the setting says now', () => {
    const checked = credit({
      status: 'confirmed',
      finance_checked_by: 'Sam Finance',
      finance_checked_at: '2026-07-27T02:30:00Z',
      confirmed_at: '2026-07-27T03:00:00Z',
    })
    expect(creditChain(checked, false).map((s) => s.key))
      .toEqual(['recorded', 'checked', 'approved'])
  })

  it('marks each step done only when its signature exists', () => {
    const steps = creditChain(credit({ status: 'admin_signed' }), false)
    expect(steps.map((s) => s.done)).toEqual([true, false])
  })
})

describe('canVoid', () => {
  it('refuses a confirmed credit — it is reversed by a compensating entry, never cancelled', () => {
    expect(canVoid(credit({ status: 'confirmed' }))).toBe(false)
  })

  it('refuses an already-cancelled credit', () => {
    expect(canVoid(credit({ status: 'cancelled' }))).toBe(false)
  })

  it('allows an unconfirmed credit', () => {
    expect(canVoid(credit({ status: 'draft' }))).toBe(true)
    expect(canVoid(credit({ status: 'admin_signed' }))).toBe(true)
  })
})

describe('pendingTotal', () => {
  it('sums only money that has not cleared the chain', () => {
    expect(pendingTotal([
      credit({ amount: '10000.00', status: 'draft' }),
      credit({ amount: '20000.00', status: 'confirmed' }),
      credit({ amount: '5000.00', status: 'cancelled' }),
      credit({ amount: '1000.00', status: 'admin_signed' }),
    ])).toBe(11000)
  })

  it('is zero when everything is settled', () => {
    expect(pendingTotal([credit({ status: 'confirmed' })])).toBe(0)
  })
})

describe('studentStage', () => {
  it('keeps offered as its own band', () => {
    // Award acceptance is off in production, so every live allocation is `offered`.
    // Folding it into "active" would misreport the whole programme.
    expect(studentStage('offered')).toBe('awaiting')
  })

  it('maps active and everything else', () => {
    expect(studentStage('active')).toBe('active')
    expect(studentStage('cancelled')).toBe('ended')
    expect(studentStage('lapsed')).toBe('ended')
  })
})

describe('hasNoMoney', () => {
  it('is true when the sponsor holds no wallet', () => {
    expect(hasNoMoney({ programmes: [] } as unknown as AdminSponsorDetail)).toBe(true)
  })

  it('is false once a wallet exists', () => {
    expect(hasNoMoney({ programmes: [{}] } as unknown as AdminSponsorDetail)).toBe(false)
  })
})
