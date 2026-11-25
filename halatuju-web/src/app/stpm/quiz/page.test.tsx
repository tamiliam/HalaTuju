/**
 * @jest-environment jsdom
 *
 * TD-708 (STPM quiz): one step per answer. Picking an answer schedules an auto-advance after 300 ms;
 * on a phone the Next button can be tapped inside that window. Both used to fire, so the page moved
 * two steps and skipped a question. Next and Previous now cancel the pending advance, and it moves on
 * from the step the answer was given on. Fake timers; `t` echoes its key.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import StpmQuizPage from './page'
import * as api from '@/lib/api'

// One stable object: a fresh `t` every render re-runs the page's effects forever (out of memory).
const mockT = { t: (k: string, p?: Record<string, string>) => (p ? `${k}|${JSON.stringify(p)}` : k), locale: 'en' }
jest.mock('@/lib/i18n', () => ({ useT: () => mockT }))
const mockAuth = { isAuthenticated: true, isLoading: false, showAuthGate: jest.fn(), token: 'tok' }
jest.mock('@/lib/auth-context', () => ({ useAuth: () => mockAuth }))
const mockRouter = { push: jest.fn(), replace: jest.fn() }
const mockParams = new URLSearchParams()
jest.mock('next/navigation', () => ({ useRouter: () => mockRouter, useSearchParams: () => mockParams }))
jest.mock('@/lib/api')
const mockApi = api as jest.Mocked<typeof api>

const opt = (text: string) => ({ text, icon: 'target_bullseye', signals: { field_x: 1 } })
const q = (id: string, prompt: string, a: string, b: string) => ({ id, prompt, options: [opt(a), opt(b)] })

beforeEach(() => {
  jest.resetAllMocks()
  jest.useFakeTimers()
  localStorage.setItem('halatuju_stpm_grades', JSON.stringify({ PHYSICS: 'A', CHEMISTRY: 'B' }))
  mockApi.getStpmQuizQuestions.mockResolvedValue({
    branch: 'science',
    questions: [q('q1', 'First?', 'A1', 'A2'), q('q2', 'Second?', 'B1', 'B2')],
    q5: q('q5', 'Fifth?', 'C1', 'C2'),
    trunk_remaining: [q('q7', 'Seventh?', 'D1', 'D2')],
  } as never)
})
afterEach(() => {
  jest.useRealTimers()
  localStorage.clear()
})

async function open() {
  render(<StpmQuizPage />)
  await act(async () => { await Promise.resolve() })
  expect(screen.queryByText('First?')).not.toBeNull()
}

describe('STPM quiz: one step per answer (TD-708)', () => {
  it('answer then Next at once lands on the next question, not two ahead', async () => {
    await open()
    fireEvent.click(screen.getByText('A1'))
    fireEvent.click(screen.getByTestId('quiz-next'))
    act(() => { jest.advanceTimersByTime(1000) })
    expect(screen.queryByText('Second?')).not.toBeNull()
  })

  it('answer then wait still auto-advances exactly one step', async () => {
    await open()
    fireEvent.click(screen.getByText('A1'))
    expect(screen.queryByText('First?')).not.toBeNull()
    act(() => { jest.advanceTimersByTime(300) })
    expect(screen.queryByText('Second?')).not.toBeNull()
    act(() => { jest.advanceTimersByTime(2000) })
    expect(screen.queryByText('Second?')).not.toBeNull()
  })

  it('answer then Previous does not jump forward later', async () => {
    await open()
    fireEvent.click(screen.getByText('A1'))
    fireEvent.click(screen.getByTestId('quiz-next'))
    expect(screen.queryByText('Second?')).not.toBeNull()
    fireEvent.click(screen.getByText('B1'))            // schedules an advance from step 2
    fireEvent.click(screen.getByText('quiz.previous'))
    act(() => { jest.advanceTimersByTime(2000) })
    expect(screen.queryByText('First?')).not.toBeNull()
  })
})

// The Q2 answer used to vanish once Q3/Q4 came back: the lookup kept Q1/Q2 answers from the render
// before the Q2 tap, which had no Q2 answer. So the last page's "See results" stayed grey.
describe('STPM quiz: the Q2 answer survives the Q3/Q4 lookup', () => {
  async function flush() {
    await act(async () => { for (let i = 0; i < 5; i++) await Promise.resolve() })
  }
  async function toQ2() {
    await open()
    fireEvent.click(screen.getByText('A1'))
    act(() => { jest.advanceTimersByTime(300) })
    expect(screen.queryByText('Second?')).not.toBeNull()
  }
  beforeEach(() => {
    mockApi.resolveStpmQuizQ3Q4.mockResolvedValue({ q3: q('q3', 'Third?', 'E1', 'E2'), q4: null } as never)
  })

  it('keeps the Q2 answer and moves on to Q3', async () => {
    await toQ2()
    fireEvent.click(screen.getByText('B1'))
    await flush()
    act(() => { jest.advanceTimersByTime(300) })
    expect(screen.queryByText('Third?')).not.toBeNull()
    expect(screen.queryByText('quiz.answered|{"count":"2"}')).not.toBeNull()
  })

  it('two quick taps on Q2 start one lookup and keep the last answer', async () => {
    await toQ2()
    fireEvent.click(screen.getByText('B1'))
    fireEvent.click(screen.getByText('B2'))
    await flush()
    expect(mockApi.resolveStpmQuizQ3Q4).toHaveBeenCalledTimes(1)
    act(() => { jest.advanceTimersByTime(300) })
    expect(screen.queryByText('quiz.answered|{"count":"2"}')).not.toBeNull()
    fireEvent.click(screen.getByText('quiz.previous'))
    expect(screen.getByText('B2').closest('button')!.className).toContain('border-info-500')
  })

  it('Previous during the lookup is not undone by the auto-advance', async () => {
    await toQ2()
    fireEvent.click(screen.getByText('B1'))
    fireEvent.click(screen.getByText('quiz.previous'))
    await flush()
    act(() => { jest.advanceTimersByTime(2000) })
    expect(screen.queryByText('First?')).not.toBeNull()
  })

  it('Next waits on a phone while the lookup runs', async () => {
    await toQ2()
    fireEvent.click(screen.getByText('B1'))
    expect((screen.getByTestId('quiz-next') as HTMLButtonElement).disabled).toBe(true)
    await flush()
    expect((screen.getByTestId('quiz-next') as HTMLButtonElement).disabled).toBe(false)
  })
})
