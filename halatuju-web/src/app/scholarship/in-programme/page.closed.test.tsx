/**
 * @jest-environment jsdom
 *
 * TD-352 review round 1, item 6: the in-programme page counts a `closed` application only when it
 * was FUNDED (`active_at` stamped). An officer may now close a stalled case before any award — that
 * student has no programme and no sponsor to thank, and the api (`in_programme._require_can_thank`)
 * refuses her thank-you. `t` echoes its key.
 */
import { render, screen, waitFor } from '@testing-library/react'
import InProgrammePage from './page'
import * as api from '@/lib/api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/auth-context', () => ({
  useAuth: () => ({ status: 'ready', token: 'tok', profile: null }),
}))
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }))
jest.mock('@/components/AppHeader', () => () => null)
jest.mock('@/components/AppFooter', () => () => null)
jest.mock('@/lib/api')
const mockApi = api as jest.Mocked<typeof api>

type AppsReply = Awaited<ReturnType<typeof api.getMyScholarshipApplications>>

const serve = (app: Record<string, unknown>) =>
  mockApi.getMyScholarshipApplications.mockResolvedValue(
    { applications: [{ id: 7, cohort_name: 'B40', closure_reason: 'graduated', ...app }] } as unknown as AppsReply)

beforeEach(() => {
  jest.resetAllMocks()
  mockApi.getSemesterResults.mockResolvedValue({ results: [] } as never)
  mockApi.getPromotionalConsent.mockResolvedValue({ granted: false, is_minor: false } as never)
  mockApi.getGraduationMessages.mockResolvedValue({ messages: [] } as never)
})

it('a case closed BEFORE it was funded is not in the programme', async () => {
  serve({ status: 'closed', closure_reason: 'stalled', active_at: null })
  render(<InProgrammePage />)
  expect(await screen.findByText('scholarship.inProgramme.notInProgramme')).toBeTruthy()
  expect(mockApi.getGraduationMessages).not.toHaveBeenCalled()
})

it('a FUNDED case that was closed still reaches the page (the thank-you stays open)', async () => {
  serve({ status: 'closed', active_at: '2026-01-10T00:00:00Z' })
  render(<InProgrammePage />)
  await waitFor(() => expect(mockApi.getGraduationMessages).toHaveBeenCalledWith(7, { token: 'tok' }))
  expect(screen.queryByText('scholarship.inProgramme.notInProgramme')).toBeNull()
})
