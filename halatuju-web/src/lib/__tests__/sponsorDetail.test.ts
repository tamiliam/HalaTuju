import {
  canRecordCredit, canVoid, creditActions, creditableProgrammes, creditChain, creditErrorKey,
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

// ── S2: the actions the credit UI may offer ─────────────────────────────────────
// Every rule below is ENFORCED by `sponsorship.sign_admin_credit`; these tests pin the
// mirror, so a divergence shows up here rather than as a button the server refuses.

describe('creditActions', () => {
  it('offers the maker signature on a draft, to the maker only', () => {
    const draft = credit({ status: 'draft' })
    expect(creditActions(draft, false, 'admin')).toMatchObject({ nextStep: 'recorded', canSign: true })
    expect(creditActions(draft, false, 'org_admin').canSign).toBe(false)
    expect(creditActions(draft, false, 'finance').canSign).toBe(false)
  })

  it('sends a signed credit to the APPROVER when finance is dormant', () => {
    // BrightPath's live path today: no finance admin, so the chain is two steps.
    const signed = credit({ status: 'admin_signed' })
    expect(creditActions(signed, false, 'org_admin')).toMatchObject({ nextStep: 'approved', canSign: true })
    expect(creditActions(signed, false, 'admin').canSign).toBe(false)
  })

  it('sends it to FINANCE instead once a finance admin is appointed', () => {
    const signed = credit({ status: 'admin_signed' })
    expect(creditActions(signed, true, 'finance')).toMatchObject({ nextStep: 'checked', canSign: true })
  })

  it('tells an org_admin WHY they cannot countersign yet, rather than hiding the reason', () => {
    // The service answers `finance_check_required` for exactly this case, because from the
    // approver's seat nothing looks amiss. The screen says the same thing.
    const signed = credit({ status: 'admin_signed' })
    expect(creditActions(signed, true, 'org_admin')).toMatchObject({
      canSign: false, blocked: 'awaiting_finance',
    })
  })

  it('returns the credit to the approver after the finance check', () => {
    const checked = credit({ status: 'finance_checked' })
    expect(creditActions(checked, true, 'org_admin')).toMatchObject({ nextStep: 'approved', canSign: true })
    expect(creditActions(checked, true, 'finance').canSign).toBe(false)
  })

  it('lets a super sign any step', () => {
    expect(creditActions(credit({ status: 'draft' }), false, 'super').canSign).toBe(true)
    expect(creditActions(credit({ status: 'admin_signed' }), true, 'super').canSign).toBe(true)
    expect(creditActions(credit({ status: 'finance_checked' }), true, 'super').canSign).toBe(true)
  })

  it('offers nothing at all on a settled credit', () => {
    for (const status of ['confirmed', 'cancelled'] as const) {
      expect(creditActions(credit({ status }), true, 'super')).toEqual({
        nextStep: null, canSign: false, blocked: null, canVoid: false,
      })
    }
  })

  it('offers Void to the maker and the approver, never on confirmed money', () => {
    const draft = credit({ status: 'draft' })
    expect(creditActions(draft, false, 'admin').canVoid).toBe(true)
    expect(creditActions(draft, false, 'org_admin').canVoid).toBe(true)
    expect(creditActions(draft, false, 'super').canVoid).toBe(true)
    // Finance checks; it does not undo.
    expect(creditActions(draft, false, 'finance').canVoid).toBe(false)
    expect(creditActions(credit({ status: 'confirmed' }), false, 'admin').canVoid).toBe(false)
  })

  it('refuses every action to a role with no business here', () => {
    for (const role of ['reviewer', 'qc', 'partner']) {
      const a = creditActions(credit({ status: 'draft' }), false, role)
      expect(a.canSign).toBe(false)
      expect(a.canVoid).toBe(false)
    }
  })
})

describe('canRecordCredit', () => {
  it('is the maker or a super — org_admin is deliberately excluded', () => {
    // The approver must stay free to countersign; a maker who is also the approver cannot
    // complete their own chain (`record_admin_credit` refuses org_admin for this reason).
    expect(canRecordCredit('admin')).toBe(true)
    expect(canRecordCredit('super')).toBe(true)
    expect(canRecordCredit('org_admin')).toBe(false)
    expect(canRecordCredit('finance')).toBe(false)
    expect(canRecordCredit('reviewer')).toBe(false)
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
