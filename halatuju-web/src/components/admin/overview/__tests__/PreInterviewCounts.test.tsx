/**
 * @jest-environment jsdom
 *
 * Request #75: the Overview funnel counts students rejected before interview, in total and by main
 * reason, under the funnel's tiles (where the decline count already shows). Like the funnel, a
 * reason at zero is not drawn, and with none at all the block is absent.
 */
import { render, screen } from '@testing-library/react'
import { FunnelSection } from '../OverviewSections'
import type { ProgrammeOverview } from '@/lib/admin-api'

const t = ((k: string) => k) as never
const BY_REASON = {
  not_b40: 2, not_government_institution: 0, results_too_low: 1,
  programme_requirements: 0, not_responsive: 0, other: 0,
}
const draw = (pre_interview?: { total: number; by_reason: Record<string, number> }) =>
  render(<FunnelSection t={t} data={{
    funnel: { total: 10, by_status: { rejected: 3 }, pre_interview },
  } as unknown as ProgrammeOverview} />)

describe('rejected before interview, on the Overview funnel', () => {
  it('shows the total and each reason that has a case', () => {
    draw({ total: 3, by_reason: BY_REASON })
    const block = screen.getByTestId('overview-pre-interview')
    expect(block.textContent).toContain('admin.programmeOverview.funnel.preInterview')
    expect(block.textContent).toContain('3')
    const labels = Array.from(block.querySelectorAll('dt')).map((n) => n.textContent)
    expect(labels).toEqual(['admin.scholarship.preInterview.reasons.not_b40', 'admin.scholarship.preInterview.reasons.results_too_low'])
    expect(Array.from(block.querySelectorAll('dd')).map((n) => n.textContent)).toEqual(['2', '1'])
  })

  it('is absent at zero', () => {
    draw({ total: 0, by_reason: { ...BY_REASON, not_b40: 0, results_too_low: 0 } })
    expect(screen.queryByTestId('overview-pre-interview')).toBeNull()
  })

  it('is absent when the payload carries no count (an older server)', () => {
    draw(undefined)
    expect(screen.getByTestId('overview-funnel')).toBeTruthy()
    expect(screen.queryByTestId('overview-pre-interview')).toBeNull()
  })
})
