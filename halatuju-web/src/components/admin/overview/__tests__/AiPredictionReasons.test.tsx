/**
 * @jest-environment jsdom
 *
 * LL2: the reason counts on the "AI prediction" card. Made-up figures, the real English messages.
 * The browser only prints what the server counted; a fact with no green -> fail case shows nothing,
 * and a payload from before LL2 (no reason keys) must draw the card exactly as it did.
 */
import { render, screen } from '@testing-library/react'

import en from '@/messages/en.json'
import { AiPredictionBlock } from '../AiPredictionSection'
import { counts, metrics } from '@/test/aiPredictionFixture'

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

const zero = { engine_wrong: 0, read_wrong: 0, new_information: 0, programme_rule: 0, other: 0 }
const withReasons = () => metrics({
  fact_counts: {
    identity: counts({ green: 50, green_failed: 0, green_agreed: 50, green_agree_rate: 1 }),
    academic: counts({ green: 30, green_failed: 3, green_agreed: 27, green_agree_rate: 0.9 }),
    pathway: counts({ green: 10, green_failed: 4, green_agreed: 6, green_agree_rate: 0.6, few_green: true }),
    income: counts({ green: 10, green_failed: 2, green_agreed: 8, green_agree_rate: 0.8 }),
  },
  fail_reasons: {
    identity: zero,
    academic: { ...zero, new_information: 2, read_wrong: 1 },
    pathway: { ...zero, programme_rule: 4 },
    income: { ...zero, other: 1 },
  },
  fail_reasons_not_given: { identity: 0, academic: 0, pathway: 0, income: 1 },
})

describe('reason counts on the card', () => {
  it('prints each fact\'s counts, in the fixed order, with "Not given" last', () => {
    render(<AiPredictionBlock ai={withReasons()} t={t} />)
    expect(screen.getByTestId('ai-reasons-academic').textContent).toBe('The document was read wrong 1 · New information (interview, call) 2')
    expect(screen.getByTestId('ai-reasons-income').textContent).toBe('Other 1 · Not given 1')
  })

  it('a few-cases fact still shows plain counts (never a percent)', () => {
    render(<AiPredictionBlock ai={withReasons()} t={t} />)
    expect(screen.getByTestId('ai-reasons-pathway').textContent).toBe('A programme rule 4')
    expect(screen.getByTestId('ai-reasons-pathway').textContent).not.toMatch(/%/)
  })

  it('a fact with no green -> fail case shows nothing', () => {
    render(<AiPredictionBlock ai={withReasons()} t={t} />)
    expect(screen.getByTestId('ai-reasons-identity').textContent).toBe('')
  })

  it('old data (no reason keys) draws no reasons column and does not crash', () => {
    render(<AiPredictionBlock ai={metrics()} t={t} />)
    expect(screen.queryByTestId('ai-reasons-academic')).toBeNull()
    expect(screen.queryByText('Why it failed')).toBeNull()
  })

  it('reasons present but empty of failures draw no column either', () => {
    render(<AiPredictionBlock ai={metrics({
      fact_counts: { identity: counts({ green_failed: 0 }) }, fail_reasons: { identity: zero },
      fail_reasons_not_given: { identity: 0 } })} t={t} />)
    expect(screen.queryByTestId('ai-reasons-identity')).toBeNull()
  })
})
