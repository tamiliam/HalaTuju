/**
 * @jest-environment jsdom
 *
 * F4b: the "AI prediction" card, scored in marks. Pinned here, with made-up figures and the REAL
 * English messages (so a key that does not exist shows up as the raw key in a failing assertion):
 *  * the figures the server sent are the figures printed — score %, points of best, points lost;
 *  * a score BELOW 0 prints with a minus sign;
 *  * a block exists because its data arrived: no `by_reviewer` = no reviewer table, no `ai_team` =
 *    no "For the AI team" fold (an org admin), `ai_team` present = the fold, open (a super);
 *  * an absent slice draws nothing (a reviewer gets no card) and a payload with no score does not crash;
 *  * facts with no mark show a small "not scored" count, never invented marks.
 */
import { render, screen, within } from '@testing-library/react'

import en from '@/messages/en.json'
import { AiPredictionBlock, AiPredictionSection } from '../AiPredictionSection'
import type { ProgrammeOverview, VerdictMetrics } from '@/lib/admin-api'
import { SECTION_RENDERERS } from '../OverviewSections'
import { block, leadMetrics, metrics, superMetrics } from '@/test/aiPredictionFixture'

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

describe('the card\'s figures (an organisation admin)', () => {
  it('prints the header, the two tiles and the legend from the served numbers', () => {
    render(<AiPredictionBlock ai={metrics()} t={t} />)
    const card = screen.getByTestId('overview-ai-prediction')
    expect(within(card).getByText('Counted over 187 decided applications')).toBeTruthy()
    const score = screen.getByTestId('ai-tile-score')
    expect(score.textContent).toContain('AI score')
    expect(score.textContent).toContain('47%')
    expect(score.textContent).toContain('+736 of a best +1,550 points. 100% = sure and right on every fact.')
    expect(score.textContent).toContain('0% = no better than "Unsure" on every fact.')
    const lost = screen.getByTestId('ai-tile-lost')
    expect(lost.textContent).toContain('Points lost')
    expect(lost.textContent).toContain('−390')
    expect(lost.textContent).toContain('Most from Pathway (−156)')
    const legend = screen.getByTestId('ai-legend').textContent as string
    for (const w of ['Right, sure (+2)', 'Right, leaning (+1)', 'Unsure (0)', 'Wrong, leaning (−3 or −1)', 'Wrong, sure (−10)']) {
      expect(legend).toContain(w)
    }
  })

  it('prints each fact row: outcome counts, score, points of best, lost, and the top reasons as chips', () => {
    render(<AiPredictionBlock ai={metrics()} t={t} />)
    const identity = screen.getByTestId('ai-fact-identity')
    expect(identity.textContent).toContain('200 facts')
    expect(identity.textContent).toContain('67%')
    expect(identity.textContent).toContain('+268 of +400')
    expect(identity.textContent).toContain('lost −52')
    const chips = within(screen.getByTestId('ai-reasons-identity')).getAllByRole('listitem')
    expect(chips.map((c) => c.textContent)).toEqual([
      'The documents show something different −30', 'Not given −20'])
  })

  it('shows the "By fact" columns in the design\'s order', () => {
    render(<AiPredictionBlock ai={metrics()} t={t} />)
    const heads = within(screen.getByTestId('ai-by-fact')).getAllByRole('columnheader').map((h) => h.textContent)
    expect(heads).toEqual(['Fact', 'Right, sure', 'Right, leaning', 'Unsure', 'Wrong, leaning', 'Wrong, sure',
      'Score', 'Where it lost most points'])
  })

  it('draws no reviewer table and no AI-team fold for an organisation admin without those keys', () => {
    render(<AiPredictionBlock ai={metrics()} t={t} />)
    expect(screen.queryByTestId('ai-by-reviewer')).toBeNull()
    expect(screen.queryByTestId('ai-team')).toBeNull()
    expect(screen.queryByText('For the AI team')).toBeNull()
    // The dropped blocks stay dropped.
    expect(screen.queryByTestId('ai-trend')).toBeNull()
    expect(screen.queryByTestId('ai-decision')).toBeNull()
    expect(screen.queryByTestId('ai-qc-checked')).toBeNull()
  })

  it('shows the extra note beside the heading when one is passed', () => {
    render(<AiPredictionBlock ai={metrics()} t={t} note="All programmes together." />)
    expect(screen.getByText('All programmes together.')).toBeTruthy()
  })
})

