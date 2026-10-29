/**
 * @jest-environment jsdom
 *
 * TD-352 review round 1, item 6: the in-programme page counts a `closed` application only when it
 * was FUNDED (`active_at` stamped). An officer may now close a stalled case before any award — that
 * student has no programme and no sponsor to thank, and the api (`in_programme._require_can_thank`)
 * refuses her thank-you. `t` echoes its key.
 *
 * Student maintenance S1 (2026-10-29): the page no longer derives this from statuses — it reads the
 * server's `has_file` (who reaches the page) and `in_maintenance` (who gets the results form), both
 * from `maintenance_scope.py`. So the 65 live students, all `awarded` with a live wallet, reach it.
 * The results form follows the served `can_record_results` (active / maintenance until Sprint 4 —
 * review M2) and the paused notice the coarse `support_paused` (review L5), never the raw sub-state.
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
  serve({ status: 'closed', closure_reason: 'stalled', active_at: null, has_file: false, in_maintenance: false })
  render(<InProgrammePage />)
  expect(await screen.findByText('scholarship.inProgramme.notInProgramme')).toBeTruthy()
  expect(mockApi.getGraduationMessages).not.toHaveBeenCalled()
})

it('a FUNDED case that was closed still reaches the page (the thank-you stays open)', async () => {
  serve({ status: 'closed', active_at: '2026-01-10T00:00:00Z', has_file: true, in_maintenance: false })
  render(<InProgrammePage />)
  await waitFor(() => expect(mockApi.getGraduationMessages).toHaveBeenCalledWith(7, { token: 'tok' }))
  expect(screen.queryByText('scholarship.inProgramme.notInProgramme')).toBeNull()
  // Read-only: the closed notice, and no results form.
  expect(screen.getByText('scholarship.inProgramme.closed.graduated.title')).toBeTruthy()
  expect(screen.queryByText(/scholarship\.inProgramme\.results\.add/)).toBeNull()
})

it('an AWARDED student with a live wallet reaches the page, without the results form until Sprint 4', async () => {
  serve({ status: 'awarded', closure_reason: '', has_file: true, in_maintenance: true,
          can_record_results: false, support_paused: false })
  render(<InProgrammePage />)
  await waitFor(() => expect(mockApi.getSemesterResults).toHaveBeenCalledWith(7, { token: 'tok' }))
  expect(screen.queryByText('scholarship.inProgramme.notInProgramme')).toBeNull()
  expect(screen.queryByText(/scholarship\.inProgramme\.results\.add/)).toBeNull()
  expect(screen.queryByText('scholarship.inProgramme.onHold.title')).toBeNull()
})

it('an ACTIVE student gets the results form (the server says can_record_results)', async () => {
  serve({ status: 'active', closure_reason: '', has_file: true, in_maintenance: true,
          can_record_results: true, support_paused: false })
  render(<InProgrammePage />)
  expect(await screen.findByText(/scholarship\.inProgramme\.results\.add/)).toBeTruthy()
})

it('an on-hold awarded student sees the paused notice', async () => {
  serve({ status: 'awarded', closure_reason: '', has_file: true, in_maintenance: true,
          can_record_results: false, support_paused: true })
  render(<InProgrammePage />)
  expect(await screen.findByText('scholarship.inProgramme.onHold.title')).toBeTruthy()
})

it('an awarded student with NO live wallet is not in the programme yet', async () => {
  serve({ status: 'awarded', closure_reason: '', has_file: false, in_maintenance: false })
  render(<InProgrammePage />)
  expect(await screen.findByText('scholarship.inProgramme.notInProgramme')).toBeTruthy()
  expect(mockApi.getSemesterResults).not.toHaveBeenCalled()
})
