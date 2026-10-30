/**
 * @jest-environment jsdom
 *
 * Organisation → Settings → Student communications (S4b; every email + switches S6a, layout A). Pinned:
 *  * every email the server lists sits under its heading, ONE row each (not one row per language);
 *  * a switchable email has the switch, a locked one has NO switch and says why — both read from the
 *    server's payload, never decided here; switching posts `{key, enabled}` and a refusal rolls back;
 *  * a platform flag holding an email back is said on the row; last sent / not yet / not recorded;
 *  * the worded (Results) emails: one chip per language marking whose wording it is, and an editor
 *    with a tab per language that saves `{kind, language, …}` and resets with "Use the default";
 *  * the read-only wording opens in language tabs; the partner notice links to Sources;
 *  * the Results platform switch is stated; a super with several organisations chooses one.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import StudentCommsTab from './StudentCommsTab'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin' } }) }))
jest.mock('next/link', () => ({ __esModule: true, default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>
const P = 'admin.orgSettings.studentComms'

const tpl = (kind: api.StudentEmailKind, language: api.StudentEmailLanguage, customised = false): api.StudentEmailTemplate => ({
  key: `${kind}.${language}`, kind, language, subject: `${kind} ${language}`, body: 'Dear {name}, {link}',
  customised, placeholders: ['name', 'link', 'due_date'], updated_by_email: '', updated_at: null,
})
const row = (key: string, over: Partial<api.StudentEmailRow> = {}): api.StudentEmailRow => ({
  key, group: 'applying', languages: 'en_ms_ta', editable: false, switchable: false, enabled: true, lock: 'decision',
  platform_flag: null, platform_on: true, tracked: true, last_sent_at: null, managed_on: null, wording: {}, ...over,
})
const PAYLOAD = (over: Partial<api.StudentEmailsPayload> = {}): api.StudentEmailsPayload => ({
  organisation: { code: 'alpha', name: 'Alpha' }, enabled: false,
  groups: ['account', 'applying', 'interview', 'award', 'results', 'closure'],
  catalogue: [
    row('verify_email', { group: 'account', lock: 'credential', tracked: false }),
    row('application_received', { switchable: true, lock: null, last_sent_at: '2026-10-29T08:00:00Z',
      wording: { en: { subject: 'We received it', body: 'Dear {name}' }, ms: { subject: 'Diterima', body: 'Salam {name}' },
        ta: { subject: 'பெற்றோம்', body: 'அன்புள்ள {name}' } } }),
    row('declined'),
    row('partner_access', { group: 'interview', languages: 'en', lock: 'managed_elsewhere', tracked: false, managed_on: 'sources' }),
    row('interview_reminders', { group: 'interview', languages: 'en_ms', switchable: true, lock: null, enabled: false }),
    row('results_due', { group: 'results', editable: true, switchable: true, lock: null, platform_on: false,
      platform_flag: 'MAINTENANCE_REMINDERS_ENABLED' }),
  ],
  templates: (['en', 'ms', 'ta'] as const).map((l) => tpl('results_due', l, l === 'ms')),
  ...over,
})

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getStudentEmails.mockResolvedValue(PAYLOAD())
  mockApi.saveStudentEmail.mockResolvedValue(PAYLOAD())
  mockApi.setStudentEmailSwitch.mockResolvedValue(PAYLOAD())
})

it('puts every email under its heading, one row each, and skips an empty heading', async () => {
  render(<StudentCommsTab />)
  const applying = await screen.findByTestId('student-comms-group-applying')
  expect(within(applying).getByTestId('student-email-application_received')).toBeTruthy()
  expect(within(applying).getByTestId('student-email-declined')).toBeTruthy()
  expect(within(screen.getByTestId('student-comms-group-account')).getByTestId('student-email-verify_email')).toBeTruthy()
  expect(screen.queryByTestId('student-comms-group-award')).toBeNull()
  expect(screen.queryByTestId('student-email-results_due.en')).toBeNull()          // not a row per language
})

it('a switchable email has the switch; a locked one has none and says why', async () => {
  render(<StudentCommsTab />)
  const safe = await screen.findByTestId('student-email-application_received')
  expect(within(safe).getByRole('switch').getAttribute('aria-checked')).toBe('true')
  const locked = screen.getByTestId('student-email-declined')
  expect(within(locked).queryByRole('switch')).toBeNull()
  expect(within(locked).getByText(`${P}.lock.decision`)).toBeTruthy()
  expect(within(locked).getByRole('img', { name: `${P}.locked` })).toBeTruthy()
  expect(within(screen.getByTestId('student-email-interview_reminders')).getByRole('switch')
    .getAttribute('aria-checked')).toBe('false')
})

it('switching posts the key and the new state, and a refusal puts the switch back', async () => {
  render(<StudentCommsTab />)
  const safe = await screen.findByTestId('student-email-application_received')
  fireEvent.click(within(safe).getByRole('switch'))
  await waitFor(() => expect(mockApi.setStudentEmailSwitch).toHaveBeenCalledWith(
    'application_received', false, undefined, { token: 'tok' }))
  mockApi.setStudentEmailSwitch.mockRejectedValueOnce(new Error('400'))
  fireEvent.click(within(screen.getByTestId('student-email-interview_reminders')).getByRole('switch'))
  expect(await screen.findByText(`${P}.switchFailed`)).toBeTruthy()
  expect(within(screen.getByTestId('student-email-interview_reminders')).getByRole('switch')
    .getAttribute('aria-checked')).toBe('false')
})

it('says when the platform holds an email back, and when it was last sent', async () => {
  render(<StudentCommsTab />)
  expect(await screen.findByTestId('student-email-held-results_due')).toBeTruthy()
  expect(screen.queryByTestId('student-email-held-application_received')).toBeNull()
  expect(within(screen.getByTestId('student-email-application_received')).getByText(/lastSent/)).toBeTruthy()
  expect(within(screen.getByTestId('student-email-declined')).getByText(`${P}.neverSent`)).toBeTruthy()
  expect(within(screen.getByTestId('student-email-verify_email')).getByText(`${P}.notTracked`)).toBeTruthy()
  expect((screen.getByTestId('student-comms-switch')).textContent).toBe(`${P}.off`)
})

it('the worded email: one chip per language, then a tab per language that saves and resets', async () => {
  render(<StudentCommsTab />)
  const chips = await screen.findByTestId('student-email-chips-results_due')
  expect(Array.from(chips.children).map((c) => c.getAttribute('data-customised'))).toEqual(['false', 'true', 'false'])
  const li = screen.getByTestId('student-email-results_due')
  fireEvent.click(within(li).getByText(`${P}.edit`))
  fireEvent.click(within(li).getByTestId('student-email-tab-results_due.ta'))
  fireEvent.change(within(li).getAllByRole('textbox')[0], { target: { value: 'A reminder' } })
  fireEvent.click(within(li).getByText('admin.sources.save'))
  await waitFor(() => expect(mockApi.saveStudentEmail).toHaveBeenCalledWith(
    expect.objectContaining({ kind: 'results_due', language: 'ta', subject: 'A reminder' }), undefined, { token: 'tok' }))
  fireEvent.click(within(li).getByText(`${P}.edit`))
  fireEvent.click(within(li).getByTestId('student-email-tab-results_due.ms'))
  fireEvent.click(within(li).getByText(`${P}.reset`))
  await waitFor(() => expect(mockApi.saveStudentEmail).toHaveBeenLastCalledWith(
    { kind: 'results_due', language: 'ms', reset: true }, undefined, { token: 'tok' }))
})

it('shows code-owned wording read-only per language, and links the partner notice to Sources', async () => {
  render(<StudentCommsTab />)
  const li = await screen.findByTestId('student-email-application_received')
  fireEvent.click(within(li).getByText(`${P}.showWording`))
  expect(within(li).getByText('Dear {name}')).toBeTruthy()
  fireEvent.click(within(li).getByTestId('student-email-tab-application_received.ms'))
  expect(within(li).getByText('Salam {name}')).toBeTruthy()
  expect(within(li).queryByRole('textbox')).toBeNull()
  expect(within(screen.getByTestId('student-email-declined')).getByText(`${P}.builtInCode`)).toBeTruthy()
  const partner = screen.getByTestId('student-email-partner_access')
  expect(within(partner).getByText(`${P}.manageOnSources`).closest('a')?.getAttribute('href')).toBe('/admin/sources')
  expect(within(partner).queryByRole('switch')).toBeNull()
})

it('a super with several organisations chooses one, sent as org', async () => {
  mockApi.getStudentEmails
    .mockRejectedValueOnce(Object.assign(new Error('x'), { body: { code: 'organisation_required', organisations: ['alpha', 'beta'] } }))
    .mockResolvedValueOnce(PAYLOAD({ enabled: true }))
  render(<StudentCommsTab />)
  fireEvent.click(await screen.findByText('beta'))
  expect((await screen.findByTestId('student-comms-switch')).textContent).toBe(`${P}.on`)
  expect(mockApi.getStudentEmails).toHaveBeenLastCalledWith('beta', { token: 'tok' })
})
