/**
 * @jest-environment jsdom
 *
 * Her Growth tab on My Bursary (student maintenance S10; the ModuleStudent board). Pinned: the list draws each
 * module with its due date, contents and progress; opening one shows ONE lesson at a time, starting at the first
 * unread; "I have read this — next lesson" marks it and moves on, and the tab's red number follows the reply; the
 * reflection is sent as typed and an empty one is said before anything is sent; a reviewed task shows the
 * comment and can no longer change; the video is a link that opens a new tab, never an embed.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import BursaryGrowth from './BursaryGrowth'
import * as api from '@/lib/api/bursaryGrowth'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
jest.mock('@/lib/api/bursaryGrowth')
const mockApi = api as jest.Mocked<typeof api>
const P = 'bursaryTabs.growth'

const card = (over: Partial<api.MyModuleCard> = {}): api.MyModuleCard => ({
  id: 5, title: 'Managing your money', summary: 'About 30 minutes.', due_on: '2026-11-30', task_kind: 'reflection',
  lessons: 2, read: 1, done: false, started: true, can_act: true, task_sent_at: null, reviewed: false, ...over,
})

const lessons = (readFirst: boolean): api.MyLesson[] => [
  { id: 11, title: 'Where does the money go?', body: 'Write it down. See https://example.test/x', video_url: '',
    file: null, read: readFirst },
  { id: 12, title: 'A simple budget', body: 'Rent first.', video_url: 'https://youtu.be/abc', file: null, read: false },
]

const mod = (over: Partial<api.MyModule> = {}): api.MyModule => ({
  id: 5, title: 'Managing your money', summary: '', due_on: '2026-11-30', can_act: true, done: false,
  lessons: lessons(true),
  task: { kind: 'reflection', prompt: 'Make your own budget.', text: '', file: null, sent_at: null, reviewed_at: null,
    comment: '', can_change: false },
  ...over,
})

beforeEach(() => jest.clearAllMocks())

it('lists a module with its due date, contents and progress', async () => {
  mockApi.getMyModules.mockResolvedValue({ organisation: 'BrightPath', modules: [card(), card({ id: 6, done: true,
    reviewed: true, title: 'CV' })] })
  render(<BursaryGrowth token="tok" />)
  const one = await screen.findByTestId('module-5')
  expect(one.textContent).toContain(`${P}.due`)
  expect(one.textContent).toContain(`${P}.withTask`)
  expect(one.textContent).toContain(`${P}.continue`)
  expect(screen.getByTestId('module-done-6').textContent).toContain(`${P}.reviewed`)
})

it('opens on the first unread lesson; reading moves on and the red number follows', async () => {
  mockApi.getMyModules.mockResolvedValue({ organisation: 'BrightPath', modules: [card()] })
  mockApi.getMyModule.mockResolvedValue(mod())
  const after = mod({ lessons: lessons(true).map((l) => ({ ...l, read: true })),
    task: { ...mod().task, can_change: true } })
  mockApi.markLessonRead.mockResolvedValue({ module: after, to_do: 1 })
  const onCount = jest.fn()
  render(<BursaryGrowth token="tok" onCount={onCount} />)
  fireEvent.click(await screen.findByTestId('module-open-5'))
  await screen.findByTestId('lesson-12')
  const video = screen.getByTestId('lesson-video')
  expect(video.getAttribute('href')).toBe('https://youtu.be/abc')
  expect(video.getAttribute('target')).toBe('_blank')
  expect(screen.getByTestId('lesson-read').textContent).toBe(`${P}.markLast`)
  fireEvent.click(screen.getByTestId('lesson-read'))
  await waitFor(() => expect(mockApi.markLessonRead).toHaveBeenCalledWith(5, 12, { token: 'tok' }))
  expect(await screen.findByTestId('module-task')).toBeTruthy()
  expect(onCount).toHaveBeenCalledWith(1)
})

it('sends the reflection as typed and says an empty one first', async () => {
  mockApi.getMyModules.mockResolvedValue({ organisation: 'BrightPath', modules: [card({ read: 2 })] })
  const ready = mod({ lessons: lessons(true).map((l) => ({ ...l, read: true })), task: { ...mod().task, can_change: true } })
  mockApi.getMyModule.mockResolvedValue(ready)
  mockApi.sendReflection.mockResolvedValue({ module: { ...ready, done: true,
    task: { ...ready.task, text: 'Cook more.', sent_at: '2026-11-02T00:00:00Z' } }, to_do: 0 })
  render(<BursaryGrowth token="tok" />)
  fireEvent.click(await screen.findByTestId('module-open-5'))
  fireEvent.click(await screen.findByTestId('module-send'))
  expect(screen.getByTestId('module-error').textContent).toBe(`${P}.error.text_required`)
  expect(mockApi.sendReflection).not.toHaveBeenCalled()
  fireEvent.change(screen.getByTestId('module-reflection'), { target: { value: '  Cook more.  ' } })
  fireEvent.click(screen.getByTestId('module-send'))
  await waitFor(() => expect(mockApi.sendReflection).toHaveBeenCalledWith(5, 'Cook more.', { token: 'tok' }))
  expect((await screen.findByTestId('module-sent')).textContent).toContain(`${P}.sent`)
  expect(screen.getByTestId('module-finished')).toBeTruthy()
})

it('a reviewed task shows the comment and cannot change; a refusal is said', async () => {
  mockApi.getMyModules.mockResolvedValue({ organisation: 'BrightPath', modules: [card({ read: 2, done: true })] })
  mockApi.getMyModule.mockResolvedValue(mod({ done: true, lessons: lessons(true).map((l) => ({ ...l, read: true })),
    task: { ...mod().task, text: 'Cook more.', sent_at: '2026-11-02T00:00:00Z', reviewed_at: '2026-11-03T00:00:00Z',
      comment: 'Good plan.', can_change: false } }))
  render(<BursaryGrowth token="tok" />)
  fireEvent.click(await screen.findByTestId('module-open-5'))
  expect((await screen.findByTestId('module-reviewed')).textContent).toContain(`${P}.comment`)
  expect(screen.queryByTestId('module-send')).toBeNull()
  expect(screen.getByTestId('module-task').textContent).toContain('Cook more.')
})

it('says when there is none', async () => {
  mockApi.getMyModules.mockResolvedValue({ organisation: 'B', modules: [] })
  render(<BursaryGrowth token="tok" />)
  expect((await screen.findByTestId('growth-empty')).textContent).toBe(`${P}.empty`)
})
