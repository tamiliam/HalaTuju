/**
 * @jest-environment jsdom
 *
 * LL1: the "AI prediction" section. Pinned here, with made-up figures and the REAL English messages
 * (so a key that does not exist shows up as the raw key in a failing assertion):
 *  * the figures the server sent are the figures printed — a rounded percent, "x of y", a month name;
 *  * ⚠ a served `few` flag prints the count and a "few cases" pill and NO percent;
 *  * a block exists because its data arrived: no `by_reviewer` means no reviewer table and no "Leads only" tag;
 *  * the two neutral reviewer rows show a translated label, not the served name;
 *  * an absent slice draws nothing — the page never asks who the reader is.
 */
import { render, screen, within } from '@testing-library/react'

import en from '@/messages/en.json'
import { AiPredictionBlock, AiPredictionSection } from '../AiPredictionSection'
import type { ProgrammeOverview } from '@/lib/admin-api'
import { SECTION_RENDERERS } from '../OverviewSections'
import { counts, leadMetrics, metrics } from '@/test/aiPredictionFixture'

const lookup = (key: string): string | undefined =>
  key.split('.').reduce<unknown>((o, k) => (o && typeof o === 'object' ? (o as Record<string, unknown>)[k] : undefined), en) as string | undefined

const t = (key: string, params?: Record<string, string>): string => {
  const raw = lookup(key)
  if (typeof raw !== 'string') return key
  return raw.replace(/\{(\w+)\}/g, (_m, p: string) => params?.[p] ?? `{${p}}`)
}

// TableFrame reads `useT` (for its own scroll hints only); the block's text comes from the `t` prop.
jest.mock('@/lib/i18n', () => ({
  ...jest.requireActual('@/lib/i18n'),
  useT: () => ({ t: (k: string) => k, locale: 'en' }),
}))

const overview = (over: Partial<ProgrammeOverview>): ProgrammeOverview => ({
  programme: null, generated_at: '2026-11-01T00:00:00Z', data_to: null, sections: ['ai_prediction'],
  intake: null, intakes: [], ...over,
})

describe('the picture\'s figures', () => {
  it('prints the headline tiles, the fact table and the doubts from the served numbers', () => {
    render(<AiPredictionBlock ai={metrics()} t={t} />)
    const block = screen.getByTestId('overview-ai-prediction')
    expect(within(block).getByText('90%')).toBeTruthy()
    expect(within(block).getByText('90 of 100 facts')).toBeTruthy()
    expect(within(block).getByText('75%')).toBeTruthy()
    expect(within(block).getByText('30 of 40 facts')).toBeTruthy()
    const identity = screen.getByTestId('ai-fact-identity')
    expect(identity.textContent).toContain('49 of 50')
    expect(identity.textContent).toContain('(98%)')
    expect(screen.getByTestId('ai-doubts').textContent).toContain('18 of 20')
    expect(screen.getByTestId('ai-decision').textContent).toContain('17 of 20')
    expect(screen.getByTestId('ai-decision').textContent).toContain('Sent back: 2. Rejected: 1.')
  })

  it('labels the trend months from the YYYY-MM key and lists every month as text', () => {
    render(<AiPredictionBlock ai={metrics()} t={t} />)
    const values = screen.getByTestId('ai-trend-values')
    expect(values.textContent).toContain('Aug')
    expect(values.textContent).toContain('17 of 20')
    expect(values.textContent).toContain('85%')
    expect(screen.getByTestId('ai-trend').textContent).toContain('2026')
  })

  it('keeps the engine-version table inside a collapsed details and names a blank version', () => {
    render(<AiPredictionBlock ai={metrics()} t={t} />)
    const details = screen.getByTestId('ai-by-version') as HTMLDetailsElement
    expect(details.open).toBe(false)
    expect(details.textContent).toContain('v5.1')
    expect(details.textContent).toContain('Unknown version')
  })

  it('shows the extra note beside the heading when one is passed', () => {
    render(<AiPredictionBlock ai={metrics()} t={t} note="All programmes together." />)
    expect(screen.getByText('All programmes together.')).toBeTruthy()
  })
})

