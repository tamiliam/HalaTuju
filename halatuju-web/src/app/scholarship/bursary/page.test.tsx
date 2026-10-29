/**
 * @jest-environment jsdom
 *
 * "My Bursary" (student maintenance S3; the in-programme page moved here). Pinned:
 *  * WHO reaches it is the server's: the summary endpoint serves her own file or 404s — a 404 is the
 *    calm "not in the programme yet" and wipes the header's hint;
 *  * the results form shows only when the server says `can_record_results` (S4a: the file
 *    predicate, so an awarded student records too); a slip goes sign → PUT → record, "graduated"
 *    is the site Toggle (`role="switch"`), and each result shows its REVIEW, never a standing;
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

let mockLocale = 'en'
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: mockLocale }),
}))
jest.mock('@/lib/auth-context', () => ({
  useAuth: () => ({ status: 'ready', token: 'tok', profile: null }),
}))
// A STABLE router, as Next's is — a new object per render would re-run the page's load effect.
const mockRouter = { push: jest.fn(), replace: jest.fn() }
jest.mock('next/navigation', () => ({ useRouter: () => mockRouter }))
jest.mock('@/components/AppHeader', () => () => null)
jest.mock('@/components/AppFooter', () => () => null)
jest.mock('@/lib/api')
const mockApi = api as jest.Mocked<typeof api>

const SUMMARY: api.BursarySummary = {
  application_id: 7, name: 'NUR AISYAH', gift: 'Flagship', gift_names: { en: 'Flagship', ms: 'Unggulan', ta: 'Flagship' },
  course: 'Diploma in Accounting',
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
  mockLocale = 'en'
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

it('without can_record_results she sees her results but no form', async () => {
  serve()
  render(<BursaryPage />)
  fireEvent.click(await screen.findByRole('tab', { name: 'scholarship.bursary.tab.results' }))
  expect(await screen.findByText('scholarship.inProgramme.results.empty')).toBeTruthy()
  expect(screen.queryByText(/scholarship\.inProgramme\.results\.add/)).toBeNull()
})

it('records a result with its slip: sign, upload, then name the slip; graduated is a Toggle', async () => {
  serve({ can_record_results: true })
  mockApi.signUploadDocument.mockResolvedValue({ upload_url: 'https://put.example', storage_path: 'p/slip.pdf' } as never)
  mockApi.uploadFileToSignedUrl.mockResolvedValue(undefined as never)
  mockApi.addSemesterResult.mockResolvedValue({} as never)
  render(<BursaryPage />)
  fireEvent.click(await screen.findByRole('tab', { name: 'scholarship.bursary.tab.results' }))
  fireEvent.click(await screen.findByText(/scholarship\.inProgramme\.results\.add/))
  const toggle = screen.getByRole('switch', { name: 'scholarship.inProgramme.results.graduated' })
  expect(screen.queryByRole('checkbox')).toBeNull()
  fireEvent.click(toggle)
  const file = new File(['%PDF'], 'slip.pdf', { type: 'application/pdf' })
  fireEvent.change(screen.getByTestId('slip-input'), { target: { files: [file] } })
  fireEvent.change(screen.getByPlaceholderText('scholarship.inProgramme.results.semesterPh'), { target: { value: 'Sem 4' } })
  fireEvent.click(screen.getByText('scholarship.inProgramme.results.save'))
  await waitFor(() => expect(mockApi.addSemesterResult).toHaveBeenCalledWith(7, {
    semester: 'Sem 4', cgpa: null, graduated: true,
    slip: { storage_path: 'p/slip.pdf', original_filename: 'slip.pdf', content_type: 'application/pdf', size: 4 },
  }, { token: 'tok' }))
  expect(mockApi.signUploadDocument).toHaveBeenCalledWith('semester_result', { token: 'tok' })
  expect(mockApi.uploadFileToSignedUrl).toHaveBeenCalledWith('https://put.example', file)
})

it('a refused slip says why, in her words', async () => {
  serve({ can_record_results: true })
  mockApi.addSemesterResult.mockRejectedValue(Object.assign(new Error('x'), { code: 'bad_cgpa' }))
  render(<BursaryPage />)
  fireEvent.click(await screen.findByRole('tab', { name: 'scholarship.bursary.tab.results' }))
  fireEvent.click(await screen.findByText(/scholarship\.inProgramme\.results\.add/))
  fireEvent.click(screen.getByText('scholarship.inProgramme.results.save'))
  expect(await screen.findByText('scholarship.bursary.resultError.bad_cgpa')).toBeTruthy()
})

it('each result shows its review, and a query shows the officer’s note', async () => {
  serve()
  mockApi.getSemesterResults.mockResolvedValue({ results: [
    { id: 1, semester: 'Sem 3', cgpa: '2.40', graduated: false, note: '', created_at: '2026-10-20T00:00:00Z',
      review_status: 'queried', review_note: 'Please send the stamped slip.' },
    { id: 2, semester: 'Sem 2', cgpa: '3.10', graduated: false, note: '', created_at: '2026-07-01T00:00:00Z',
      review_status: 'accepted', review_note: '' },
  ] } as never)
  render(<BursaryPage />)
  fireEvent.click(await screen.findByRole('tab', { name: 'scholarship.bursary.tab.results' }))
  const rows = await screen.findAllByTestId('result-row')
  expect(rows[0].textContent).toContain('scholarship.bursary.review.queried')
  expect(rows[0].textContent).toContain('scholarship.bursary.review.queriedNote|{"note":"Please send the stamped slip."}')
  expect(rows[1].textContent).toContain('scholarship.bursary.review.accepted')
  // The browser never judges her CGPA (the old <= 2.0 "needs attention" chip is gone).
  expect(screen.queryByText(/scholarship\.inProgramme\.progress\./)).toBeNull()
})

it('a paused student sees the paused notice (support_paused, never a sub-state)', async () => {
  serve({ support_paused: true })
  render(<BursaryPage />)
  expect(await screen.findByText('scholarship.inProgramme.onHold.title')).toBeTruthy()
  expect(screen.getByText('scholarship.bursary.state.paused')).toBeTruthy()
})

it('a funded case that was closed still reaches the hub, read-only — and the thank-you stays open', async () => {
  serve({ status: 'closed', closure_reason: 'graduated', in_maintenance: false })
  render(<BursaryPage />)
  expect(await screen.findByText('scholarship.inProgramme.closed.graduated.title')).toBeTruthy()
  await waitFor(() => expect(mockApi.getGraduationMessages).toHaveBeenCalledWith(7, { token: 'tok' }))
  expect(screen.getByText('scholarship.inProgramme.grad.title')).toBeTruthy()
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

it('names her gift in her language, English where a translation is missing', async () => {
  mockLocale = 'ms'
  serve()
  render(<BursaryPage />)
  expect(await screen.findByText('Unggulan · Diploma in Accounting')).toBeTruthy()
})

it('a failure that is not "no file" says so, keeps the hint, and retries', async () => {
  localStorage.setItem(KEY_HAS_BURSARY_FILE, '1')
  mockApi.getBursarySummary.mockRejectedValueOnce(Object.assign(new Error('boom'), { status: 500 }))
  mockApi.getBursarySummary.mockResolvedValueOnce({ ...SUMMARY })
  render(<BursaryPage />)
  expect(await screen.findByText('scholarship.bursary.loadFailed')).toBeTruthy()
  expect(screen.queryByText('scholarship.inProgramme.notInProgramme')).toBeNull()
  expect(localStorage.getItem(KEY_HAS_BURSARY_FILE)).toBe('1')
  fireEvent.click(screen.getByRole('button', { name: 'scholarship.bursary.retry' }))
  expect(await screen.findByTestId('bursary-hello')).toBeTruthy()
})
