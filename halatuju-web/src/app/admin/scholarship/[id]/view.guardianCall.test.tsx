/**
 * @jest-environment jsdom
 *
 * Request #26 — the owner's consent framing (2026-10-05): a parent phone that is the student's own
 * is FLAGGED ("Shared phone — call the parent") and an admin RECORDS the call. Super + org_admin
 * only, like the correction (the server is the gate; a button for a role it refuses looks live and
 * answers 403).
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import { buildApplicationDetail } from '@/test/adminApplicationDetail'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')
const recordCall = () => screen.queryByRole('button', { name: 'admin.scholarship.guardianRecordCall' })
const flagged = () => ({ ...buildApplicationDetail('awarded'), guardian_needs_call: true })

describe('the shared-phone flag and Record call', () => {
  it('shows the flag only when the payload says the parent needs a call', async () => {
    const view = renderCockpit({ role: 'super', app: flagged() })
    await loaded()
    expect(screen.getByText('admin.scholarship.guardianNeedsCall')).toBeTruthy()
    view.unmount()
    renderCockpit({ role: 'super', stage: 'awarded' })
    await loaded()
    expect(screen.queryByText('admin.scholarship.guardianNeedsCall')).toBeNull()
  })

  it.each(['super', 'org_admin'] as const)('%s may record a call', async (role) => {
    renderCockpit({ role, app: flagged() })
    await loaded()
    expect(recordCall()).toBeTruthy()
  })

  it.each(['admin', 'reviewer', 'qc', 'finance'] as const)('%s may not', async (role) => {
    renderCockpit({ role, app: flagged() })
    await loaded()
    expect(recordCall()).toBeNull()
  })

  it('a confirmed call sends the outcome and consent, never a number, then re-reads the case', async () => {
    const { api } = renderCockpit({ role: 'org_admin', app: flagged() })
    await loaded()
    api.recordGuardianCall.mockResolvedValue({ id: 1, outcome: 'shared_confirmed', name: 'G', phone: 'p', needs_call: false })
    const reads = api.getScholarshipApplication.mock.calls.length
    fireEvent.click(recordCall()!)
    fireEvent.change(screen.getByRole('combobox', { name: 'admin.scholarship.guardianRecordCall' }),
      { target: { value: 'shared_confirmed' } })
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(api.recordGuardianCall).toHaveBeenCalledWith(7, {
      outcome: 'shared_confirmed', consent: true, number: '', parent_name: '', note: '',
    }, { token: 'test-token' }))
    await waitFor(() => expect(api.getScholarshipApplication.mock.calls.length).toBeGreaterThan(reads))
  })

  it('a corrected number is sent in the stored form; could-not-reach sends no consent', async () => {
    const { api } = renderCockpit({ role: 'super', app: flagged() })
    await loaded()
    api.recordGuardianCall.mockResolvedValue({ id: 1, outcome: 'x' as never, name: '', phone: '', needs_call: false })
    fireEvent.click(recordCall()!)
    const outcome = screen.getByRole('combobox', { name: 'admin.scholarship.guardianRecordCall' })
    fireEvent.change(outcome, { target: { value: 'parent_number_corrected' } })
    fireEvent.change(screen.getByRole('textbox', { name: 'scholarship.apply.field.parentPhone' }),
      { target: { value: '+60139998888' } })
    fireEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(api.recordGuardianCall).toHaveBeenLastCalledWith(7,
      expect.objectContaining({ outcome: 'parent_number_corrected', number: '013-999 8888', consent: false }),
      { token: 'test-token' }))

    fireEvent.click(await screen.findByRole('button', { name: 'admin.scholarship.guardianRecordCall' }))
    fireEvent.change(screen.getByRole('combobox', { name: 'admin.scholarship.guardianRecordCall' }),
      { target: { value: 'could_not_reach' } })
    expect(screen.queryByRole('checkbox')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(api.recordGuardianCall).toHaveBeenLastCalledWith(7,
      expect.objectContaining({ outcome: 'could_not_reach', consent: null }), { token: 'test-token' }))
  })
})
