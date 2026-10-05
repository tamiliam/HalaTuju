/**
 * @jest-environment jsdom
 *
 * Request #26 — "Correct" beside the parent/guardian phone (owner ruling R3): offered to a super
 * and an org_admin ONLY, because the server refuses everybody else (`AdminGuardianContactView`).
 * A button that renders for a role the server refuses is a button that looks live and answers 403.
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')
const correct = () => screen.queryByRole('button', { name: 'admin.scholarship.guardianCorrect' })

describe('the Correct action on the parent/guardian phone', () => {
  it.each(['super', 'org_admin'] as const)('%s is offered it', async (role) => {
    renderCockpit({ role, stage: 'awarded' })
    await loaded()
    expect(correct()).toBeTruthy()
  })

  it.each(['admin', 'reviewer', 'qc', 'finance'] as const)('%s is not', async (role) => {
    renderCockpit({ role, stage: 'awarded' })
    await loaded()
    expect(correct()).toBeNull()
  })

  it('saves the corrected contact for THIS application, then re-reads the case', async () => {
    const { api } = renderCockpit({ role: 'org_admin', stage: 'awarded' })
    await loaded()
    api.correctGuardianContact.mockResolvedValue({ name: 'Test Guardian 03', phone: '013-999 8888', changed: true })
    const reads = api.getScholarshipApplication.mock.calls.length
    fireEvent.click(correct()!)
    const phone = screen.getByRole('textbox', { name: 'scholarship.apply.field.parentPhone' })
    expect((phone as HTMLInputElement).value).toBe('012-345 6788')
    fireEvent.change(phone, { target: { value: '0139998888' } })
    fireEvent.click(screen.getByRole('button', { name: 'common.save' }))
    await waitFor(() => expect(api.correctGuardianContact).toHaveBeenCalledWith(
      7, { name: 'Test Guardian 03', phone: '013-999 8888' }, { token: 'test-token' }))
    await waitFor(() => expect(api.getScholarshipApplication.mock.calls.length).toBeGreaterThan(reads))
  })
})
