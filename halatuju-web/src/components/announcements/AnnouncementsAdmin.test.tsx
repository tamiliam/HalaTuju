/**
 * @jest-environment jsdom
 *
 * Programme → Announcements (student maintenance S8; the AnnouncementsAdmin board), rendered. Pinned: the
 * status tabs with the server's counts; each row's audience, emailed and "read N of M"; Withdraw only where
 * `can_withdraw`, Delete only where `can_delete`; the roles outside super / org_admin / admin see a refusal
 * and call nothing; a published one's edit sends only the title, message and pin; a scheduled time travels
 * as Malaysian time from a 24-hour TEXT box.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import * as api from '@/lib/admin-api'
import AnnouncementsAdmin, { emailedLabel } from './AnnouncementsAdmin'
import { mytInstant, mytParts } from './AnnouncementForm'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k) }),
}))
let mockRole: { role: string } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: mockRole }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>
const K = 'admin.announcements'

const row = (over: Partial<api.AnnouncementRow>): api.AnnouncementRow => ({
  id: 1, title: 'Results are due', body: 'Upload your slip.', status: 'published', pinned: true, programme: null,
  audience_count: 65, read_count: 41, email_requested: true, emailed_at: '2026-11-01T03:00:00Z', emailed_count: 65,
  email_switched_off: false, publish_at: null, published_at: '2026-11-01T02:00:00Z', edited_at: null,
  withdrawn_at: null, author: { email: 'siti@example.org', name: 'Siti', role: 'org_admin' },
  created_at: '2026-11-01T01:00:00Z', can_delete: false, can_withdraw: true, ...over,
})
const payload = (rows: api.AnnouncementRow[]): api.AnnouncementsPayload => ({
  organisation: { code: 'bp', name: 'BrightPath' }, announcements: rows,
  counts: {
    published: rows.filter((r) => r.status === 'published').length,
    scheduled: rows.filter((r) => r.status === 'scheduled').length,
    draft: rows.filter((r) => r.status === 'draft').length, withdrawn: 0,
  },
  audiences: [{ programme: null, name: '', count: 65 }, { programme: 'flag', name: 'Flagship', count: 40 }],
  email_switch_on: true, limits: { title: 150, body: 5000 },
})

beforeEach(() => { jest.clearAllMocks(); mockRole = { role: 'org_admin' } })

it('lists the published ones with the server counts and only the offered actions', async () => {
  mockApi.getAnnouncements.mockResolvedValue(payload([row({}),
    row({ id: 2, status: 'draft', can_delete: true, can_withdraw: false, pinned: false })]))
  render(<AnnouncementsAdmin programme="flag" />)
  const r1 = await screen.findByTestId('announcement-row-1')
  expect(mockApi.getAnnouncements).toHaveBeenCalledWith('flag', { token: 'tok' })
  expect(r1.textContent).toContain(`${K}.forAll {"count":"65"}`)
  expect(screen.getByTestId('announcement-read-1').textContent).toBe(`${K}.read {"read":"41","count":"65"}`)
  expect(screen.getByTestId('announcement-emailed-1').textContent).toBe(`${K}.emailed.sent {"count":"65"}`)
  expect(screen.getByTestId('announcement-withdraw-1')).toBeTruthy()
  expect(screen.queryByTestId('announcement-delete-1')).toBeNull()
  expect(screen.queryByTestId('announcement-row-2')).toBeNull()
  fireEvent.click(screen.getByRole('tab', { name: new RegExp(`${K}.tab.draft`) }))
  expect(screen.getByTestId('announcement-delete-2')).toBeTruthy()
  expect(screen.queryByTestId('announcement-withdraw-2')).toBeNull()
})

it('M2d E8: the table and header match Scholars - phone-only 44px taps, ground-100 dividers, bold title', async () => {
  mockApi.getAnnouncements.mockResolvedValue(payload([row({})]))
  render(<AnnouncementsAdmin programme="flag" />)
  const tr = await screen.findByTestId('announcement-row-1')
  expect(tr.parentElement?.className).toContain('divide-ground-100')
  for (const el of Array.from(tr.querySelectorAll('a, button'))) {
    expect(el.className).toContain('max-md:min-h-11')
    expect(el.className).not.toMatch(/(^|\s)min-h-11/)
  }
  const h1 = screen.getByRole('heading', { level: 1 })
  expect(h1.className).toContain('font-bold')
  expect(h1.nextElementSibling?.className).toContain('text-ground-500')
  expect(screen.getByTestId('announcement-new').className).not.toMatch(/(^|\s)min-h-11/)
})

it('refuses the roles outside super, org_admin and admin and calls nothing', () => {
  for (const r of ['reviewer', 'qc', 'finance', 'mentor', 'source_partner']) {
    mockRole = { role: r }
    const { unmount } = render(<AnnouncementsAdmin />)
    expect(screen.getByText('apiErrors.superAdminRequired')).toBeTruthy()
    unmount()
  }
  expect(mockApi.getAnnouncements).not.toHaveBeenCalled()
})

it('sends only the title, the message and the pin when a published one is edited', async () => {
  mockApi.getAnnouncements.mockResolvedValue(payload([row({})]))
  mockApi.updateAnnouncement.mockResolvedValue(row({ edited_at: '2026-11-02T00:00:00Z' }))
  render(<AnnouncementsAdmin />)
  fireEvent.click(await screen.findByTestId('announcement-edit-1'))
  expect((screen.getByTestId('announcement-audience') as HTMLSelectElement).disabled).toBe(true)
  fireEvent.change(screen.getByTestId('announcement-title'), { target: { value: 'Results moved' } })
  fireEvent.click(screen.getByTestId('announcement-save'))
  await waitFor(() => expect(mockApi.updateAnnouncement).toHaveBeenCalledWith(
    1, { title: 'Results moved', body: 'Upload your slip.', pinned: true }, { token: 'tok' }))
})

it('schedules in Malaysian time from a 24-hour text box', async () => {
  mockApi.getAnnouncements.mockResolvedValue(payload([]))
  mockApi.createAnnouncement.mockResolvedValue(row({ id: 9, status: 'scheduled' }))
  render(<AnnouncementsAdmin programme="flag" />)
  fireEvent.click(await screen.findByTestId('announcement-new'))
  fireEvent.change(screen.getByTestId('announcement-title'), { target: { value: 'Talk' } })
  fireEvent.change(screen.getByTestId('announcement-body'), { target: { value: 'At 8 pm.' } })
  fireEvent.change(screen.getByTestId('announcement-audience'), { target: { value: 'flag' } })
  fireEvent.change(screen.getByTestId('announcement-when'), { target: { value: 'later' } })
  fireEvent.change(screen.getByTestId('announcement-date'), { target: { value: '2026-11-20' } })
  fireEvent.change(screen.getByTestId('announcement-time'), { target: { value: '9:30pm' } })
  fireEvent.click(screen.getByTestId('announcement-primary'))
  expect(screen.getByTestId('announcement-error').textContent).toBe(`${K}.error.badTime`)
  fireEvent.change(screen.getByTestId('announcement-time'), { target: { value: '21:30' } })
  fireEvent.click(screen.getByTestId('announcement-primary'))
  await waitFor(() => expect(mockApi.createAnnouncement).toHaveBeenCalledWith({
    title: 'Talk', body: 'At 8 pm.', pinned: false, email: false, programme: 'flag', action: 'schedule',
    publish_at: '2026-11-20T21:30:00+08:00' }, 'flag', { token: 'tok' }))
})

it('words the email column from the server state', () => {
  const t = (k: string) => k
  expect(emailedLabel(t, row({ email_requested: false }))).toBe(`${K}.emailed.none`)
  expect(emailedLabel(t, row({ email_switched_off: true }))).toBe(`${K}.emailed.off`)
  expect(emailedLabel(t, row({ emailed_at: null }))).toBe(`${K}.emailed.pending`)
  expect(emailedLabel(t, row({ emailed_at: null, status: 'scheduled' }))).toBe(`${K}.emailed.later`)
})

it('round-trips a stored instant through the Malaysian boxes', () => {
  expect(mytParts('2026-11-20T13:30:00Z')).toEqual({ date: '2026-11-20', time: '21:30' })
  expect(mytInstant('2026-11-20', '21:30')).toBe('2026-11-20T21:30:00+08:00')
  expect(mytInstant('2026-11-20', '24:00')).toBeNull()
})
