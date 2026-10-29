/**
 * @jest-environment jsdom
 *
 * "My Bursary" (student maintenance S3; the in-programme page moved here). Pinned:
 *  * WHO reaches it is the server's: the summary endpoint serves her own file or 404s — a 404 is the
 *    calm "not in the programme yet" and wipes the header's hint;
 *  * the results form shows only when the server says `can_record_results` (Sprint 4 widens it);
 *  * the paused notice reads `support_paused`, never a sub-state; the closed notice stays;
 *  * Overview carries her funds and latest result; only two tabs exist (the rest are hidden until
 *    their modules ship). `t` echoes its key and params.
 *
 * TD-352 carried from the old page's test: a stalled close before any award has no file — the
 * server answers 404, so she sees "not in the programme".
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import BursaryPage from './page'
import * as api from '@/lib/api'
import { KEY_HAS_BURSARY_FILE } from '@/lib/storage'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
jest.mock('@/lib/auth-context', () => ({
  useAuth: () => ({ status: 'ready', token: 'tok', profile: null }),
}))
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace: jest.fn() }) }))
jest.mock('@/components/AppHeader', () => () => null)
jest.mock('@/components/AppFooter', () => () => null)
jest.mock('@/lib/api')
const mockApi = api as jest.Mocked<typeof api>

const SUMMARY: api.BursarySummary = {
  application_id: 7, name: 'NUR AISYAH', gift: 'Flagship', course: 'Diploma in Accounting',
  institution: 'Politeknik Ungku Omar', status: 'awarded', closure_reason: '',
  in_maintenance: true, can_record_results: false, support_paused: false,
  funds: { award_amount: '2000.00', received: '1200.00', remaining: '800.00',
    last_payment: { amount: '200.00', at: '2026-10-01T00:00:00Z' } },
  latest_result: null,
}
const serve = (over: Partial<api.BursarySummary> = {}) =>
  mockApi.getBursarySummary.mockResolvedValue({ ...SUMMARY, ...over })

beforeEach(() => {
  jest.resetAllMocks()
  localStorage.clear()
  mockApi.getSemesterResults.mockResolvedValue({ results: [] } as never)
  mockApi.getPromotionalConsent.mockResolvedValue({ granted: false, is_minor: false } as never)
  mockApi.getGraduationMessages.mockResolvedValue({ messages: [] } as never)
})

it('greets her and shows her funds and latest result on the Overview', async () => {
  serve()
  render(<BursaryPage />)
  expect(await screen.findByText('scholarship.bursary.hello|{"name":"Nur"}')).toBeTruthy()
  expect(screen.getByText('scholarship.bursary.state.in')).toBeTruthy()
  expect(screen.getByTestId('bursary-funds').textContent).toContain('RM1,200.00')
  expect(screen.getByText('scholarship.bursary.latest.none')).toBeTruthy()
  expect(screen.getAllByRole('tab').map((b) => b.textContent))
    .toEqual(['scholarship.bursary.tab.overview', 'scholarship.bursary.tab.results'])
  expect(localStorage.getItem(KEY_HAS_BURSARY_FILE)).toBe('1')
  await waitFor(() => expect(mockApi.getGraduationMessages).toHaveBeenCalledWith(7, { token: 'tok' }))
})

it('the results form follows can_record_results, on the Results tab', async () => {
  serve({ status: 'active', can_record_results: true })
  render(<BursaryPage />)
  fireEvent.click(await screen.findByRole('tab', { name: 'scholarship.bursary.tab.results' }))
  expect(await screen.findByText(/scholarship\.inProgramme\.results\.add/)).toBeTruthy()
})

it('an awarded student sees her results but no form until Sprint 4', async () => {
  serve()
  render(<BursaryPage />)
  fireEvent.click(await screen.findByRole('tab', { name: 'scholarship.bursary.tab.results' }))
  expect(await screen.findByText('scholarship.inProgramme.results.empty')).toBeTruthy()
  expect(screen.queryByText(/scholarship\.inProgramme\.results\.add/)).toBeNull()
})

it('a paused student sees the paused notice (support_paused, never a sub-state)', async () => {
  serve({ support_paused: true })
  render(<BursaryPage />)
  expect(await screen.findByText('scholarship.inProgramme.onHold.title')).toBeTruthy()
  expect(screen.getByText('scholarship.bursary.state.paused')).toBeTruthy()
})

it('a funded case that was closed still reaches the hub, read-only', async () => {
  serve({ status: 'closed', closure_reason: 'graduated', in_maintenance: false })
  render(<BursaryPage />)
  expect(await screen.findByText('scholarship.inProgramme.closed.graduated.title')).toBeTruthy()
  fireEvent.click(screen.getByRole('tab', { name: 'scholarship.bursary.tab.results' }))
  expect(screen.queryByText(/scholarship\.inProgramme\.results\.add/)).toBeNull()
})

it('no file (a 404) is the calm not-in-the-programme page, and the header hint goes', async () => {
  localStorage.setItem(KEY_HAS_BURSARY_FILE, '1')
  mockApi.getBursarySummary.mockRejectedValue(Object.assign(new Error('Not found'), { status: 404 }))
  render(<BursaryPage />)
  expect(await screen.findByText('scholarship.inProgramme.notInProgramme')).toBeTruthy()
  expect(localStorage.getItem(KEY_HAS_BURSARY_FILE)).toBeNull()
  expect(mockApi.getGraduationMessages).not.toHaveBeenCalled()
})
