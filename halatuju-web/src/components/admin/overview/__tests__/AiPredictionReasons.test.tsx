/**
 * @jest-environment jsdom
 *
 * F4b: the "Where it lost most points" chips on the AI prediction card. The server sends a key
 * (`fail:<code>`, `fail:not_given`, `pass:<band>`); the browser turns it into the real English
 * words, never a raw key. A fact with no lost points shows a dash.
 */
import { render, screen } from '@testing-library/react'

import en from '@/messages/en.json'
import { AiPredictionBlock } from '../AiPredictionSection'
import { reasonName } from '../AiPredictionTables'
import { factScore, metrics } from '@/test/aiPredictionFixture'

const lookup = (key: string): string | undefined =>
  key.split('.').reduce<unknown>((o, k) => (o && typeof o === 'object' ? (o as Record<string, unknown>)[k] : undefined), en) as string | undefined
const t = (key: string, params?: Record<string, string>): string => {
  const raw = lookup(key)
  if (typeof raw !== 'string') return key
  return raw.replace(/\{(\w+)\}/g, (_m, p: string) => params?.[p] ?? `{${p}}`)
}
jest.mock('@/lib/i18n', () => ({
  ...jest.requireActual('@/lib/i18n'),
  useT: () => ({ t: (k: string) => k, locale: 'en' }),
}))

describe('reason keys as words', () => {
  it.each([
    ['fail:proof_missing', 'Proof is missing or unclear'],
    ['fail:interview_differs', 'The interview or a call showed something different'],
    ['fail:other', 'Other'],
    ['fail:not_given', 'Not given'],
    ['pass:ruleNotMet', 'AI said Rule not met, reviewer passed'],
    ['pass:unverifiable', 'AI said Can\'t verify, reviewer passed'],
  ])('%s reads "%s"', (key, words) => {
    expect(reasonName(t, key)).toBe(words)
  })

  it('shows an unknown fail code or band as plain words, never a crash', () => {
    expect(reasonName(t, 'fail:some_new_code')).toBe('some new code')
    expect(reasonName(t, 'pass:certain')).toBe('pass certain')
  })
})

describe('the chips on the card', () => {
  it('prints the top reasons with their points, and a dash for a fact with none', () => {
    render(<AiPredictionBlock ai={metrics()} t={t} />)
    expect(screen.getByTestId('ai-reasons-academic').textContent)
      .toBe('The interview or a call showed something different −50AI said Rule not met, reviewer passed −28')
    expect(screen.getByTestId('ai-reasons-income').textContent).toBe('–')
  })

  it('never prints a raw key', () => {
    const ai = metrics()
    ai.score.by_fact.identity = factScore({
      top_reasons: [{ key: 'fail:document_false', points: -10 }, { key: 'pass:unverifiable', points: -4 }] })
    render(<AiPredictionBlock ai={ai} t={t} />)
    const text = screen.getByTestId('ai-reasons-identity').textContent as string
    expect(text).not.toMatch(/fail:|pass:/)
    expect(text).toContain('A document looks false or altered −10')
  })
})
