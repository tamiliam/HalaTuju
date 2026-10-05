/**
 * @jest-environment jsdom
 *
 * Request #26 — the student's parent/guardian contact on /profile.
 *  * R4: drawn ONLY for a student who has applied — otherwise nothing at all.
 *  * R2: while bursary signing is possible it is read-only, with the note saying why and who to ask.
 *  * Otherwise the student may correct it; a save the server refuses as locked flips to the note.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import GuardianContactSection from './GuardianContactSection'
import * as api from '@/lib/api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/auth-context', () => ({ useAuth: () => ({ token: 'tok' }) }))
jest.mock('@/lib/api')
const mockApi = api as jest.Mocked<typeof api>

const contact = (over: Partial<api.GuardianContact> = {}): api.GuardianContact => ({
  has_scholarship_application: true, guardian_contact_locked: false,
  name: 'Ravi a/l Muthu', phone: '0123456789', ...over,
})

beforeEach(() => jest.resetAllMocks())

it('draws nothing for a student who has never applied', async () => {
  mockApi.getGuardianContact.mockResolvedValue(contact({ has_scholarship_application: false }))
  const { container } = render(<GuardianContactSection />)
  await waitFor(() => expect(mockApi.getGuardianContact).toHaveBeenCalledWith({ token: 'tok' }))
  expect(container.innerHTML).toBe('')
  expect(screen.queryByText('profile.guardianContact')).toBeNull()
})

it('shows the contact on its own line, editable, for an applicant', async () => {
  mockApi.getGuardianContact.mockResolvedValue(contact())
  render(<GuardianContactSection />)
  expect(await screen.findByText('profile.guardianContact')).toBeTruthy()
  expect(screen.getByText('Ravi a/l Muthu')).toBeTruthy()
  expect(screen.getByText('012-345 6789')).toBeTruthy()
  expect(screen.queryByText('profile.guardianContactLocked')).toBeNull()
  expect(screen.getByRole('button', { name: 'profile.edit' })).toBeTruthy()
})

it('is read-only with the locked note while the agreement is being signed', async () => {
  mockApi.getGuardianContact.mockResolvedValue(contact({ guardian_contact_locked: true }))
  render(<GuardianContactSection />)
  expect(await screen.findByText('profile.guardianContactLocked')).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'profile.edit' })).toBeNull()
  expect(screen.getByText('012-345 6789')).toBeTruthy()
})

it('saves a corrected number, formatted the way the apply form stores it', async () => {
  mockApi.getGuardianContact.mockResolvedValue(contact())
  mockApi.updateGuardianContact.mockResolvedValue({ ...contact({ phone: '013-999 8888' }), changed: true })
  render(<GuardianContactSection />)
  fireEvent.click(await screen.findByRole('button', { name: 'profile.edit' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'scholarship.apply.field.parentPhone' }),
    { target: { value: '0139998888' } })
  fireEvent.click(screen.getByRole('button', { name: 'profile.save' }))
  await waitFor(() => expect(mockApi.updateGuardianContact).toHaveBeenCalledWith(
    { name: 'Ravi a/l Muthu', phone: '013-999 8888' }, { token: 'tok' }))
  expect(await screen.findByText('013-999 8888')).toBeTruthy()
})

it('an invalid number cannot be saved', async () => {
  mockApi.getGuardianContact.mockResolvedValue(contact())
  render(<GuardianContactSection />)
  fireEvent.click(await screen.findByRole('button', { name: 'profile.edit' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'scholarship.apply.field.parentPhone' }),
    { target: { value: '0123' } })
  expect(screen.getByText('scholarship.apply.error.phone')).toBeTruthy()
  expect((screen.getByRole('button', { name: 'profile.save' }) as HTMLButtonElement).disabled).toBe(true)
})

it('a save refused as locked turns into the locked note', async () => {
  mockApi.getGuardianContact.mockResolvedValue(contact())
  mockApi.updateGuardianContact.mockRejectedValue(
    Object.assign(new Error('locked'), { code: 'guardian_contact_locked' }))
  render(<GuardianContactSection />)
  fireEvent.click(await screen.findByRole('button', { name: 'profile.edit' }))
  fireEvent.click(screen.getByRole('button', { name: 'profile.save' }))
  expect(await screen.findByText('profile.guardianContactLocked')).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'profile.edit' })).toBeNull()
})

it('a stored +60 number pre-fills in a form that can be saved (review F4)', async () => {
  mockApi.getGuardianContact.mockResolvedValue(contact({ phone: '+60123456789' }))
  render(<GuardianContactSection />)
  fireEvent.click(await screen.findByRole('button', { name: 'profile.edit' }))
  const phone = screen.getByRole('textbox', { name: 'scholarship.apply.field.parentPhone' }) as HTMLInputElement
  expect(phone.value).toBe('012-345 6789')
  expect(screen.queryByText('scholarship.apply.error.phone')).toBeNull()
  expect((screen.getByRole('button', { name: 'profile.save' }) as HTMLButtonElement).disabled).toBe(false)
})

it("the student's own number is refused in words (review F3)", async () => {
  mockApi.getGuardianContact.mockResolvedValue(contact())
  mockApi.updateGuardianContact.mockRejectedValue(
    Object.assign(new Error('own'), { code: 'guardian_phone_is_students' }))
  render(<GuardianContactSection />)
  fireEvent.click(await screen.findByRole('button', { name: 'profile.edit' }))
  fireEvent.click(screen.getByRole('button', { name: 'profile.save' }))
  expect(await screen.findByText('profile.guardianPhoneIsOwn')).toBeTruthy()
})
