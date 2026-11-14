/**
 * @jest-environment jsdom
 *
 * Programme → Development (student maintenance S10; the ModulesAdmin board), rendered. Pinned: the status tabs
 * with the server's counts; "N of M" done and "to review"; Archive / Put back / Delete only where the row says;
 * the roles outside super / org_admin / admin see a refusal and call nothing; a new module sends its lessons, its
 * task and a due date; a STARTED module's edit sends no task type, audience or publishing time, but does send
 * its lessons with their ids (so her reads follow them).
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import * as api from '@/lib/admin-api/development'
import DevelopmentAdmin from './DevelopmentAdmin'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k) }),
}))
let mockRole: { role: string } = { role: 'org_admin' }
jest.mock('@/lib/adminAuthCore', () => ({ useAdminAuth: () => ({ token: 'tok', role: mockRole }) }))
jest.mock('@/lib/admin-api/development')
const mockApi = api as jest.Mocked<typeof api>
const K = 'admin.development'

const L: api.LessonRow = { id: 21, title: 'Where does the money go?', body: 'Write it down.', video_url: '', file: null }
const row = (over: Partial<api.ModuleRow>): api.ModuleRow => ({
  id: 1, title: 'Managing your money', summary: 'About 30 minutes.', status: 'published', programme: null,
  publish_at: '2026-11-01T01:00:00Z', due_on: '2026-11-30', task_kind: 'reflection', task_prompt: 'Budget?',
  lessons: [L], audience_count: 65, started_count: 30, done_count: 21, to_review_count: 4, email_on_publish: false,
  remind: false, published_emailed_at: null, reminded_at: null,
  author: { email: 'siti@example.org', name: 'Siti', role: 'org_admin' }, created_at: '2026-11-01T00:00:00Z',
  locked: true, can_delete: false, can_archive: true, can_restore: false, ...over,
})
const payload = (rows: api.ModuleRow[]): api.ModulesPayload => ({
  organisation: { code: 'bp', name: 'BrightPath' }, modules: rows,
  counts: {
    published: rows.filter((r) => r.status === 'published').length,
    scheduled: rows.filter((r) => r.status === 'scheduled').length,
    draft: rows.filter((r) => r.status === 'draft').length, archived: rows.filter((r) => r.status === 'archived').length,
  },
  audiences: [{ programme: null, name: '', count: 65 }, { programme: 'flag', name: 'Flagship', count: 40 }],
  email_switch_on: true,
  limits: { title: 150, summary: 500, lesson_title: 150, lesson_body: 10000, lessons: 20, prompt: 1000,
    file_bytes: 10485760 },
})

beforeEach(() => { jest.clearAllMocks(); mockRole = { role: 'org_admin' } })

it('lists the published ones with the server counts and only the offered actions', async () => {
  mockApi.getModules.mockResolvedValue(payload([row({}),
    row({ id: 2, status: 'draft', can_archive: false, can_delete: true, locked: false, done_count: 0 })]))
  render(<DevelopmentAdmin programme="flag" />)
  await screen.findByTestId('module-row-1')
  expect(mockApi.getModules).toHaveBeenCalledWith('flag', { token: 'tok' })
  expect(screen.getByTestId('module-done-1').textContent).toContain(`${K}.doneOf {"n":"21","count":"65"}`)
  expect(screen.getByTestId('module-done-1').textContent).toContain(`${K}.toReview`)
  expect(screen.getByTestId('module-archive-1')).toBeTruthy()
  expect(screen.queryByTestId('module-delete-1')).toBeNull()
  expect(screen.getByTestId('module-progress-1').getAttribute('href')).toBe('/admin/programme/development/1?programme=flag')
  fireEvent.click(screen.getByRole('tab', { name: new RegExp(`${K}.tab.draft`) }))
  expect(screen.getByTestId('module-delete-2')).toBeTruthy()
  expect(screen.queryByTestId('module-progress-2')).toBeNull()
})

it('M2d E8: the table and header match Scholars - phone-only 44px taps, ground-100 dividers, bold title', async () => {
  mockApi.getModules.mockResolvedValue(payload([row({})]))
  render(<DevelopmentAdmin programme="flag" />)
  const tr = await screen.findByTestId('module-row-1')
  expect(tr.parentElement?.className).toContain('divide-ground-100')
  for (const el of Array.from(tr.querySelectorAll('a, button'))) {
    expect(el.className).toContain('max-md:min-h-11')
    expect(el.className).not.toMatch(/(^|\s)min-h-11/)
  }
  const h1 = screen.getByRole('heading', { level: 1 })
  expect(h1.className).toContain('font-bold')
  expect(h1.nextElementSibling?.className).toContain('text-ground-500')
  expect(screen.getByTestId('module-new').className).not.toMatch(/(^|\s)min-h-11/)
})

it('refuses the roles outside super, org_admin and admin and calls nothing', () => {
  for (const r of ['reviewer', 'qc', 'finance', 'mentor', 'source_partner']) {
    mockRole = { role: r }
    const { unmount } = render(<DevelopmentAdmin />)
    expect(screen.getByText('apiErrors.superAdminRequired')).toBeTruthy()
    unmount()
  }
  expect(mockApi.getModules).not.toHaveBeenCalled()
})

it('creates one with its lessons, task and due date', async () => {
  mockApi.getModules.mockResolvedValue(payload([]))
  mockApi.createModule.mockResolvedValue(row({ id: 9 }))
  render(<DevelopmentAdmin programme="flag" />)
  fireEvent.click(await screen.findByTestId('module-new'))
  fireEvent.change(screen.getByTestId('module-title'), { target: { value: 'Writing your first CV' } })
  fireEvent.change(screen.getByTestId('lesson-title-0'), { target: { value: 'What a CV is' } })
  fireEvent.change(screen.getByTestId('lesson-body-0'), { target: { value: 'One page.' } })
  fireEvent.change(screen.getByTestId('lesson-video-0'), { target: { value: ' https://youtu.be/x ' } })
  expect(screen.getByText(`${K}.form.fileSaveFirst`)).toBeTruthy()   // a file needs a saved lesson
  fireEvent.click(screen.getByTestId('module-task-upload'))
  fireEvent.change(screen.getByTestId('module-prompt'), { target: { value: 'Upload your CV' } })
  fireEvent.change(screen.getByTestId('module-due'), { target: { value: '2026-12-01' } })
  fireEvent.click(screen.getByTestId('module-primary'))
  await waitFor(() => expect(mockApi.createModule).toHaveBeenCalled())
  const [body, programme] = mockApi.createModule.mock.calls[0]
  expect(programme).toBe('flag')
  expect(body).toMatchObject({ title: 'Writing your first CV', task_kind: 'upload', task_prompt: 'Upload your CV',
    due_on: '2026-12-01', action: 'publish', programme: null,
    lessons: [{ title: 'What a CV is', body: 'One page.', video_url: 'https://youtu.be/x' }] })
  expect(body.publish_at).toBeUndefined()
})

it('a started module edit sends its lessons with ids, never the task type, audience or time', async () => {
  mockApi.getModules.mockResolvedValue(payload([row({})]))
  mockApi.updateModule.mockResolvedValue(row({}))
  render(<DevelopmentAdmin />)
  fireEvent.click(await screen.findByTestId('module-edit-1'))
  expect((screen.getByTestId('module-task-reflection') as HTMLButtonElement).disabled).toBe(false)
  expect((screen.getByTestId('module-task-upload') as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(screen.getByTestId('module-add-lesson'))
  fireEvent.change(screen.getByTestId('lesson-title-1'), { target: { value: 'One more' } })
  fireEvent.click(screen.getByTestId('module-save'))
  await waitFor(() => expect(mockApi.updateModule).toHaveBeenCalled())
  const body = mockApi.updateModule.mock.calls[0][1]
  expect(body).not.toHaveProperty('task_kind')
  expect(body).not.toHaveProperty('programme')
  expect(body).not.toHaveProperty('publish_at')
  expect(body.lessons).toEqual([{ id: 21, title: L.title, body: L.body, video_url: '' },
    { title: 'One more', body: '', video_url: '' }])
})

it('says the server refusal with the lesson it names', async () => {
  mockApi.getModules.mockResolvedValue(payload([]))
  mockApi.createModule.mockRejectedValue(Object.assign(new Error('x'), { code: 'bad_video', body: { detail: 0 } }))
  render(<DevelopmentAdmin />)
  fireEvent.click(await screen.findByTestId('module-new'))
  fireEvent.click(screen.getByTestId('module-draft'))
  expect((await screen.findByTestId('module-error')).textContent).toBe(`${K}.error.bad_video ${K}.error.atLesson {"n":"1"}`)
})
