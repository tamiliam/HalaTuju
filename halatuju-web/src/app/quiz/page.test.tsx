/**
 * @jest-environment jsdom
 *
 * The interest quiz on a phone (owner, 2026-11-02, Mobile M4c follow-up): the row of 10 px question dots
 * cannot be 44 px targets, so below `md` it is HIDDEN; the header's progress bar and "Question n of N" say
 * where she is, and she moves with Next / Previous (Next once the question has an answer). From `md` the
 * dots and the old layout stay. jsdom applies no media queries, so "hidden below md" is the class pair
 * `hidden md:flex` on the dot row and `md:hidden` on Next. `t` echoes its key and params.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import QuizPage from './page'
import * as api from '@/lib/api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }),
}))
jest.mock('@/lib/auth-context', () => ({
  useAuth: () => ({ isAuthenticated: true, isLoading: false, showAuthGate: jest.fn(), token: 'tok' }),
}))
const mockRouter = { push: jest.fn(), replace: jest.fn() }
jest.mock('next/navigation', () => ({ useRouter: () => mockRouter, useSearchParams: () => new URLSearchParams() }))
jest.mock('@/lib/api')
const mockApi = api as jest.Mocked<typeof api>

const opt = (text: string) => ({ text, icon: 'laptop_code', signals: {} })
const QUESTIONS = [
  { id: 'q1', prompt: 'First?', select_mode: 'multi' as const, max_select: 2, options: [opt('A'), opt('B'), opt('C'), opt('D')] },
  { id: 'q2', prompt: 'Second?', options: [opt('E'), opt('F'), opt('G'), opt('H')] },
  { id: 'q3', prompt: 'Third?', options: [opt('I'), opt('J'), opt('K'), opt('L')] },
]

beforeEach(() => {
  jest.resetAllMocks()
  mockApi.getQuizQuestions.mockResolvedValue({ questions: QUESTIONS } as never)
})

const classes = (el: Element) => (el.getAttribute('class') ?? '').split(/\s+/)

describe('the quiz on a phone: a progress bar and Next / Previous, no dot row', () => {
  it('hides the dot row below md and keeps it from md', async () => {
    render(<QuizPage />)
    await screen.findByText('First?')
    const dots = screen.getByTestId('quiz-dots')
    expect(classes(dots)).toEqual(expect.arrayContaining(['hidden', 'md:flex']))
    expect(dots.querySelectorAll('button')).toHaveLength(3)   // still one per question, for md and up
  })

  it('shows where she is: "Question n of N" and the progress bar, at every width', async () => {
    render(<QuizPage />)
    const count = await screen.findByText('quiz.questionOf|{"current":"1","total":"3"}')
    // No width class on the count or its bar: a phone shows both.
    expect(classes(count).some((c) => /^(hidden|md:)/.test(c))).toBe(false)
    const bar = document.querySelector('[style*="width"]') as HTMLElement
    expect(bar.style.width).toBe(`${(1 / 3) * 100}%`)
    expect(classes(bar.parentElement!).some((c) => c === 'hidden')).toBe(false)
  })

  it('Next is a 44 px phone button that waits for an answer, then moves on; Previous goes back', async () => {
    render(<QuizPage />)
    await screen.findByText('First?')
    const next = screen.getByTestId('quiz-next')
    expect(classes(next)).toEqual(expect.arrayContaining(['md:hidden', 'min-h-11']))
    expect(next.textContent).toContain('discovery.quizNext')
    expect((next as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByText('A'))           // multi-select: one pick, no auto-advance
    expect((next as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(next)
    await screen.findByText('Second?')
    fireEvent.click(screen.getByText('quiz.previous'))
    await screen.findByText('First?')
  })

  it('on the last question the submit button takes Next’s place', async () => {
    render(<QuizPage />)
    await screen.findByText('First?')
    fireEvent.click(screen.getByText('A'))
    fireEvent.click(screen.getByTestId('quiz-next'))
    await screen.findByText('Second?')
    fireEvent.click(screen.getByText('E'))           // single choice auto-advances, as on desktop
    await waitFor(() => expect(screen.queryByText('Third?')).not.toBeNull(), { timeout: 2000 })
    expect(screen.queryByTestId('quiz-next')).toBeNull()
    expect(screen.queryByText('quiz.seeResults')).not.toBeNull()
  })
})
