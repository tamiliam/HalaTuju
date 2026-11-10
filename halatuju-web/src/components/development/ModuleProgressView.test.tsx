/**
 * @jest-environment jsdom
 *
 * One module's Progress (student maintenance S10; the ModuleProgress board), rendered. Pinned: the four tabs with
 * the server's counts (To review first), lessons read x of y, the mentor, "Late"; "Read" opens the reflection and
 * "Mark reviewed" sends the comment; the Remind button only where `can_remind`, and a short reason instead of it
 * while the module email is switched off; the roles outside super / org_admin / admin call nothing.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import * as api from '@/lib/admin-api/development'
import ModuleProgressView from './ModuleProgressView'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k) }),
}))
let mockRole: { role: string; permissions?: string[]; mentoring?: boolean } = { role: 'org_admin' }
jest.mock('@/lib/adminAuthCore', () => ({ useAdminAuth: () => ({ token: 'tok', role: mockRole }) }))
jest.mock('@/lib/admin-api/development')
const mockApi = api as jest.Mocked<typeof api>
const K = 'admin.development.progress'

const MODULE = {
  id: 3, title: 'Managing your money', summary: '', status: 'published', programme: null, publish_at: null,
  due_on: '2026-11-30', task_kind: 'reflection', task_prompt: 'Budget?', lessons: [], audience_count: 3,
  started_count: 2, done_count: 1, to_review_count: 1, email_on_publish: false, remind: true, published_emailed_at: null,
  reminded_at: null, author: { email: '', name: '', role: '' }, created_at: '2026-11-01T00:00:00Z', locked: true,
  can_delete: false, can_archive: true, can_restore: false,
} as api.ModuleRow
const base = (over: Partial<api.ProgressRow>): api.ProgressRow => ({
  application_id: 1, name: 'NUR AISYAH', mentor: 'Ravi K.', bucket: 'done', to_review: true, read: 3, lessons: 3,
  started_at: '2026-11-02T00:00:00Z', task_sent_at: '2026-11-12T00:00:00Z', task_text: 'Cook three days a week.',
  task_file: null, reviewed_at: null, reviewed_by: '', review_comment: '', late: false, ...over,
})
const payload = (over: Partial<api.ModuleProgress> = {}): api.ModuleProgress => ({
  module: MODULE, email_switch_on: true, can_remind: true,
  rows: [base({}), base({ application_id: 2, name: 'THIVYA', bucket: 'in_progress', to_review: false, read: 1,
    task_sent_at: null, task_text: '', mentor: '', late: true }),
  base({ application_id: 4, name: 'KAVI', bucket: 'not_started', to_review: false, read: 0, task_sent_at: null,
    task_text: '', started_at: null })],
  counts: { to_review: 1, done: 1, in_progress: 1, not_started: 1 }, ...over,
})

beforeEach(() => { jest.clearAllMocks(); mockRole = { role: 'org_admin' } })

it('shows To review first, then each tab with lessons, mentor and Late', async () => {
  mockApi.getModuleProgress.mockResolvedValue(payload())
  render(<ModuleProgressView id={3} programme="flag" />)
  const first = await screen.findByTestId('progress-row-1')
  expect(first.textContent).toContain(`${K}.lessonsOf {"read":"3","count":"3"}`)
  expect(first.textContent).toContain('Ravi K.')
  expect(screen.queryByTestId('progress-row-2')).toBeNull()
  fireEvent.click(screen.getByRole('tab', { name: new RegExp(`${K}.tab.in_progress`) }))
  expect(screen.getByTestId('late-2')).toBeTruthy()
  expect(screen.queryByTestId('read-2')).toBeNull()
})

it('sprint S1: a name links to the file only for a reader of every file, never a mentor without `scholars`', async () => {
  mockApi.getModuleProgress.mockResolvedValue(payload())
  const { unmount } = render(<ModuleProgressView id={3} />)
  await screen.findByTestId('progress-row-1')
  expect(screen.getByRole('link', { name: 'NUR AISYAH' }).getAttribute('href')).toBe('/admin/scholars/1')
  unmount()
  mockRole = { role: 'admin', permissions: ['see_all'], mentoring: true }
  render(<ModuleProgressView id={3} />)
  await screen.findByTestId('progress-row-1')
  expect(screen.queryByRole('link', { name: 'NUR AISYAH' })).toBeNull()
  expect(screen.getByTestId('progress-row-1').textContent).toContain('NUR AISYAH')
})

it('reads a reflection and marks it reviewed with a comment', async () => {
  mockApi.getModuleProgress.mockResolvedValue(payload())
  mockApi.reviewTask.mockResolvedValue({ rows: [base({ to_review: false, reviewed_at: '2026-11-13T00:00:00Z',
    reviewed_by: 'siti@example.org', review_comment: 'Good plan.' })],
  counts: { to_review: 0, done: 1, in_progress: 0, not_started: 0 }, can_remind: false })
  render(<ModuleProgressView id={3} />)
  fireEvent.click(await screen.findByTestId('read-1'))
  expect(screen.getByTestId('review-1').textContent).toContain('Cook three days a week.')
  fireEvent.change(screen.getByTestId('review-comment'), { target: { value: ' Good plan. ' } })
  fireEvent.click(screen.getByTestId('review-save'))
  await waitFor(() => expect(mockApi.reviewTask).toHaveBeenCalledWith(3, 1, 'Good plan.', { token: 'tok' }))
  expect(await screen.findByText(`${K}.saved`)).toBeTruthy()
})

it('offers Remind only when the server says so, and says why when the email is off', async () => {
  mockApi.getModuleProgress.mockResolvedValue(payload({ email_switch_on: false }))
  const { unmount } = render(<ModuleProgressView id={3} />)
  expect(await screen.findByTestId('module-remind-off')).toBeTruthy()
  expect(screen.queryByTestId('module-remind')).toBeNull()
  unmount()
  mockApi.getModuleProgress.mockResolvedValue(payload({ can_remind: false }))
  render(<ModuleProgressView id={3} />)
  await screen.findByTestId('module-progress')
  expect(screen.queryByTestId('module-remind')).toBeNull()
})

it('refuses the roles outside super, org_admin and admin and calls nothing', () => {
  mockRole = { role: 'reviewer' }
  render(<ModuleProgressView id={3} />)
  expect(screen.getByText('apiErrors.superAdminRequired')).toBeTruthy()
  expect(mockApi.getModuleProgress).not.toHaveBeenCalled()
})
