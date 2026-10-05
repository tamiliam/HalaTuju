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

  const open = async (app = flagged()) => {
    const view = renderCockpit({ role: 'org_admin', app })
    await loaded()
    view.api.recordGuardianCall.mockResolvedValue({ id: 1, outcome: 'shared_confirmed', name: 'G', phone: 'p', needs_call: false })
    fireEvent.click(recordCall()!)
    return view
  }
  const pick = (value: string) => fireEvent.change(
    screen.getByRole('combobox', { name: 'admin.scholarship.guardianRecordCall' }), { target: { value } })
  const save = () => screen.getByRole('button', { name: 'common.save' }) as HTMLButtonElement

  it('a confirmed call sends the number it DISPLAYED and an explicit consent, then re-reads the case', async () => {
    const { api } = await open()
    const reads = api.getScholarshipApplication.mock.calls.length
    pick('shared_confirmed')
    expect(save().disabled).toBe(true)                       // nothing pre-selected: no consent yet
    expect(screen.getAllByRole('radio').some((r) => (r as HTMLInputElement).checked)).toBe(false)
    fireEvent.click(screen.getByRole('radio', { name: 'profile.yes' }))
    fireEvent.click(save())
    await waitFor(() => expect(api.recordGuardianCall).toHaveBeenCalledWith(7, {
      outcome: 'shared_confirmed', consent: true, number: '0123456788', parent_name: '', note: '',
    }, { token: 'test-token' }))
    await waitFor(() => expect(api.getScholarshipApplication.mock.calls.length).toBeGreaterThan(reads))
  })

  it('"No" is only ever a choice someone made', async () => {
    const { api } = await open()
    pick('parent_number_confirmed')
    fireEvent.click(screen.getByRole('radio', { name: 'profile.no' }))
    fireEvent.click(save())
    await waitFor(() => expect(api.recordGuardianCall).toHaveBeenLastCalledWith(7,
      expect.objectContaining({ consent: false }), { token: 'test-token' }))
  })

  it('a corrected number is sent in the stored form, with the consent chosen', async () => {
    const { api } = await open()
    pick('parent_number_corrected')
    fireEvent.change(screen.getByRole('textbox', { name: 'scholarship.apply.field.parentPhone' }),
      { target: { value: '+60139998888' } })
    expect(save().disabled).toBe(true)
    fireEvent.click(screen.getByRole('radio', { name: 'profile.yes' }))
    fireEvent.click(save())
    await waitFor(() => expect(api.recordGuardianCall).toHaveBeenLastCalledWith(7,
      expect.objectContaining({ outcome: 'parent_number_corrected', number: '013-999 8888', consent: true }),
      { token: 'test-token' }))
  })

  it('could-not-reach asks no consent and sends the number dialled', async () => {
    const { api } = await open()
    pick('could_not_reach')
    expect(screen.queryByRole('radio')).toBeNull()
    fireEvent.click(save())
    await waitFor(() => expect(api.recordGuardianCall).toHaveBeenLastCalledWith(7,
      expect.objectContaining({ outcome: 'could_not_reach', consent: null, number: '0123456788' }),
      { token: 'test-token' }))
  })

  it('a number that changed since the dialog opened is refused in words', async () => {
    const { api } = await open()
    api.recordGuardianCall.mockRejectedValue(Object.assign(new Error('stale'), { code: 'called_number_mismatch' }))
    pick('shared_confirmed')
    fireEvent.click(screen.getByRole('radio', { name: 'profile.yes' }))
    fireEvent.click(save())
    expect((await screen.findByRole('alert')).textContent).toBe('admin.scholarship.guardianCallStale')
  })

  it('with no parent number on file, only "corrected" and "could not reach" are offered', async () => {
    const base = flagged()
    await open({ ...base, guardians: [{ name: 'G', phone: '' }] })
    const values = Array.from(screen.getByRole('combobox', { name: 'admin.scholarship.guardianRecordCall' })
      .querySelectorAll('option')).map((o) => (o as HTMLOptionElement).value)
    expect(values).toEqual(['', 'parent_number_corrected', 'could_not_reach'])
  })
})
