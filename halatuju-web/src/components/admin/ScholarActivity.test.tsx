/**
 * @jest-environment jsdom
 *
 * The scholar file's activity log (student maintenance Sprint 2; reshaped in sprint P1, 2026-11-09).
 * Pinned:
 *  * a system entry reads as a translated sentence built from its event code — never raw meta;
 *  * WHO (P1-d): a person's name and photo, initials without one, the System icon only for a fully
 *    automatic row, and never an email for a known person;
 *  * ORDER (P1-b): oldest at the top, newest at the bottom, the box after the list; "Show older (n)"
 *    fetches the next page;
 *  * the Activity tab's All · Notes · System filter asks the SERVER (P1-f); the side panel has none;
 *  * the composer (P1-a, P1-g): one line until focused, Esc on an empty box closes it, Save posts a
 *    NOTE with the staff-only flag (the site Toggle — a `role="switch"`, never a checkbox).
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import ScholarActivity from './ScholarActivity'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
const mockToast = jest.fn()
jest.mock('@/components/ToastContext', () => ({ useToast: () => ({ showToast: mockToast }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const SYSTEM: api.ScholarActivity = {
  id: 1, kind: 'system', event: 'substate_changed', body: '',
  meta: { old: 'on_track', new: 'on_hold', excluded_from_runs: [] },
  actor_email: 'officer@example.org', internal: true, created_at: '2026-10-02T00:00:00Z',
  actor: { name: 'Gopal Officer', photo_url: null, kind: 'staff' },
}
const NOTE: api.ScholarActivity = {
  id: 2, kind: 'call', event: '', body: 'Talked through a study plan.', meta: {},
  actor_email: 'farah@example.org', internal: true, created_at: '2026-10-27T00:00:00Z',
  actor: { name: 'Farah Officer', photo_url: 'https://signed.example.org/farah.webp', kind: 'staff' },
}
const AUTO: api.ScholarActivity = {
  id: 3, kind: 'system', event: 'results_overdue', body: '', meta: { due_on: '2026-12-15', term_index: 2 },
  actor_email: '', internal: true, created_at: '2027-01-20T00:00:00Z', actor: null,
}
const COUNTS = { all: 2, notes: 1, system: 1 }
const page = (results: api.ScholarActivity[], count = results.length) =>
  ({ count, page: 1, page_size: 20, counts: COUNTS, results })

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getScholarActivity.mockResolvedValue(page([NOTE, SYSTEM]))     // newest first, as served
  mockApi.addScholarActivity.mockResolvedValue({ ...NOTE, kind: 'note' })
})

const rows = () => screen.getAllByTestId('activity-row')

it('reads a system row as a sentence and an officer row as its own words', async () => {
  render(<ScholarActivity id={7} token="tok" />)
  expect(await screen.findByText('Talked through a study plan.')).toBeTruthy()
  expect(screen.getByText(
    'admin.scholars.event.substate_changed|{"from":"admin.maintenance.substate.on_track","to":"admin.maintenance.substate.on_hold"}',
  )).toBeTruthy()
  expect(screen.queryByText(/excluded_from_runs/)).toBeNull()
  expect(rows()).toHaveLength(2)
})

it('shows oldest at the top and newest at the bottom, with the box after the list', async () => {
  render(<ScholarActivity id={7} token="tok" />)
  await screen.findByText('Talked through a study plan.')
  expect(rows().map((r) => within(r).getByTestId('activity-who').textContent))
    .toEqual(['Gopal Officer', 'Farah Officer'])
  const composer = screen.getByTestId('activity-composer')
  expect(rows()[1].compareDocumentPosition(composer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})

it('names the person with their photo, or initials without one, and never prints their email', async () => {
  render(<ScholarActivity id={7} token="tok" />)
  await screen.findByText('Talked through a study plan.')
  const [system, call] = rows()
  expect((within(call).getByTestId('staff-avatar-photo') as HTMLImageElement).src)
    .toBe('https://signed.example.org/farah.webp')
  expect(within(system).getByTestId('staff-avatar-initials').textContent).toBe('GO')
  expect(within(system).queryByTestId('activity-system-icon')).toBeNull()   // a person had a hand in it
  expect(document.body.textContent).not.toContain('@example.org')
})

it('a fully automatic row shows the System icon; a plain note shows no kind word, a call does', async () => {
  const plain = { ...NOTE, id: 4, kind: 'note' as const, body: 'Plain note.' }
  mockApi.getScholarActivity.mockResolvedValue(page([plain, NOTE, AUTO]))
  render(<ScholarActivity id={7} token="tok" />)
  await screen.findByText('Plain note.')
  const [auto, call, note] = rows()
  expect(within(auto).getByTestId('activity-system-icon')).toBeTruthy()
  expect(within(auto).getByTestId('activity-who').textContent).toBe('admin.scholars.activity.bySystem')
  expect(auto.textContent).not.toContain('2026-12-15')                     // a date, never raw ISO (S4b L10)
  expect(call.textContent).toContain('admin.scholars.activity.kind.call')
  expect(note.textContent).not.toContain('admin.scholars.activity.kind.')
})

it('a mentor the viewer may not know, and the scholar without a name, get their own words', async () => {
  const mentor = { ...NOTE, id: 5, actor_email: '', actor: { name: '', photo_url: null, kind: 'mentor' as const } }
  const scholar = { ...SYSTEM, id: 6, event: 'letter_acknowledged', meta: { subject: 'Warning' }, actor_email: '',
    actor: { name: '', photo_url: null, kind: 'scholar' as const } }
  mockApi.getScholarActivity.mockResolvedValue(page([mentor, scholar]))
  render(<ScholarActivity id={7} token="tok" />)
  await waitFor(() => expect(rows()).toHaveLength(2))
  expect(rows().map((r) => within(r).getByTestId('activity-who').textContent))
    .toEqual(['admin.scholars.activity.theScholar', 'admin.scholars.activity.aMentor'])
})

it('shows the time relative, with the exact time for a hover and a screen reader', async () => {
  render(<ScholarActivity id={7} token="tok" />)
  await screen.findByText('Talked through a study plan.')
  const time = rows()[1].querySelector('time')!
  expect(time.getAttribute('dateTime')).toBe('2026-10-27T00:00:00Z')
  expect(time.getAttribute('title')).toMatch(/^\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}$/)
  expect(time.querySelector('.sr-only')!.textContent).toBe(time.getAttribute('title'))
})

it('"Show older (n)" loads the next page above, once per page', async () => {
  const older: api.ScholarActivity = { ...SYSTEM, id: 9, created_at: '2026-09-01T00:00:00Z' }
  mockApi.getScholarActivity.mockResolvedValueOnce(page([NOTE, SYSTEM], 3))
    .mockResolvedValueOnce({ ...page([older], 3), page: 2 })
  render(<ScholarActivity id={7} token="tok" compact />)
  const button = await screen.findByTestId('activity-older')
  expect(button.textContent).toBe('admin.scholars.activity.showOlder|{"n":"1"}')
  expect(mockApi.getScholarActivity).toHaveBeenLastCalledWith(7, { token: 'tok', page_size: 6, show: 'all' })
  fireEvent.click(button)
  await waitFor(() => expect(rows()).toHaveLength(3))
  expect(mockApi.getScholarActivity).toHaveBeenLastCalledWith(7, { token: 'tok', page: 2, page_size: 6, show: 'all' })
  expect(rows()[0].contains(screen.getAllByText(/substate_changed/)[0])).toBe(true)
  expect(screen.queryByTestId('activity-older')).toBeNull()
})

it('the Activity tab filters on the server; the side panel has no filter', async () => {
  const { unmount } = render(<ScholarActivity id={7} token="tok" compact />)
  await screen.findByText('Talked through a study plan.')
  expect(screen.queryByRole('button', { name: /activity\.filter\./ })).toBeNull()
  unmount()
  render(<ScholarActivity id={7} token="tok" />)
  await screen.findByText('Talked through a study plan.')
  const notes = screen.getByRole('button', { name: 'admin.scholars.activity.filter.notes|{"n":"1"}' })
  expect(screen.getByRole('button', { name: 'admin.scholars.activity.filter.all|{"n":"2"}' })
    .getAttribute('aria-pressed')).toBe('true')
  mockApi.getScholarActivity.mockResolvedValue(page([NOTE]))
  fireEvent.click(notes)
  await waitFor(() => expect(rows()).toHaveLength(1))
  expect(mockApi.getScholarActivity).toHaveBeenLastCalledWith(7, { token: 'tok', page_size: 20, show: 'notes' })
  expect(notes.getAttribute('aria-pressed')).toBe('true')
  expect(screen.queryByText(/substate_changed/)).toBeNull()
})

it('the composer is one line until focused, and Esc on an empty box closes it', async () => {
  render(<ScholarActivity id={7} token="tok" />)
  await screen.findByText('Talked through a study plan.')
  const box = screen.getByRole('textbox', { name: 'admin.scholars.activity.addLabel' }) as HTMLTextAreaElement
  expect(box.rows).toBe(1)
  expect(screen.queryByRole('switch')).toBeNull()
  fireEvent.focus(box)
  expect(box.rows).toBe(3)
  expect(screen.getByRole('switch', { name: 'admin.scholars.activity.staffOnly' })).toBeTruthy()
  fireEvent.keyDown(box, { key: 'Escape' })
  expect(box.rows).toBe(1)
  fireEvent.focus(box)
  fireEvent.change(box, { target: { value: 'Half a thought' } })
  fireEvent.keyDown(box, { key: 'Escape' })
  expect(box.rows).toBe(3)                                                  // never throws words away
  fireEvent.click(screen.getByRole('button', { name: 'admin.scholars.activity.cancel' }))
  expect(box.rows).toBe(1)
  expect(box.value).toBe('')
})

it('Save posts a note with the staff-only flag, then re-reads and closes the box', async () => {
  render(<ScholarActivity id={7} token="tok" />)
  await screen.findByText('Talked through a study plan.')
  const box = screen.getByPlaceholderText('admin.scholars.activity.placeholder') as HTMLTextAreaElement
  fireEvent.focus(box)
  expect((screen.getByRole('button', { name: 'admin.scholars.activity.save' }) as HTMLButtonElement).disabled).toBe(true)
  fireEvent.change(box, { target: { value: 'Met at the campus.' } })
  fireEvent.click(screen.getByRole('switch', { name: 'admin.scholars.activity.staffOnly' }))
  fireEvent.click(screen.getByRole('button', { name: 'admin.scholars.activity.save' }))
  await waitFor(() => expect(mockApi.addScholarActivity).toHaveBeenCalledWith(
    7, { kind: 'note', body: 'Met at the campus.', internal: true }, { token: 'tok' }))
  await waitFor(() => expect(mockApi.getScholarActivity).toHaveBeenCalledTimes(2))
  expect(mockToast).toHaveBeenCalledWith('admin.scholars.activity.saved', 'success')
  await waitFor(() => expect(box.rows).toBe(1))
  expect(box.value).toBe('')
})

it('a closed file has no composer', async () => {
  render(<ScholarActivity id={7} token="tok" readOnly />)
  await screen.findByText('Talked through a study plan.')
  expect(screen.getByTestId('activity-read-only')).toBeTruthy()
  expect(screen.queryByTestId('activity-composer')).toBeNull()
})

it('words the three letter events with the subject of each letter (S6b)', async () => {
  const letterRow = (id: number, event: string): api.ScholarActivity => ({ ...SYSTEM, id, event, meta: { subject: 'Warning (clause 5)' } })
  mockApi.getScholarActivity.mockResolvedValue(page([
    letterRow(11, 'letter_issued'), letterRow(12, 'letter_withdrawn'), letterRow(13, 'letter_acknowledged')]))
  render(<ScholarActivity id={7} token="tok" />)
  for (const event of ['letter_issued', 'letter_withdrawn', 'letter_acknowledged']) {
    expect(await screen.findByText(`admin.scholars.event.${event}|{"subject":"Warning (clause 5)"}`)).toBeTruthy()
  }
})
