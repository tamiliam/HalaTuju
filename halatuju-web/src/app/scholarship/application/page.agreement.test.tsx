/**
 * @jest-environment jsdom
 *
 * TD-291 (2026-10-04): the student's application page asks for the signed bursary agreement ONLY
 * while the feature is on. `/scholarship/bursary-agreement/` answers 404 while
 * BURSARY_AGREEMENT_ENABLED is off, and this page used to ask it on every load (24 times in the
 * production logs the audit read). The award payload now says whether the route is live
 * (`agreement_enabled`), and the page reads that first.
 */
import { render, waitFor } from '@testing-library/react'
import ScholarshipApplicationPage from './page'
import * as api from '@/lib/api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/auth-context', () => ({
  useAuth: () => ({ status: 'authenticated', token: 'tok', profile: null }),
}))
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }))
jest.mock('@/components/AppHeader', () => () => null)
jest.mock('@/components/AppFooter', () => () => null)
jest.mock('@/components/ScholarshipNextSteps', () => () => null)
jest.mock('@/components/ActionCentre', () => () => null)
jest.mock('@/components/scholarship/LazyInterviewBookingPanel', () => () => null)
jest.mock('@/lib/api')
const mockApi = api as jest.Mocked<typeof api>

type AwardReply = Awaited<ReturnType<typeof api.getStudentAward>>

beforeEach(() => {
  jest.resetAllMocks()
  mockApi.getMyScholarshipApplications.mockResolvedValue(
    { applications: [] } as unknown as Awaited<ReturnType<typeof api.getMyScholarshipApplications>>)
  mockApi.getBursaryAgreement.mockRejectedValue(new Error('404'))
})

it('does not ask for the agreement while the feature is off', async () => {
  mockApi.getStudentAward.mockResolvedValue(
    { offer: null, is_minor: false, agreement_enabled: false } as AwardReply)
  render(<ScholarshipApplicationPage />)
  await waitFor(() => expect(mockApi.getStudentAward).toHaveBeenCalled())
  await waitFor(() => expect(mockApi.getMyScholarshipApplications).toHaveBeenCalled())
  expect(mockApi.getBursaryAgreement).not.toHaveBeenCalled()
})

it('does not ask when the award reply is older and carries no flag at all', async () => {
  mockApi.getStudentAward.mockResolvedValue({ offer: null, is_minor: false } as AwardReply)
  render(<ScholarshipApplicationPage />)
  await waitFor(() => expect(mockApi.getStudentAward).toHaveBeenCalled())
  expect(mockApi.getBursaryAgreement).not.toHaveBeenCalled()
})

it('asks for it once the feature is on (the positive half of the pair)', async () => {
  mockApi.getStudentAward.mockResolvedValue(
    { offer: null, is_minor: false, agreement_enabled: true } as AwardReply)
  render(<ScholarshipApplicationPage />)
  await waitFor(() => expect(mockApi.getBursaryAgreement).toHaveBeenCalledWith({ token: 'tok' }))
})
