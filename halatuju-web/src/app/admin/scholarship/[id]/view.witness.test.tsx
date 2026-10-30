/**
 * @jest-environment jsdom
 *
 * Only a super records a witness (sources Sprint C, owner's ruling 2026-10-09 — until sources have
 * logins). The server refuses everyone else (`AdminBursaryWitnessView`), so the bursary card offers
 * the button to a super only; an org_admin still sees the four signature states.
 */
import { fireEvent, screen } from '@testing-library/react'

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

/** Source sign-in review L6: the super's fallback says WHICH refusal, not "something went wrong". */
describe('the witness button\'s refusals', () => {
  it.each(['witness_changed', 'no_witness_organisation', 'already_witnessed'])('%s reads in its own words', async (code) => {
    const signed = { student_signed_at: '2026-10-24', guarantor_signed_at: '2026-10-25', witness_signed_at: null,
                     foundation_signed_at: null }
    const { api } = renderCockpit({ role: 'super', app: awarded({ source: SRC, bursary_agreement: signed }) })
    api.adminWitnessBursary.mockRejectedValue(Object.assign(new Error(code), { status: 409, code }))
    fireEvent.click(await screen.findByRole('button', { name: 'admin.scholarship.bursary.witnessAction' }))
    expect(await screen.findByText(`admin.scholarship.bursary.witnessRefused.${code}`)).toBeTruthy()
  })
})
