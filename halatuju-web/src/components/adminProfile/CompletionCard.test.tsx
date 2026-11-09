/**
 * @jest-environment jsdom
 *
 * Staff nudges (2026-11-08): the completion bar at the top of My Profile (the owner-approved
 * mock-up) — rendered from the SERVED `completion`, never derived.
 */
import { render, screen } from '@testing-library/react'
import CompletionCard, { ITEM_CARD } from './CompletionCard'
import type { ProfileState } from './shared'
import type { ProfileCompletion } from '@/lib/admin-api'

const t = (k: string, v?: Record<string, string>) => (v ? `${k}(${Object.values(v).join('|')})` : k)
const P = 'admin.myProfile.completion'
const state = (completion: ProfileCompletion | null) => ({ t, completion } as unknown as ProfileState)

const SIXTY: ProfileCompletion = {
  items: [{ key: 'photo', done: false }, { key: 'name', done: true }, { key: 'job_title', done: true },
          { key: 'about', done: false }, { key: 'phone', done: true }],
  done: 3, total: 5, percent: 60, important_missing: ['photo'],
}

it('shows the bar, "N of M done", a tick for each done item and a link for each missing one', () => {
  render(<CompletionCard state={state(SIXTY)} />)
  expect(screen.getByRole('heading', { name: `${P}.title(60)` })).toBeTruthy()
  expect(screen.getByText(`${P}.count(3|5)`)).toBeTruthy()
  const bar = screen.getByRole('progressbar')
  expect(bar.getAttribute('aria-valuenow')).toBe('60')
  expect((bar.firstChild as HTMLElement).style.width).toBe('60%')
  expect(screen.getByTestId('completion-done-name').textContent).toContain(`${P}.done.name`)
  expect(screen.getByRole('link', { name: `${P}.todo.photo` }).getAttribute('href')).toBe('#profile-card-you')
  expect(screen.getByRole('link', { name: `${P}.todo.about` }).getAttribute('href')).toBe('#profile-card-you')
  expect(screen.queryByTestId('completion-todo-name')).toBeNull()
  expect(screen.getByText(`${P}.note`)).toBeTruthy()
})

it('every item scrolls to a card the page has', () => {
  const cards = new Set(['you', 'contact', 'qualifications', 'address', 'mentoring'])
  for (const card of Object.values(ITEM_CARD)) expect(cards.has(card)).toBe(true)
})

it('at 100% it is one line', () => {
  render(<CompletionCard state={state({ ...SIXTY, items: SIXTY.items.map((i) => ({ ...i, done: true })),
    done: 5, percent: 100, important_missing: [] })} />)
  expect(screen.getByTestId('profile-completion').textContent).toContain(`${P}.complete`)
  expect(screen.queryByRole('progressbar')).toBeNull()
  expect(screen.queryAllByRole('link')).toHaveLength(0)
})

it('a super (served none) sees nothing', () => {
  const { container } = render(<CompletionCard state={state(null)} />)
  expect(container.innerHTML).toBe('')
})

it('a missing item\'s link is 44 px tall on a phone, and the ticks fold away there (the phone mock-up)', () => {
  render(<CompletionCard state={state(SIXTY)} />)
  expect(screen.getByRole('link', { name: `${P}.todo.photo` }).className).toContain('max-md:min-h-11')
  expect(screen.getByTestId('completion-done-name').className).toContain('max-sm:hidden')
})
