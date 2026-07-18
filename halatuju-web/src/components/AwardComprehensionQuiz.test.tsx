/**
 * @jest-environment jsdom
 *
 * Slim component test for the API-served comprehension quiz (Sprint 4). The content
 * invariants (3 options, one correct, locale parity) now live server-side (contracts
 * Q2–Q4 + pytest); this pins the FE behaviour: fetch → walk → record the pass pinned
 * to the template_version, and re-take on a version_changed 409.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import AwardComprehensionQuiz from './AwardComprehensionQuiz'
import * as api from '@/lib/api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ locale: 'en', t: (k: string) => k }) }))
jest.mock('@/lib/api')

const mockApi = api as jest.Mocked<typeof api>

const QUIZ = {
  template_version: '2026-v1',
  locale_used: 'en',
  checkpoints: [
    { tag: 'T', plain: 'P', question: 'Q1?', options: ['wrong', 'right', 'no'], correct: 1, why: 'because' },
  ],
}

beforeAll(() => { window.scrollTo = jest.fn() })
beforeEach(() => jest.clearAllMocks())

describe('AwardComprehensionQuiz', () => {
  it('fetches the quiz, walks it, and records the pass pinned to the version', async () => {
    mockApi.getComprehensionQuiz.mockResolvedValue(QUIZ)
    mockApi.recordComprehensionPass.mockResolvedValue({ ok: true, template_version: '2026-v1' })
    const onComplete = jest.fn()

    render(<AwardComprehensionQuiz onComplete={onComplete} token="tok" />)

    // fetched with the locale + token
    await waitFor(() => expect(mockApi.getComprehensionQuiz).toHaveBeenCalledWith('en', { token: 'tok' }))
    // intro → begin → answer correctly → finish
    fireEvent.click(await screen.findByText(/begin/i))
    fireEvent.click(screen.getByText('right'))
    fireEvent.click(screen.getByText(/read & sign/i))

    await waitFor(() =>
      expect(mockApi.recordComprehensionPass).toHaveBeenCalledWith('2026-v1', { token: 'tok' }))
    await waitFor(() => expect(onComplete).toHaveBeenCalled())
  })

  it('re-takes on a version_changed 409 (never completes)', async () => {
    mockApi.getComprehensionQuiz.mockResolvedValue(QUIZ)
    mockApi.recordComprehensionPass.mockRejectedValue(
      Object.assign(new Error('version_changed'), { code: 'version_changed' }))
    const onComplete = jest.fn()

    render(<AwardComprehensionQuiz onComplete={onComplete} token="tok" />)
    fireEvent.click(await screen.findByText(/begin/i))
    fireEvent.click(screen.getByText('right'))
    fireEvent.click(screen.getByText(/read & sign/i))

    expect(await screen.findByText(/agreement was updated/i)).toBeTruthy()
    expect(onComplete).not.toHaveBeenCalled()
    // it re-fetched for the re-take
    await waitFor(() => expect(mockApi.getComprehensionQuiz).toHaveBeenCalledTimes(2))
  })

  it('shows an error + retry when the fetch fails', async () => {
    mockApi.getComprehensionQuiz.mockRejectedValue(new Error('boom'))
    render(<AwardComprehensionQuiz onComplete={jest.fn()} token="tok" />)
    expect(await screen.findByText(/load the questions/i)).toBeTruthy()
  })
})
