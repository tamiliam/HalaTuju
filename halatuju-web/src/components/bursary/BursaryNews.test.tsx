/**
 * @jest-environment jsdom
 *
 * Her News tab on My Bursary (student maintenance S8; the StudentNews board). Pinned: the server's order is
 * drawn as it comes; "Pinned", "New" and "edited" marks; web addresses become links and nothing else is
 * markup; opening the tab sends ONLY the new ones to `news/read/` and hands the page the unread count back.
 */
import { render, screen, waitFor } from '@testing-library/react'
import BursaryNews, { linkify } from './BursaryNews'
import * as api from '@/lib/api/bursaryNews'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
jest.mock('@/lib/api/bursaryNews')
const mockApi = api as jest.Mocked<typeof api>
const P = 'bursaryTabs.news'

const item = (over: Partial<api.NewsItem>): api.NewsItem => ({
  id: 1, title: 'Results are due', body: 'Upload your slip.', pinned: false, published_at: '2026-11-01T02:00:00Z',
  edited_at: null, new: false, ...over,
})

beforeEach(() => jest.clearAllMocks())

it('draws pinned, new and edited marks and marks only the new ones read', async () => {
  mockApi.getBursaryNews.mockResolvedValue({ organisation: 'BrightPath', announcements: [
    item({ id: 3, pinned: true, new: true }), item({ id: 2, new: true, body: 'Join: https://meet.example/x.' }),
    item({ id: 1, edited_at: '2026-11-01T05:00:00Z' })] })
  mockApi.markNewsRead.mockResolvedValue({ marked: 2, unread: 0 })
  const onRead = jest.fn()
  render(<BursaryNews token="tok" onRead={onRead} />)
  const pinned = await screen.findByTestId('news-3')
  expect(pinned.textContent).toContain(`${P}.pinned`)
  expect(pinned.textContent).toContain(`${P}.new`)
  expect(screen.getByTestId('news-1').textContent).toContain(`${P}.edited`)
  expect(screen.getByTestId('news-1').textContent).not.toContain(`${P}.new`)
  expect(screen.getByTestId('news-fresh').textContent).toContain(`${P}.fresh`)
  const link = screen.getByTestId('news-2').querySelector('a')!
  expect(link.getAttribute('href')).toBe('https://meet.example/x')
  expect(link.getAttribute('rel')).toBe('noopener noreferrer')
  await waitFor(() => expect(onRead).toHaveBeenCalledWith(0))
  expect(mockApi.markNewsRead).toHaveBeenCalledWith([3, 2], { token: 'tok' })
})

it('sends nothing when nothing is new, and says when there is no news', async () => {
  mockApi.getBursaryNews.mockResolvedValue({ organisation: 'B', announcements: [item({})] })
  const { unmount } = render(<BursaryNews token="tok" />)
  await screen.findByTestId('news-1')
  expect(mockApi.markNewsRead).not.toHaveBeenCalled()
  unmount()
  mockApi.getBursaryNews.mockResolvedValue({ organisation: 'B', announcements: [] })
  render(<BursaryNews token="tok" />)
  expect((await screen.findByTestId('news-empty')).textContent).toBe(`${P}.empty`)
})

it('links only web addresses, never markup', () => {
  render(<p data-testid="x">{linkify('See www.example.org, or <b>bold</b>')}</p>)
  const p = screen.getByTestId('x')
  expect(p.querySelector('a')!.getAttribute('href')).toBe('https://www.example.org')
  expect(p.querySelector('b')).toBeNull()
  expect(p.textContent).toBe('See www.example.org, or <b>bold</b>')
})
