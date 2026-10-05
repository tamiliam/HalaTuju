/**
 * @jest-environment jsdom
 *
 * Request #26, gap B: signing refuses `guarantor_phone_changed` when the parent phone on file is no
 * longer the number the PIN was checked against (e.g. an admin corrected it mid-window). The page
 * must say so in words — never a raw key — and put the PIN step back so the guarantor re-verifies.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useEffect } from 'react'
import ScholarshipAwardPage from './page'
import * as api from '@/lib/api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/auth-context', () => ({ useAuth: () => ({ status: 'authenticated', token: 'tok' }) }))
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }))
jest.mock('@/components/AppHeader', () => () => null)
jest.mock('@/components/AppFooter', () => () => null)
// The comprehension quiz gates the signing form; it is not what this test is about.
jest.mock('@/components/AwardComprehensionQuiz', () => function Passed({ onComplete }: { onComplete: () => void }) {
  useEffect(() => { onComplete() }, [onComplete])
  return null
})
jest.mock('@/lib/api')
const mockApi = api as jest.Mocked<typeof api>

const PREVIEW = {
  award_amount: '3000', payment_schedule: [], institution_name: 'Politeknik', course_name: 'Diploma',
  progress_standard: '', foundation_signatory_name: 'F', foundation_signatory_title: 'T',
  rendered_html: '<p>agreement</p>',
}

beforeEach(() => {
  jest.resetAllMocks()
  window.scrollTo = jest.fn()
  mockApi.getStudentAward.mockResolvedValue({
    offer: { amount: '3000', accept_deadline: null }, finalising: false, is_minor: false,
    acceptance_enabled: true, agreement_enabled: true, bursary_preview: PREVIEW,
  } as unknown as Awaited<ReturnType<typeof api.getStudentAward>>)
  mockApi.sendGuarantorPin.mockResolvedValue({ status: 'sent', phone_hint: '•••• 6789' })
  mockApi.checkGuarantorPin.mockResolvedValue({ verified: true } as Awaited<ReturnType<typeof api.checkGuarantorPin>>)
})

it('a phone changed after the PIN check reads as words and brings the PIN step back', async () => {
  const { container } = render(<ScholarshipAwardPage />)
  fireEvent.click(await screen.findByText('scholarship.award.bursary.guarantor.pin.send'))
  const verify = await screen.findByText('scholarship.award.bursary.guarantor.pin.verify')
  fireEvent.change(container.querySelector('input[autocomplete="one-time-code"]')!, { target: { value: '123456' } })
  fireEvent.click(verify)
  expect(await screen.findByText('scholarship.award.bursary.guarantor.pin.verified')).toBeTruthy()

  mockApi.respondToAward.mockRejectedValue(
    Object.assign(new Error('changed'), { code: 'guarantor_phone_changed' }))
  fireEvent.submit(container.querySelector('form')!)

  expect(await screen.findByText('scholarship.award.error.guarantor_phone_unverified')).toBeTruthy()
  expect(screen.queryByText('scholarship.award.error.guarantor_phone_changed')).toBeNull()
  await waitFor(() => expect(screen.queryByText('scholarship.award.bursary.guarantor.pin.verified')).toBeNull())
  expect(screen.getByText('scholarship.award.bursary.guarantor.pin.send')).toBeTruthy()
})

it('a PIN refused because the parent still needs a call reads as words (owner ruling A)', async () => {
  mockApi.sendGuarantorPin.mockRejectedValue(Object.assign(new Error('call'), { code: 'parent_call_needed' }))
  render(<ScholarshipAwardPage />)
  fireEvent.click(await screen.findByText('scholarship.award.bursary.guarantor.pin.send'))
  expect(await screen.findByText('scholarship.award.error.no_active_template')).toBeTruthy()
  expect(screen.queryByText('scholarship.award.bursary.guarantor.pin.error.generic')).toBeNull()
})

it('a signature refused because the parent still needs a call reads as words (owner ruling A)', async () => {
  const { container } = render(<ScholarshipAwardPage />)
  await screen.findByText('scholarship.award.bursary.guarantor.pin.send')
  mockApi.respondToAward.mockRejectedValue(Object.assign(new Error('call'), { code: 'parent_call_needed' }))
  fireEvent.submit(container.querySelector('form')!)
  expect(await screen.findByText('scholarship.award.error.no_active_template')).toBeTruthy()
})
