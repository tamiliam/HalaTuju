/**
 * @jest-environment jsdom
 *
 * The Quiz tab is a REHEARSAL, not a form. What it must prove is the behaviour you cannot see in an
 * editor: a wrong answer explains itself and lets you go again without penalty, and Next stays shut
 * until the checkpoint is actually passed.
 */
import { fireEvent, render, screen } from '@testing-library/react'
import QuizRehearsal from './QuizRehearsal'
import type { SponsorTermsSection } from '@/lib/admin-api'

const t = (k: string, p?: Record<string, string>) =>
  (p ? `${k}:${Object.values(p).join(',')}` : k)

const QUIZ = {
  tag: 'Unused credit', plain: 'Credit left unused is eventually reallocated.',
  question: 'What happens to it?',
  options: ['It is refunded to you', 'It stays yours', 'We reallocate it'],
  correct: 2, why: 'A donation cannot be refunded.',
}

const section = (over: Partial<SponsorTermsSection> = {}): SponsorTermsSection => ({
  order: 11, heading_en: 'Refunds', heading_ms: '', heading_ta: '',
  body_en: 'Body.', body_ms: '', body_ta: '',
  is_quiz_candidate: true, quiz_en: QUIZ, quiz_ms: {}, quiz_ta: {},
  quiz_generated_model: '', ...over,
})

describe('taking the quiz', () => {
  it('shows the label, the plain restatement and the question as distinct things', () => {
    render(<QuizRehearsal sections={[section()]} t={t} />)
    expect(screen.getByText('Unused credit')).toBeTruthy()
    expect(screen.getByText('Credit left unused is eventually reallocated.')).toBeTruthy()
    expect(screen.getByText('What happens to it?')).toBeTruthy()
  })

  it('a wrong answer explains itself and lets you try again — never penalised', () => {
    render(<QuizRehearsal sections={[section()]} t={t} />)
    fireEvent.click(screen.getByText('It is refunded to you'))

    expect(screen.getByText('admin.sponsors.terms.rehearseWrong')).toBeTruthy()
    expect(screen.getByText('A donation cannot be refunded.')).toBeTruthy()
    // The other options stay live — that is the "try again" the owner asked to be able to see.
    expect((screen.getByText('We reallocate it') as HTMLButtonElement).disabled).toBe(false)
  })

  it('keeps Next shut until the checkpoint is passed', () => {
    render(<QuizRehearsal sections={[section()]} t={t} />)
    const next = screen.getByText('admin.sponsors.terms.rehearseFinish') as HTMLButtonElement
    expect(next.disabled).toBe(true)

    fireEvent.click(screen.getByText('It is refunded to you'))     // wrong
    expect(next.disabled).toBe(true)

    fireEvent.click(screen.getByText('We reallocate it'))          // right
    expect(screen.getByText('admin.sponsors.terms.rehearseRight')).toBeTruthy()
    expect(next.disabled).toBe(false)
  })

  it('reaches the end and says what would happen next for a sponsor', () => {
    render(<QuizRehearsal sections={[section()]} t={t} />)
    fireEvent.click(screen.getByText('We reallocate it'))
    fireEvent.click(screen.getByText('admin.sponsors.terms.rehearseFinish'))
    expect(screen.getByText('admin.sponsors.terms.rehearseDone:1')).toBeTruthy()
    expect(screen.getByText('admin.sponsors.terms.rehearseDoneBody')).toBeTruthy()
  })

  it('starts again from the top', () => {
    render(<QuizRehearsal sections={[section()]} t={t} />)
    fireEvent.click(screen.getByText('We reallocate it'))
    fireEvent.click(screen.getByText('admin.sponsors.terms.rehearseRestart'))
    expect(screen.queryByText('admin.sponsors.terms.rehearseRight')).toBeNull()
  })
})

describe('what it refuses to show', () => {
  it('says nothing is set up when no section is a checkpoint', () => {
    render(<QuizRehearsal sections={[section({ is_quiz_candidate: false })]} t={t} />)
    expect(screen.getByText('admin.sponsors.terms.quizNone')).toBeTruthy()
  })

  it('skips a half-written checkpoint rather than showing an unanswerable card', () => {
    // Same rule as the server's Q2 — the rehearsal must never display a card that could not ship.
    render(<QuizRehearsal sections={[section({ quiz_en: { question: 'Half?', options: ['a'] } })]} t={t} />)
    expect(screen.getByText('admin.sponsors.terms.quizNone')).toBeTruthy()
  })

  it('walks every complete checkpoint in section order', () => {
    render(<QuizRehearsal
      sections={[section({ order: 1 }), section({ order: 11 })]} t={t} />)
    expect(screen.getByText('admin.sponsors.terms.rehearseProgress:1,2,1')).toBeTruthy()
  })
})
