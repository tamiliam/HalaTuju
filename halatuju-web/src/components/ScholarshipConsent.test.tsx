/**
 * @jest-environment jsdom
 *
 * Audit sprint A2.8a (TD-400): when the parent's IC was only half read during our outage, the consent
 * refusal says "try later" (the existing blocker words), never the generic "something went wrong".
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import ScholarshipConsent from './ScholarshipConsent'
import * as api from '@/lib/api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/api')
const mockApi = api as jest.Mocked<typeof api>

const STATUS = {
  is_minor: true, consent_version: 'v', consents: [], student_name: 'PELAJAR CONTOH',
  student_nric: '110101-14-5678', student_gender: '', parent_ic_vision_nric: '', parent_ic_vision_name: '',
  blockers: [],
} as unknown as api.ConsentStatus

async function fillAndSubmit(code: string) {
  mockApi.getConsentStatus.mockResolvedValue(STATUS)
  mockApi.listDocuments.mockResolvedValue({ documents: [{ doc_type: 'parent_ic' }] } as never)
  mockApi.recordConsent.mockRejectedValueOnce(Object.assign(new Error('400'), { code }))
  render(<ScholarshipConsent token="tok" locale="en" />)
  // The switch renders before the status loads; wait for the minor-only textboxes (slow under load).
  const [name, nric] = await screen.findAllByRole('textbox')
  fireEvent.change(name, { target: { value: 'IBU CONTOH' } })
  fireEvent.change(nric, { target: { value: '750101145678' } })
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'mother' } })
  fireEvent.click(screen.getByRole('switch'))
  await act(async () => { fireEvent.submit(screen.getByRole('switch').closest('form') as HTMLFormElement) })
}

beforeEach(() => jest.clearAllMocks())

it('TD-400: a half-read parent IC refusal says try later', async () => {
  await fillAndSubmit('parent_ic_service_down')
  expect(await screen.findByText('scholarship.consent.blocker.ic_service_down')).toBeTruthy()
  expect(mockApi.recordConsent).toHaveBeenCalledTimes(1)
})

it('any other refusal keeps the generic line', async () => {
  await fillAndSubmit('parent_ic_nric_mismatch')
  expect(await screen.findByText('scholarship.consent.error')).toBeTruthy()
})
