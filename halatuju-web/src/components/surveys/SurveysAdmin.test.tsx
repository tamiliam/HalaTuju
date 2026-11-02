/**
 * @jest-environment jsdom
 *
 * Programme → Surveys (student maintenance S9; the SurveysAdmin board), rendered. Pinned: the status tabs
 * with the server's counts; "N of M" answered; Close now / Delete only where `can_close` / `can_delete`;
 * the roles outside super / org_admin / admin see a refusal and call nothing; a new survey sends its
 * questions (choices one per line, empty lines dropped) and Malaysian times; a LOCKED survey's edit sends
 * no questions, audience or opening time.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import * as api from '@/lib/admin-api'
import SurveysAdmin from './SurveysAdmin'
import { cleanQuestion } from './SurveyForm'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k) }),
}))
let mockRole: { role: string } = { role: 'org_admin' }
jest.mock('@/lib/adminAuthCore', () => ({ useAdminAuth: () => ({ token: 'tok', role: mockRole }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>
const K = 'admin.surveys'

const Q: api.SurveyQuestionRow = { id: 11, kind: 'one', text: 'How are your studies going?', hint: '', required: true,
  mentor_only: false, options: ['Well', 'OK'] }
const row = (over: Partial<api.SurveyRow>): api.SurveyRow => ({
  id: 1, title: 'Semester 1 check-in', intro: 'Five minutes, please.', status: 'open', programme: null,
  opens_at: '2026-11-01T01:00:00Z', closes_at: '2026-11-15T15:59:00Z', questions: [Q], audience_count: 65,
  answered_count: 38, email_on_open: false, remind: false, opened_emailed_at: null, reminded_at: null,
  author: { email: 'siti@example.org', name: 'Siti', role: 'org_admin' }, created_at: '2026-11-01T00:00:00Z',
  locked: true, can_delete: false, can_close: true, ...over,
})
const payload = (rows: api.SurveyRow[]): api.SurveysPayload => ({
  organisation: { code: 'bp', name: 'BrightPath' }, surveys: rows,
  counts: {
    open: rows.filter((r) => r.status === 'open').length, scheduled: rows.filter((r) => r.status === 'scheduled').length,
    draft: rows.filter((r) => r.status === 'draft').length, closed: rows.filter((r) => r.status === 'closed').length,
  },
  audiences: [{ programme: null, name: '', count: 65 }, { programme: 'flag', name: 'Flagship', count: 40 }],
  email_switch_on: true,
  limits: { title: 150, intro: 1000, question: 300, hint: 200, option: 120, options: 12, questions: 30 },
})

beforeEach(() => { jest.clearAllMocks(); mockRole = { role: 'org_admin' } })

it('lists the open ones with the server counts and only the offered actions', async () => {
  mockApi.getSurveys.mockResolvedValue(payload([row({}),
    row({ id: 2, status: 'draft', can_close: false, can_delete: true, locked: false, answered_count: 0 })]))
  render(<SurveysAdmin programme="flag" />)
  await screen.findByTestId('survey-row-1')
  expect(mockApi.getSurveys).toHaveBeenCalledWith('flag', { token: 'tok' })
  expect(screen.getByTestId('survey-answered-1').textContent).toBe(`${K}.answeredOf {"n":"38","count":"65"}`)
  expect(screen.getByTestId('survey-close-1')).toBeTruthy()
  expect(screen.queryByTestId('survey-delete-1')).toBeNull()
  expect(screen.getByTestId('survey-results-1').getAttribute('href')).toBe('/admin/programme/surveys/1?programme=flag')
  fireEvent.click(screen.getByRole('tab', { name: new RegExp(`${K}.tab.draft`) }))
  expect(screen.getByTestId('survey-delete-2')).toBeTruthy()
  expect(screen.queryByTestId('survey-close-2')).toBeNull()
  expect(screen.queryByTestId('survey-results-2')).toBeNull()
})

it('refuses the roles outside super, org_admin and admin and calls nothing', () => {
  for (const r of ['reviewer', 'qc', 'finance', 'mentor', 'source_partner']) {
    mockRole = { role: r }
    const { unmount } = render(<SurveysAdmin />)
    expect(screen.getByText('apiErrors.superAdminRequired')).toBeTruthy()
    unmount()
  }
  expect(mockApi.getSurveys).not.toHaveBeenCalled()
})

it('creates one with its questions and Malaysian closing time', async () => {
  mockApi.getSurveys.mockResolvedValue(payload([]))
  mockApi.createSurvey.mockResolvedValue(row({ id: 9 }))
  render(<SurveysAdmin programme="flag" />)
  fireEvent.click(await screen.findByTestId('survey-new'))
  fireEvent.change(screen.getByTestId('survey-title'), { target: { value: 'Check-in' } })
  fireEvent.change(screen.getByTestId('survey-qtext-0'), { target: { value: 'How is it going?' } })
  fireEvent.change(screen.getByTestId('survey-qoptions-0'), { target: { value: 'Well\n\nOK\n' } })
  fireEvent.change(screen.getByTestId('survey-close-date'), { target: { value: '2026-11-15' } })
  fireEvent.change(screen.getByTestId('survey-close-time'), { target: { value: '9pm' } })
  fireEvent.click(screen.getByTestId('survey-primary'))
  expect(screen.getByTestId('survey-error').textContent).toBe(`${K}.error.badTime`)
  fireEvent.change(screen.getByTestId('survey-close-time'), { target: { value: '23:59' } })
  fireEvent.click(screen.getByTestId('survey-primary'))
  await waitFor(() => expect(mockApi.createSurvey).toHaveBeenCalledWith({
    title: 'Check-in', intro: '', closes_at: '2026-11-15T23:59:00+08:00', email_on_open: false, remind: false,
    programme: null, action: 'publish',
    questions: [{ kind: 'one', text: 'How is it going?', hint: '', required: true, mentor_only: false,
      options: ['Well', 'OK'] }],
  }, 'flag', { token: 'tok' }))
})

it('a locked survey edits only the title, introduction, closing date and emails', async () => {
  mockApi.getSurveys.mockResolvedValue(payload([row({})]))
  mockApi.updateSurvey.mockResolvedValue(row({ title: 'Renamed' }))
  render(<SurveysAdmin />)
  fireEvent.click(await screen.findByTestId('survey-edit-1'))
  expect((screen.getByTestId('survey-audience') as HTMLSelectElement).disabled).toBe(true)
  expect(screen.queryByTestId('survey-add-question')).toBeNull()
  expect(screen.queryByTestId('survey-qedit-btn-0')).toBeNull()
  fireEvent.change(screen.getByTestId('survey-title'), { target: { value: 'Renamed' } })
  fireEvent.click(screen.getByTestId('survey-save'))
  await waitFor(() => expect(mockApi.updateSurvey).toHaveBeenCalledWith(1, {
    title: 'Renamed', intro: 'Five minutes, please.', email_on_open: false, remind: false,
  }, { token: 'tok' }))   // the closing date did not change, so it is not sent
})

it('shows the question error at its place', async () => {
  mockApi.getSurveys.mockResolvedValue(payload([]))
  mockApi.createSurvey.mockRejectedValue(Object.assign(new Error('x'), { code: 'options_count', body: { detail: 0 } }))
  render(<SurveysAdmin />)
  fireEvent.click(await screen.findByTestId('survey-new'))
  fireEvent.change(screen.getByTestId('survey-close-date'), { target: { value: '2026-11-15' } })
  fireEvent.click(screen.getByTestId('survey-draft'))
  expect((await screen.findByTestId('survey-error')).textContent)
    .toBe(`${K}.error.options_count ${K}.error.atQuestion {"n":"1"}`)
})

it('sends a choice list only for a choice question', () => {
  expect(cleanQuestion({ kind: 'rating', text: ' Rate ', hint: '', required: true, mentor_only: true, options: ['a'] }))
    .toEqual({ kind: 'rating', text: 'Rate', hint: '', required: true, mentor_only: true, options: [] })
})
