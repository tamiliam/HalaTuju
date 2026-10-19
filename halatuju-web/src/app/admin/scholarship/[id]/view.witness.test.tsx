/**
 * @jest-environment jsdom
 *
 * Only a super records a witness (sources Sprint C, owner's ruling 2026-10-09 — until sources have
 * logins). The server refuses everyone else (`AdminBursaryWitnessView`), so the bursary card offers
 * the button to a super only; an org_admin still sees the four signature states.
 */
import { screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import { buildApplicationDetail } from '@/test/adminApplicationDetail'

installCockpitConsoleGuard()

const awarded = () => buildApplicationDetail('awarded', { bursary_agreement_enabled: true })

describe('the bursary card\'s witness button', () => {
  it('is offered to a super', async () => {
    renderCockpit({ role: 'super', app: awarded() })
    await screen.findByText('admin.scholarship.bursary.title')
    expect(screen.getByRole('button', { name: 'admin.scholarship.bursary.witnessAction' })).toBeTruthy()
  })

  it('is not offered to an org_admin, who still sees the witness state', async () => {
    renderCockpit({ role: 'org_admin', app: awarded() })
    await screen.findByText('admin.scholarship.bursary.title')
    expect(screen.getByText('admin.scholarship.bursary.witness')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'admin.scholarship.bursary.witnessAction' })).toBeNull()
  })
})
