/**
 * @jest-environment jsdom
 *
 * LL2b: "checked by the QC" on the "AI prediction" card, and the two QC columns of the by-reviewer
 * table. Made-up figures, the real English messages. The browser only prints served counts: no
 * percent, the served `few` flag adds the pill, and old payloads (no keys) draw the card as before.
 */
import { render, screen, within } from '@testing-library/react'

import en from '@/messages/en.json'
import { AiPredictionBlock } from '../AiPredictionSection'
import { leadMetrics, metrics, qcChecked, reviewer } from '@/test/aiPredictionFixture'

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

const withQc = () => metrics({
  qc_checked: {
    total: qcChecked({ in_doubt: 9, checked: 7, not_checked: 2, agreed: 5, disagreed: 2 }),
    facts: {
      identity: qcChecked(),
      academic: qcChecked({ in_doubt: 6, checked: 5, not_checked: 1, agreed: 4, disagreed: 1 }),
      pathway: qcChecked({ in_doubt: 3, checked: 2, not_checked: 1, agreed: 1, disagreed: 1, few: true }),
      income: qcChecked(),
    },
  },
})

describe('checked by the QC, on the card', () => {
  it('prints checked "x of y", agreed and disagreed for each fact in doubt, never a percent', () => {
    render(<AiPredictionBlock ai={withQc()} t={t} />)
    const block = screen.getByTestId('ai-qc-checked')
    expect(within(block).getByText('Facts in doubt, checked by the QC')).toBeTruthy()
    const academic = screen.getByTestId('ai-qc-academic')
    expect(academic.textContent).toBe('Academic5 of 641')
    expect(block.textContent).not.toMatch(/%/)
  })

  it('a fact with none in doubt has no row', () => {
    render(<AiPredictionBlock ai={withQc()} t={t} />)
    expect(screen.queryByTestId('ai-qc-identity')).toBeNull()
    expect(screen.queryByTestId('ai-qc-income')).toBeNull()
  })

  it('the served few flag adds the "Few cases" pill; enough cases add none', () => {
    render(<AiPredictionBlock ai={withQc()} t={t} />)
    expect(within(screen.getByTestId('ai-qc-pathway')).queryByTestId('few-pill')).not.toBeNull()
    expect(within(screen.getByTestId('ai-qc-academic')).queryByTestId('few-pill')).toBeNull()
  })

  it('shows nothing when no fact was in doubt', () => {
    render(<AiPredictionBlock ai={metrics({ qc_checked: { total: qcChecked(), facts: {} } })} t={t} />)
    expect(screen.queryByTestId('ai-qc-checked')).toBeNull()
  })

  it('shows nothing on an older payload with no qc_checked key', () => {
    render(<AiPredictionBlock ai={metrics()} t={t} />)
    expect(screen.queryByTestId('ai-qc-checked')).toBeNull()
  })
})

describe('the QC columns of the by-reviewer table', () => {
  it('appear with the served counts when the rows carry them', () => {
    render(<AiPredictionBlock ai={metrics({ by_reviewer: [
      reviewer({ qc_checked: 8, qc_overturned: 3 }),
    ] })} t={t} />)
    const table = screen.getByTestId('ai-by-reviewer')
    expect(within(table).getAllByText('Checked by the QC').length).toBeGreaterThan(0)
    expect(within(table).getAllByText('Disagreed with the reviewer').length).toBeGreaterThan(0)
    const row = screen.getByTestId('ai-reviewer-row')
    expect(row.querySelector('[data-label="Checked by the QC"]')?.textContent).toBe('8')
    expect(row.querySelector('[data-label="Disagreed with the reviewer"]')?.textContent).toBe('3')
  })

  it('are absent on an older payload (rows without the keys)', () => {
    render(<AiPredictionBlock ai={leadMetrics()} t={t} />)
    expect(within(screen.getByTestId('ai-by-reviewer')).queryByText('Checked by the QC')).toBeNull()
  })
})
