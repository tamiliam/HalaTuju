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

const SRC = { id: 3, code: 'test-source', name: 'Test Referring Organisation' }
const awarded = (extra: object = { source: SRC }) =>
  buildApplicationDetail('awarded', { bursary_agreement_enabled: true, ...extra })
const button = () => screen.queryByRole('button', { name: 'admin.scholarship.bursary.witnessAction' })

describe('the bursary card\'s witness button', () => {
  it('is offered to a super when the application has a source', async () => {
    renderCockpit({ role: 'super', app: awarded() })
    await screen.findByText('admin.scholarship.bursary.title')
    expect(button()).toBeTruthy()
  })

  it('is offered to a super when an override is assigned and there is no source', async () => {
    renderCockpit({ role: 'super', app: awarded({ source: null, witness_org: SRC }) })
    await screen.findByText('admin.scholarship.bursary.title')
    expect(button()).toBeTruthy()
  })

  it('is not offered with neither a source nor an override (the server refuses: no_witness_organisation)', async () => {
    renderCockpit({ role: 'super', app: awarded({ source: null, witness_org: null }) })
    await screen.findByText('admin.scholarship.bursary.title')
    expect(screen.getByText('admin.scholarship.bursary.witness')).toBeTruthy()
    expect(button()).toBeNull()
  })

  it('is not offered to an org_admin, who still sees the witness state', async () => {
    renderCockpit({ role: 'org_admin', app: awarded() })
    await screen.findByText('admin.scholarship.bursary.title')
    expect(screen.getByText('admin.scholarship.bursary.witness')).toBeTruthy()
    expect(button()).toBeNull()
  })
})