describe('few cases', () => {
  it('prints the count and a pill, and no percent, when the served flag says few', () => {
    render(<AiPredictionBlock t={t}
      ai={metrics({ overall: counts({ green: 4, green_agreed: 4, green_agree_rate: 1, few_green: true }) })} />)
    const tile = screen.getByText('4 of 4 facts').parentElement as HTMLElement
    expect(within(tile).getByTestId('few-pill')).toBeTruthy()
    expect(tile.textContent).not.toContain('100%')
  })

  it('does the same in a table row and for a doubt row', () => {
    render(<AiPredictionBlock ai={metrics()} t={t} />)
    const doubts = screen.getByTestId('ai-doubts')
    expect(within(doubts).getByTestId('few-pill')).toBeTruthy()
    expect(doubts.textContent).toContain('3 of 4')
    expect(doubts.textContent).not.toContain('75%')
    // The September trend month is few too: its percent is not printed anywhere in the values row.
    const sept = within(screen.getByTestId('ai-trend-values')).getByText('Sep').parentElement as HTMLElement
    expect(within(sept).getByTestId('few-pill')).toBeTruthy()
    expect(sept.textContent).not.toContain('100%')
  })
})

describe('blocks appear by presence, never by role', () => {
  it('draws no reviewer table and no "Leads only" tag when by_reviewer did not arrive', () => {
    render(<AiPredictionBlock ai={metrics()} t={t} />)
    expect(screen.queryByTestId('ai-by-reviewer')).toBeNull()
    expect(screen.queryByText('Leads only')).toBeNull()
  })

  it('draws the reviewer table with the tag when by_reviewer arrived', () => {
    render(<AiPredictionBlock ai={leadMetrics()} t={t} />)
    expect(screen.getByText('Leads only')).toBeTruthy()
    expect(screen.getAllByTestId('ai-reviewer-row')).toHaveLength(3)
    expect(screen.getByText('Test Reviewer One')).toBeTruthy()
  })

  it('shows the neutral label for a label_key row, not the served name', () => {
    render(<AiPredictionBlock ai={leadMetrics()} t={t} />)
    expect(screen.getByText('Reviewer not matched to an account')).toBeTruthy()
    expect(screen.getByText('Reviewer not named')).toBeTruthy()
  })

  it('draws no Decision block when nothing went through the quality check', () => {
    render(<AiPredictionBlock t={t}
      ai={metrics({ qc_agreement: { accept: 0, reopen: 0, reject: 0, total: 0, accept_rate: 0, few: true, by_month: {} } })} />)
    expect(screen.queryByTestId('ai-decision')).toBeNull()
  })

  it('says so, instead of drawing empty tiles, when there is nothing to count yet', () => {
    render(<AiPredictionBlock t={t}
      ai={metrics({ overall: counts({ green: 0, unsure: 0 }) })} />)
    expect(screen.getByTestId('ai-empty')).toBeTruthy()
    expect(screen.queryByTestId('ai-trend')).toBeNull()
  })
})

describe('the Overview renderer', () => {
  it('is registered under the key the server sends', () => {
    expect(SECTION_RENDERERS.ai_prediction).toBe(AiPredictionSection)
  })

  it('draws the section when the slice arrived', () => {
    render(<AiPredictionSection data={overview({ ai_prediction: metrics() })} t={t} />)
    expect(screen.getByTestId('overview-ai-prediction')).toBeTruthy()
  })

  it('draws nothing at all for a payload without the key (what a reader the server withholds it from gets)', () => {
    const { container } = render(<AiPredictionSection data={overview({})} t={t} />)
    expect(container.innerHTML).toBe('')
  })
})
