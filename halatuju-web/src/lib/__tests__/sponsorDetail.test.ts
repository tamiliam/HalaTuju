import {
  canRecordCredit, creditActions, creditArmed, creditableProgrammes, creditChain, creditErrorKey,
  hasNoMoney, pendingTotal, seenBand, studentStage,
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

// ── S3 / M4b: the actions the credit UI may offer are SERVED ────────────────────
// `credit_steps.served` answers can_sign / blocked / can_void per credit (owner rulings Q-A to Q-C,
// 23 Nov: every seat is a switch). The screen derives only which step is next, as a label.

describe('creditActions', () => {
  it('draws exactly the served flags, never a role', () => {
    const draft = credit({ status: 'draft', can_sign: true, blocked: null, can_void: true })
    expect(creditActions(draft, false)).toEqual({
      nextStep: 'recorded', canSign: true, blocked: null, canVoid: true,
    })
    const other = credit({ status: 'draft', can_sign: false, blocked: null, can_void: false })
    expect(creditActions(other, false)).toMatchObject({ canSign: false, canVoid: false })
  })

  it('names the next step from the status and whether the check is armed', () => {
    expect(creditActions(credit({ status: 'admin_signed' }), false).nextStep).toBe('approved')
    expect(creditActions(credit({ status: 'admin_signed' }), true).nextStep).toBe('checked')
    expect(creditActions(credit({ status: 'finance_checked' }), true).nextStep).toBe('approved')
  })

  it('says WHY an approver cannot countersign yet, as the server serves it', () => {
    const signed = credit({ status: 'admin_signed', can_sign: false, blocked: 'awaiting_finance' })
    expect(creditActions(signed, true)).toMatchObject({ canSign: false, blocked: 'awaiting_finance' })
  })

  it('offers nothing on a payload without the served flags', () => {
    expect(creditActions(credit({ status: 'draft' }), false)).toMatchObject({
      canSign: false, blocked: null, canVoid: false,
    })
  })

  it('offers nothing at all on a settled credit, whatever a payload says', () => {
    for (const status of ['confirmed', 'cancelled'] as const) {
      expect(creditActions(credit({ status, can_sign: true, can_void: true }), true)).toEqual({
        nextStep: null, canSign: false, blocked: null, canVoid: false,
      })
    }
  })
})

describe('creditArmed', () => {
  it('reads the per-credit flag when the server sends one (A1.10a review fix)', () => {
    // The only key holder signed this credit as maker: the server says it is NOT armed for it,
    // though the screen-wide flag is true, so it goes straight to the approver.
    expect(creditArmed(credit({ status: 'admin_signed', check_required: false }), true)).toBe(false)
    expect(creditArmed(credit({ status: 'admin_signed', check_required: true }), false)).toBe(true)
  })

  it('falls back to the screen-wide flag on a payload without it', () => {
    expect(creditArmed(credit({ status: 'admin_signed' }), true)).toBe(true)
    expect(creditArmed(credit({ status: 'admin_signed' }), false)).toBe(false)
  })
})

describe('canRecordCredit', () => {
  it('reads the served can_record_credit, never a role (owner Q-A, 23 Nov)', () => {
    expect(canRecordCredit({ can_record_credit: true })).toBe(true)
    expect(canRecordCredit({ can_record_credit: false })).toBe(false)
    expect(canRecordCredit({})).toBe(false)
  })
})

describe('creditableProgrammes', () => {
  const detail = (memberships: unknown[]) =>
    ({ memberships } as unknown as AdminSponsorDetail)

  it('offers a gift the sponsor was accepted into but holds NO wallet in', () => {
    // The case a first credit is for. Reading the wallet list instead would offer nothing.
    expect(creditableProgrammes(detail([
      { programme_id: 7, programme_name: 'BrightPath Bursary', status: 'approved' },
    ]))).toEqual([{ programme_id: 7, programme_name: 'BrightPath Bursary' }])
  })

  it('excludes a membership that is not approved — the service would refuse the credit', () => {
    expect(creditableProgrammes(detail([
      { programme_id: 7, programme_name: 'Pending Gift', status: 'pending' },
      { programme_id: 8, programme_name: 'Revoked Gift', status: 'revoked' },
    ]))).toEqual([])
  })

  it('skips a legacy membership with no programme', () => {
    expect(creditableProgrammes(detail([
      { programme_id: null, programme_name: '', status: 'approved' },
    ]))).toEqual([])
  })
})

describe('creditErrorKey', () => {
  it('passes a code the server actually answers with', () => {
    expect(creditErrorKey('same_signer')).toBe('same_signer')
    expect(creditErrorKey('sponsor_not_in_programme')).toBe('sponsor_not_in_programme')
  })

  it('falls back rather than rendering a raw key path on screen', () => {
    // Our t() returns the key on a miss, so an unmapped code would print
    // "admin.sponsors.detail.creditError.some_new_code" to an admin (cf. L109).
    expect(creditErrorKey('some_new_code')).toBe('unknown')
    expect(creditErrorKey(undefined)).toBe('unknown')
    expect(creditErrorKey('')).toBe('unknown')
  })
})
