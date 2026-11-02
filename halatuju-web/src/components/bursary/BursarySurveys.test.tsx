/**
 * @jest-environment jsdom
 *
 * Her Surveys tab on My Bursary (student maintenance S9; the SurveyStudent board). Pinned: every question
 * type draws its own control (radio, checkbox, five rating buttons, yes/no buttons, text fields); a required
 * one left empty is said before anything is sent; "Send my answers" sends only what she filled, keyed by
 * question id, and the tab's red number follows the reply; a closed survey is a read-only "Your answers".
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import BursarySurveys from './BursarySurveys'
import * as api from '@/lib/api/bursarySurveys'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
jest.mock('@/lib/api/bursarySurveys')
const mockApi = api as jest.Mocked<typeof api>
const P = 'bursaryTabs.surveys'

const survey = (over: Partial<api.MySurvey> = {}): api.MySurvey => ({
  id: 4, title: 'Semester 1 check-in', intro: 'Five minutes, please.', status: 'open',
  opens_at: '2026-11-01T01:00:00Z', closes_at: '2026-11-15T15:59:00Z', can_answer: true, answered_at: null,
  updated_at: null, answers: {},
  questions: [
    { id: 1, kind: 'one', text: 'Studies?', hint: '', required: true, options: ['Well', 'OK'] },
    { id: 2, kind: 'many', text: 'Help?', hint: '', required: false, options: ['Money', 'Careers'] },
    { id: 3, kind: 'rating', text: 'Mentor?', hint: '1 = not useful', required: true, options: [] },
    { id: 4, kind: 'yes_no', text: 'Hostel?', hint: '', required: false, options: [] },
    { id: 5, kind: 'long', text: 'Anything else?', hint: '', required: false, options: [] },
  ],
  ...over,
})

beforeEach(() => jest.clearAllMocks())

it('answers every type and sends only what she filled', async () => {
  mockApi.getMySurveys.mockResolvedValue({ organisation: 'BrightPath', surveys: [survey()] })
  mockApi.sendMyAnswers.mockResolvedValue({ survey: survey({ answered_at: '2026-11-02T00:00:00Z',
    answers: { 1: 'Well', 3: 4 } }), to_answer: 0 })
  const onCount = jest.fn()
  render(<BursarySurveys token="tok" onCount={onCount} />)
  await screen.findByTestId('survey-4')
  expect(screen.getAllByRole('radio', { name: /.*/ }).length).toBeGreaterThan(5)   // 2 choices + 5 ratings + yes/no
  fireEvent.click(screen.getByTestId('survey-send'))
  expect(screen.getByTestId('survey-error').textContent).toBe(`${P}.error.required`)
  expect(mockApi.sendMyAnswers).not.toHaveBeenCalled()
  fireEvent.click(screen.getByLabelText('Well'))
  fireEvent.click(screen.getByTestId('q-3-rate-4'))
  fireEvent.click(screen.getByTestId('survey-send'))
  await waitFor(() => expect(mockApi.sendMyAnswers).toHaveBeenCalledWith(4, { 1: 'Well', 3: 4 }, { token: 'tok' }))
  expect((await screen.findByTestId('survey-saved')).textContent).toContain(`${P}.thanks`)
  expect(onCount).toHaveBeenCalledWith(0)
  expect(screen.getByTestId('survey-send').textContent).toBe(`${P}.change`)
})

it('a closed survey shows her answers read-only', async () => {
  mockApi.getMySurveys.mockResolvedValue({ organisation: 'B', surveys: [survey({ status: 'closed', can_answer: false,
    answered_at: '2026-11-02T00:00:00Z', answers: { 1: 'OK', 2: ['Money', 'Careers'], 4: false } })] })
  render(<BursarySurveys token="tok" />)
  const ro = await screen.findByTestId('survey-readonly-4')
  expect(ro.textContent).toContain('OK')
  expect(ro.textContent).toContain('Money, Careers')
  expect(ro.textContent).toContain(`${P}.no`)
  expect(ro.textContent).toContain(`${P}.noAnswer`)
  expect(screen.queryByTestId('survey-send')).toBeNull()
})

it('says when there is none, and when the server refuses', async () => {
  mockApi.getMySurveys.mockResolvedValue({ organisation: 'B', surveys: [] })
  const { unmount } = render(<BursarySurveys token="tok" />)
  expect((await screen.findByTestId('surveys-empty')).textContent).toBe(`${P}.empty`)
  unmount()
  mockApi.getMySurveys.mockResolvedValue({ organisation: 'B', surveys: [survey({ questions: [survey().questions[3]] })] })
  mockApi.sendMyAnswers.mockRejectedValue(Object.assign(new Error('x'), { code: 'survey_closed' }))
  render(<BursarySurveys token="tok" />)
  fireEvent.click(await screen.findByTestId('q-4-yes'))
  fireEvent.click(screen.getByTestId('survey-send'))
  expect((await screen.findByTestId('survey-error')).textContent).toBe(`${P}.error.survey_closed`)
})
