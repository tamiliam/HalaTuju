/**
 * @jest-environment jsdom
 *
 * POST-AWARD-CUT (2026-11-17): the cockpit draws a write control only on the SERVED flags —
 * `can_write` (`may_write_case`), `can_cancel_decline` (`may_cancel_held_decline`) and `can_tranche`
 * (`may_tranche`). It works none out from the role: a served `false` hides the control even for a role
 * that once wrote. Each test states the flags it is served (the harness defaults them to false).
 */
import { screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import { buildApplicationDetail } from '@/test/adminApplicationDetail'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')
const HOLD = { name: 'admin.scholarship.cooloff.holdAward' }
const CANCEL = { name: 'admin.scholarship.cooloff.cancelDecline' }
const AWARD_DUE = { award_due_at: '2026-12-01T00:00:00Z' }

describe('the cool-off buttons follow the served flags', () => {
  it('the assigned reviewer sees no Hold on an awarded case (served can_write false)', async () => {
    renderCockpit({ role: 'reviewer', stage: 'awarded', build: AWARD_DUE })
    await loaded()
    expect(screen.queryByRole('button', HOLD)).toBeNull()
  })

  it('a Scholars holder sees Hold on the same case', async () => {
    renderCockpit({ role: 'admin', stage: 'awarded', build: AWARD_DUE, writes: { can_write: true } })
    await loaded()
    expect(screen.getByRole('button', HOLD)).toBeTruthy()
  })

  it('a held pre-award decline keeps its cancel for the assignee, though can_write is false', async () => {
    const { app } = renderCockpit({ role: 'reviewer', stage: 'rejected', writes: { can_cancel_decline: true } })
    await loaded()
    expect(app.can_write).toBe(false)
    expect(screen.getByRole('button', CANCEL)).toBeTruthy()
  })

  it('a served false hides the control whatever the role', async () => {
    const app = { ...buildApplicationDetail('rejected', {}), can_write: false, can_cancel_decline: false }
    renderCockpit({ role: 'qc', app })
    await loaded()
    expect(screen.queryByRole('button', CANCEL)).toBeNull()
  })
})

describe('the tranche controls follow the served can_tranche (review round, 18 Nov)', () => {
  const TRANCHE = { disbursements: [{ id: 1, sequence: 1, amount: '1200.00', status: 'scheduled' as const,
    label: 'Semester 1', scheduled_for: null, released_at: null, actioned_by: '', reference: '', note: '',
    sponsorship_id: null, created_at: '' }] }

  it('a writer without the tranche key sees no Release, Withhold or Schedule', async () => {
    renderCockpit({ role: 'admin', stage: 'maintenance', build: TRANCHE, writes: { can_write: true } })
    await loaded()
    expect(screen.queryByRole('button', { name: 'admin.disbursement.action.release' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'admin.disbursement.action.withhold' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'admin.disbursement.schedule' })).toBeNull()
    expect(screen.queryByText('admin.disbursement.useComputer')).toBeNull()
  })

  it('served can_tranche brings them back', async () => {
    renderCockpit({ role: 'admin', stage: 'maintenance', build: TRANCHE, writes: true })
    await loaded()
    expect(screen.getByRole('button', { name: 'admin.disbursement.action.release' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'admin.disbursement.schedule' })).toBeTruthy()
  })
})
