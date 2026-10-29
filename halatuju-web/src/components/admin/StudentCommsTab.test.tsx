/**
 * @jest-environment jsdom
 *
 * Organisation → Settings → Student communications (student maintenance S4b). Pinned:
 *  * three emails x three languages, each saying whether it is the organisation's wording or the
 *    platform default;
 *  * the platform switch is stated: OFF says nothing is sent yet — editable letters must not read as
 *    letters that go out;
 *  * Edit saves through the shared editor as `{kind, language, subject, body}`; "Use the default"
 *    sends `reset`;
 *  * a super with several organisations is asked to choose, and the choice is sent as `org`.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import StudentCommsTab from './StudentCommsTab'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin' } }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const row = (kind: api.StudentEmailKind, language: api.StudentEmailLanguage, customised = false): api.StudentEmailTemplate => ({
  key: `${kind}.${language}`, kind, language, subject: `${kind} ${language}`, body: 'Dear {name}, {link}',
  customised, placeholders: ['name', 'link', 'due_date'], updated_by_email: '', updated_at: null,
})
const PAYLOAD = (enabled = false): api.StudentEmailsPayload => ({
  organisation: { code: 'alpha', name: 'Alpha' }, enabled,
  templates: (['results_due', 'results_overdue', 'result_queried'] as const).flatMap((k) =>
    (['en', 'ms', 'ta'] as const).map((l) => row(k, l, k === 'results_due' && l === 'ms'))),
})

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getStudentEmails.mockResolvedValue(PAYLOAD())
  mockApi.saveStudentEmail.mockResolvedValue(PAYLOAD())
})

it('lists every email in every language, and says plainly that nothing is sent while switched off', async () => {
  render(<StudentCommsTab />)
  expect((await screen.findByTestId('student-comms-switch')).textContent).toBe('admin.orgSettings.studentComms.off')
  for (const k of ['results_due', 'results_overdue', 'result_queried']) {
    for (const l of ['en', 'ms', 'ta']) expect(screen.getByTestId(`student-email-${k}.${l}`)).toBeTruthy()
  }
  expect(within(screen.getByTestId('student-email-results_due.ms')).getByText('admin.orgSettings.studentComms.customised')).toBeTruthy()
  expect(within(screen.getByTestId('student-email-results_due.en')).getByText('admin.orgSettings.studentComms.default')).toBeTruthy()
})

it('saves an edit as kind + language, and "Use the default" resets', async () => {
  render(<StudentCommsTab />)
  const li = await screen.findByTestId('student-email-result_queried.ta')
  fireEvent.click(within(li).getByText('admin.orgSettings.studentComms.edit'))
  const subject = within(li).getAllByRole('textbox')[0]
  fireEvent.change(subject, { target: { value: 'A question' } })
  fireEvent.click(within(li).getByText('admin.sources.save'))
  await waitFor(() => expect(mockApi.saveStudentEmail).toHaveBeenCalledWith(
    expect.objectContaining({ kind: 'result_queried', language: 'ta', subject: 'A question' }), undefined, { token: 'tok' }))
  fireEvent.click(within(screen.getByTestId('student-email-results_due.ms')).getByText('admin.orgSettings.studentComms.reset'))
  await waitFor(() => expect(mockApi.saveStudentEmail).toHaveBeenLastCalledWith(
    { kind: 'results_due', language: 'ms', reset: true }, undefined, { token: 'tok' }))
})

it('a super with several organisations chooses one, sent as org', async () => {
  mockApi.getStudentEmails
    .mockRejectedValueOnce(Object.assign(new Error('x'), { body: { code: 'organisation_required', organisations: ['alpha', 'beta'] } }))
    .mockResolvedValueOnce(PAYLOAD(true))
  render(<StudentCommsTab />)
  fireEvent.click(await screen.findByText('beta'))
  expect((await screen.findByTestId('student-comms-switch')).textContent).toBe('admin.orgSettings.studentComms.on')
  expect(mockApi.getStudentEmails).toHaveBeenLastCalledWith('beta', { token: 'tok' })
})
