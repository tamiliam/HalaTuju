/**
 * @jest-environment jsdom
 *
 * A survey's Results (student maintenance S9; the SurveyResults board), rendered. Pinned: the counts and
 * bars per choice, "who" opening the names (each a link to the scholar's file), the rating's average, the
 * written answers with names, Each scholar, Not answered, and the Remind button only where the server
 * offers it; the roles outside super / org_admin / admin call nothing.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import * as api from '@/lib/admin-api'
import SurveyResults from './SurveyResults'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k) }),
}))
let mockRole: { role: string; permissions?: string[]; mentoring?: boolean } = { role: 'admin' }
jest.mock('@/lib/adminAuthCore', () => ({ useAdminAuth: () => ({ token: 'tok', role: mockRole }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>
const K = 'admin.surveys.results'

const survey: api.SurveyRow = {
  id: 5, title: 'Check-in', intro: '', status: 'open', programme: null, opens_at: '2026-11-01T01:00:00Z',
  closes_at: '2026-11-15T15:59:00Z', audience_count: 3, answered_count: 2, email_on_open: false, remind: true,
  opened_emailed_at: null, reminded_at: null, author: { email: '', name: '', role: '' }, created_at: '2026-11-01T00:00:00Z',
  locked: true, can_delete: false, can_close: true,
  questions: [
    { id: 1, kind: 'one', text: 'Studies?', hint: '', required: true, mentor_only: false, options: ['Well', 'Struggling'] },
    { id: 2, kind: 'rating', text: 'Mentor?', hint: '', required: true, mentor_only: true, options: [] },
    { id: 3, kind: 'long', text: 'Anything else?', hint: '', required: false, mentor_only: false, options: [] },
  ],
}
const results = (over: Partial<api.SurveyResults> = {}): api.SurveyResults => ({
  survey,
  summary: [
    { question_id: 1, answered: 2, options: [{ option: 'Well', count: 1, who: [{ application_id: 7, name: 'Nur' }] },
      { option: 'Struggling', count: 1, who: [{ application_id: 8, name: 'Thivya' }] }] },
    { question_id: 2, answered: 1, average: 4, options: [1, 2, 3, 4, 5].map((n) => ({ option: n, count: n === 4 ? 1 : 0,
      who: n === 4 ? [{ application_id: 7, name: 'Nur' }] : [] })) },
    { question_id: 3, answered: 1, written: [{ application_id: 7, name: 'Nur', text: 'The bus is late.' }] },
  ],
  responses: [{ application_id: 7, name: 'Nur', submitted_at: '2026-11-02T00:00:00Z', updated_at: '2026-11-02T00:00:00Z',
    answers: { 1: 'Well', 2: 4, 3: 'The bus is late.' } }],
  not_answered: [{ application_id: 9, name: 'Arun', reminded: false }],
  can_remind: true,
  ...over,
})

beforeEach(() => { jest.clearAllMocks(); mockRole = { role: 'admin' } })

it('draws the summary: bars with who, the average, the written answers', async () => {
  mockApi.getSurveyResults.mockResolvedValue(results())
  render(<SurveyResults id={5} />)
  await screen.findByTestId('summary-1')
  expect(mockApi.getSurveyResults).toHaveBeenCalledWith(5, { token: 'tok' })
  fireEvent.click(screen.getByTestId('who-1-Struggling'))
  expect(screen.getByRole('link', { name: 'Thivya' }).getAttribute('href')).toBe('/admin/scholars/8')
  expect(screen.getByTestId('average-2').textContent).toBe(`${K}.average {"avg":"4"}`)
  expect(screen.getByTestId('summary-3').textContent).toContain('The bus is late.')
  expect(screen.getByTestId('survey-results-sub').textContent).toContain(`${K}.answered {"n":"2","count":"3","pct":"67"}`)
})

it('lists each scholar and who has not answered, and reminds once', async () => {
  mockApi.getSurveyResults.mockResolvedValue(results())
  mockApi.remindSurvey.mockResolvedValue({ ...results({ can_remind: false,
    not_answered: [{ application_id: 9, name: 'Arun', reminded: true }] }), sent: 1 })
  jest.spyOn(window, 'confirm').mockReturnValue(true)
  render(<SurveyResults id={5} />)
  await screen.findByTestId('summary-1')
  fireEvent.click(screen.getByRole('tab', { name: new RegExp(`${K}.tab.each`) }))
  expect(screen.getByTestId('response-7').textContent).toContain('The bus is late.')
  fireEvent.click(screen.getByRole('tab', { name: new RegExp(`${K}.tab.pending`) }))
  expect(screen.getByTestId('pending-9').textContent).toContain('Arun')
  fireEvent.click(screen.getAllByTestId('survey-remind')[0])
  await waitFor(() => expect(mockApi.remindSurvey).toHaveBeenCalledWith(5, { token: 'tok' }))
  await waitFor(() => expect(screen.queryByTestId('survey-remind')).toBeNull())
  expect(screen.getByTestId('pending-9').textContent).toContain(`${K}.remindedOne`)
})

it('offers no Remind button when the server does not', async () => {
  mockApi.getSurveyResults.mockResolvedValue(results({ can_remind: false }))
  render(<SurveyResults id={5} />)
  await screen.findByTestId('summary-1')
  expect(screen.queryByTestId('survey-remind')).toBeNull()
})

it('sprint S1: names are plain text for a reader without `scholars`, even one who mentors (no 404 links)', async () => {
  mockRole = { role: 'admin', permissions: ['see_all'], mentoring: true }
  mockApi.getSurveyResults.mockResolvedValue(results())
  render(<SurveyResults id={5} />)
  await screen.findByTestId('summary-1')
  fireEvent.click(screen.getByTestId('who-1-Struggling'))
  expect(screen.getByText('Thivya')).toBeTruthy()
  expect(screen.queryAllByRole('link').filter((a) => a.getAttribute('href')?.startsWith('/admin/scholars/'))).toEqual([])
})

it('refuses the other roles and calls nothing', () => {
  for (const r of ['reviewer', 'qc', 'finance', 'mentor']) {
    mockRole = { role: r }
    const { unmount } = render(<SurveyResults id={5} />)
    expect(screen.getByText('apiErrors.superAdminRequired')).toBeTruthy()
    unmount()
  }
  expect(mockApi.getSurveyResults).not.toHaveBeenCalled()
})

it('review 2: with the survey email switched off, Remind is not offered and the reason is', async () => {
  mockApi.getSurveyResults.mockResolvedValue({ ...results(), email_switch_on: false })
  render(<SurveyResults id={5} />)
  await screen.findByTestId('summary-1')
  expect(screen.queryByTestId('survey-remind')).toBeNull()
  expect(screen.getByTestId('survey-remind-off').textContent).toBe(`${K}.remindOff`)
})