describe('a negative score', () => {
  it('prints a score below 0% with a minus sign, in the tile and in a row', () => {
    const ai = metrics()
    ai.score = { ...ai.score, ...block({ facts: 100, points: -40, best: 200, lost: -90, score_pct: -20 }) }
    ai.score.by_fact = { ...ai.score.by_fact, pathway: { ...ai.score.by_fact.pathway, points: -12, score_pct: -6 } }
    render(<AiPredictionBlock ai={ai} t={t} />)
    expect(screen.getByTestId('ai-tile-score').textContent).toContain('−20%')
    expect(screen.getByTestId('ai-tile-score').textContent).toContain('−40 of a best +200 points')
    expect(screen.getByTestId('ai-fact-pathway').textContent).toContain('−6%')
  })

  it('prints a dash, not 0%, for a served null score', () => {
    const ai = metrics()
    ai.score = { ...ai.score, score_pct: null }
    render(<AiPredictionBlock ai={ai} t={t} />)
    expect(screen.getByTestId('ai-tile-score').textContent).toContain('–')
  })
})

describe('blocks appear by presence, never by role', () => {
  it('draws the reviewer table with counts and the footnote when by_reviewer arrived', () => {
    render(<AiPredictionBlock ai={leadMetrics()} t={t} />)
    const section = screen.getByTestId('ai-by-reviewer')
    const heads = within(section).getAllByRole('columnheader').map((h) => h.textContent)
    expect(heads).toEqual(['Reviewer', 'Applications', 'Green but failed', 'Unsure but passed', 'QC accepted', 'QC sent back'])
    const rows = screen.getAllByTestId('ai-reviewer-row')
    expect(rows).toHaveLength(3)
    expect(rows[0].textContent).toContain('Test Reviewer One')
    expect(rows[0].textContent).toContain('12')
    expect(section.textContent).toContain('Green but failed: the AI was sure, but the reviewer failed the fact.')
    expect(section.textContent).toContain('Unsure but passed: the AI was in doubt, but the reviewer passed the fact.')
  })

  it('shows the neutral label for a label_key row, not the served name', () => {
    render(<AiPredictionBlock ai={leadMetrics()} t={t} />)
    expect(screen.getByText('Reviewer not matched to an account')).toBeTruthy()
    expect(screen.getByText('Reviewer not named')).toBeTruthy()
  })

  it('draws the open "For the AI team" fold, with doubts and model versions, when ai_team arrived', () => {
    render(<AiPredictionBlock ai={superMetrics()} t={t} />)
    const fold = screen.getByTestId('ai-team') as HTMLDetailsElement
    expect(fold.open).toBe(true)
    expect(fold.textContent).toContain('For the AI team')
    expect(fold.textContent).toContain('Only you see this part.')
    expect(within(fold).getByTestId('ai-doubts').textContent).toContain('18 passed')
    const rows = within(fold).getAllByTestId('ai-version-row')
    expect(rows).toHaveLength(2)
    expect(rows[0].textContent).toContain('v5.1')
    expect(rows[0].textContent).toContain('40%')
    expect(rows[0].textContent).toContain('+210 of +520')
    // A blank version is named, and its negative score prints.
    expect(rows[1].textContent).toContain('Unknown version')
    expect(rows[1].textContent).toContain('−3%')
  })

  it('says so, instead of drawing empty tiles, when there is nothing to count yet', () => {
    const ai = metrics({ applications: 0 })
    ai.score = { ...ai.score, ...block({ facts: 0, points: 0, best: 0, lost: 0, score_pct: null }) }
    render(<AiPredictionBlock ai={ai} t={t} />)
    expect(screen.getByTestId('ai-empty')).toBeTruthy()
    expect(screen.queryByTestId('ai-tile-score')).toBeNull()
  })
})

describe('facts with no mark', () => {
  it('shows a small "not scored" count when some decided facts could not be marked', () => {
    const ai = metrics()
    ai.score = { ...ai.score, not_scored: 4 }
    render(<AiPredictionBlock ai={ai} t={t} />)
    expect(screen.getByTestId('ai-not-scored').textContent).toContain('4 decided facts had no AI mark')
  })

  it('shows nothing about it when every fact was marked', () => {
    render(<AiPredictionBlock ai={metrics()} t={t} />)
    expect(screen.queryByTestId('ai-not-scored')).toBeNull()
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

  it('draws nothing at all for a payload without the key (a reviewer: the server sends no section)', () => {
    const { container } = render(<AiPredictionSection data={overview({})} t={t} />)
    expect(container.innerHTML).toBe('')
  })

  it('draws nothing, and does not throw, for a slice with no score (an old or odd payload)', () => {
    const odd = { applications: 3 } as unknown as VerdictMetrics
    const { container } = render(<AiPredictionSection data={overview({ ai_prediction: odd })} t={t} />)
    expect(container.querySelector('[data-testid="overview-ai-prediction"]')).toBeNull()
  })
})
