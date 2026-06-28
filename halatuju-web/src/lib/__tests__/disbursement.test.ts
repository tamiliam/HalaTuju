import {
  FUNDED_STATUSES,
  isFunded,
  disbursementTone,
  statusKey,
  actionsFor,
  nextSequence,
  totalReleased,
} from '@/lib/disbursement'
import type { AdminDisbursement } from '@/lib/admin-api'

function row(over: Partial<AdminDisbursement> = {}): AdminDisbursement {
  return {
    id: 1,
    sequence: 1,
    amount: '500.00',
    status: 'scheduled',
    label: '',
    scheduled_for: null,
    released_at: null,
    actioned_by: '',
    reference: 'mock',
    note: '',
    sponsorship_id: null,
    created_at: '2026-06-28T00:00:00Z',
    ...over,
  }
}

describe('isFunded', () => {
  it('is true only for active/maintenance', () => {
    expect(FUNDED_STATUSES).toEqual(['active', 'maintenance'])
    expect(isFunded('active')).toBe(true)
    expect(isFunded('maintenance')).toBe(true)
    for (const s of ['recommended', 'awarded', 'closed', '', null, undefined]) {
      expect(isFunded(s as string)).toBe(false)
    }
  })
})

describe('disbursementTone / statusKey', () => {
  it('maps each status to a tone', () => {
    expect(disbursementTone('released')).toBe('green')
    expect(disbursementTone('due')).toBe('amber')
    expect(disbursementTone('withheld')).toBe('red')
    expect(disbursementTone('returned')).toBe('grey')
    expect(disbursementTone('scheduled')).toBe('blue')
  })
  it('namespaces the status label key', () => {
    expect(statusKey('released')).toBe('admin.disbursement.status.released')
  })
})

describe('actionsFor', () => {
  it('offers release/withhold/mark_due when scheduled', () => {
    expect(actionsFor('scheduled')).toEqual(['release', 'withhold', 'mark_due'])
  })
  it('drops mark_due once due', () => {
    expect(actionsFor('due')).toEqual(['release', 'withhold'])
  })
  it('only return after released', () => {
    expect(actionsFor('released')).toEqual(['return'])
  })
  it('terminal states offer nothing', () => {
    expect(actionsFor('withheld')).toEqual([])
    expect(actionsFor('returned')).toEqual([])
  })
})

describe('nextSequence', () => {
  it('is 1 for an empty ledger', () => {
    expect(nextSequence([])).toBe(1)
  })
  it('is max+1 otherwise', () => {
    expect(nextSequence([row({ sequence: 1 }), row({ sequence: 4 })])).toBe(5)
  })
})

describe('totalReleased', () => {
  it('sums only released tranches', () => {
    const rows = [
      row({ status: 'released', amount: '500.00' }),
      row({ status: 'released', amount: '250.50' }),
      row({ status: 'scheduled', amount: '999.00' }),
      row({ status: 'withheld', amount: '999.00' }),
    ]
    expect(totalReleased(rows)).toBeCloseTo(750.5)
  })
})
