/**
 * @jest-environment jsdom
 *
 * Request #84 (2026-11-25): on the case page, a "working" tick the family details disagree with
 * shows a warning instead of a plain "Earns". The warnings are SERVED (`earner_tick_warnings`);
 * the card only looks them up. Every name below is invented.
 */
import { render, screen } from '@testing-library/react'

import type { AdminScholarshipDetail } from '@/lib/admin-api'
import { FamilyAnswers } from './FamilyAnswers'
import type { T } from './shared'

const t = ((k: string, p?: Record<string, unknown>) => (p ? `${k}${JSON.stringify(p)}` : k)) as unknown as T

const CASE_84 = {
  father_name: 'ARUNAN', father_occupation: 'factory', mother_name: 'MEENA', mother_occupation: 'unemployed',
  other_family_members: [], income_route: 'salary',
  income_working_members: ['father', 'mother', 'guardian', 'brother', 'sister'],
}

function renderIt(extra: Record<string, unknown> = {}) {
  const app = { ...CASE_84, ...extra } as unknown as AdminScholarshipDetail
  return render(<FamilyAnswers app={app} t={t} />)
}

describe('#84: a disagreeing tick warns instead of "Earns"', () => {
  it('the mother (listed, unemployed) gets a warning, the father keeps "Earns"', () => {
    renderIt({ earner_tick_warnings: [
      { member: 'mother', kind: 'not_working', occupation: 'unemployed' },
      { member: 'guardian', kind: 'not_listed' },
    ] })
    expect(screen.getByTestId('earner-tick-warning-mother').textContent).toContain(
      'admin.scholarship.familyAnswers.tickDisagrees{"status":"scholarship.nextSteps.story.cardA.prof.unemployed"}')
    // One "Earns" only: the father's. The mother's was replaced, not added to.
    expect(screen.getAllByText('admin.scholarship.familyAnswers.earns')).toHaveLength(1)
  })

  it('a ticked member the family details do not list gets its own line', () => {
    renderIt({ earner_tick_warnings: [{ member: 'guardian', kind: 'not_listed' }] })
    expect(screen.getByTestId('earner-tick-warning-guardian').textContent).toContain(
      'admin.scholarship.familyAnswers.tickNotListed{"role":"scholarship.nextSteps.story.cardA.role.guardian"}')
  })

  it('no served warnings (or an older api) = plain "Earns" for every listed ticked member', () => {
    renderIt()
    expect(screen.getAllByText('admin.scholarship.familyAnswers.earns')).toHaveLength(2)
    expect(screen.queryByTestId(/earner-tick-warning/)).toBeNull()
  })
})
