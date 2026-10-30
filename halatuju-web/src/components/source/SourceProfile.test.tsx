/**
 * @jest-environment jsdom
 *
 * A source user's Profile (source sign-in S3): "You" (own name; the sign-in email shown, never
 * edited) and "Organisation" (name, contact person, email for updates, phone) — `admin/source/
 * profile/` only. Save wakes only on a real change, sends the user half only when the name changed,
 * and every refusal code reads in its own words.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import SourceProfile from './SourceProfile'
import * as api from '@/lib/admin-api'
import { PROFILE } from './testFixtures'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
const refreshRole = jest.fn()
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'source_partner' }, refreshRole }),
}))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const save = () => screen.getByText('common.save').closest('button') as HTMLButtonElement

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getSourceProfile.mockResolvedValue(PROFILE)
})

it('shows both cards; the sign-in email is read-only; Save sleeps until something changes', async () => {
  render(<SourceProfile />)
  await screen.findByDisplayValue('MUETMyWay')
  // Two fields hold that address — the read-only sign-in and the editable contact email.
  const both = screen.getAllByDisplayValue('muetmyway@example.org') as HTMLInputElement[]
  expect(both.map((i) => i.disabled)).toEqual([true, false])
  expect(save().disabled).toBe(true)
  fireEvent.change(screen.getByDisplayValue('016-845 1270'), { target: { value: '0168451271' } })
  expect(save().disabled).toBe(false)
})

it('saves the organisation details, and the user half only when the name changed', async () => {
  mockApi.updateSourceProfile.mockResolvedValue({
    ...PROFILE, source: { ...PROFILE.source, contact_person: 'Kavi' } })
  render(<SourceProfile />)
  const person = (await screen.findAllByDisplayValue('Audrey Koh Sui Ean'))[1]
  fireEvent.change(person, { target: { value: 'Kavi' } })
  fireEvent.click(save())
  await waitFor(() => expect(mockApi.updateSourceProfile).toHaveBeenCalledWith({
    source: { name: 'MUETMyWay', contact_person: 'Kavi', contact_email: 'muetmyway@example.org',
              phone: '016-845 1270' },
  }, { token: 'tok' }))
  expect(await screen.findByText('admin.sourceConsole.profile.saved')).toBeTruthy()
  expect(refreshRole).not.toHaveBeenCalled()
})

it('a changed own name goes as `user.name` and refreshes the header', async () => {
  mockApi.updateSourceProfile.mockResolvedValue({ ...PROFILE, user: { ...PROFILE.user, name: 'Audrey K' } })
  render(<SourceProfile />)
  const own = (await screen.findAllByDisplayValue('Audrey Koh Sui Ean'))[0]
  fireEvent.change(own, { target: { value: 'Audrey K' } })
  fireEvent.click(save())
  await waitFor(() => expect(mockApi.updateSourceProfile).toHaveBeenCalledWith(
    expect.objectContaining({ user: { name: 'Audrey K' } }), { token: 'tok' }))
  await waitFor(() => expect(refreshRole).toHaveBeenCalled())
})

it.each(['name_required', 'source_name_required', 'bad_email', 'not_editable', 'source_unavailable', 'odd'])(
  'shows the %s refusal in its own words', async (code) => {
    mockApi.updateSourceProfile.mockRejectedValue(Object.assign(new Error(code), { code }))
    render(<SourceProfile />)
    fireEvent.change(await screen.findByDisplayValue('016-845 1270'), { target: { value: '0168451271' } })
    fireEvent.click(save())
    const words = code === 'odd' ? 'generic' : code
    await waitFor(() => expect(screen.getByRole('alert').textContent)
      .toBe(`admin.sourceConsole.profile.error.${words}`))
  })
