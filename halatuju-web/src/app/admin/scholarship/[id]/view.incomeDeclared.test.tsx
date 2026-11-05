/**
 * @jest-environment jsdom
 *
 * Request #54 (BrightPath) — the Household income card fell back to the student's own figure with no
 * label, hiding what the payslips add up to. DISPLAY ONLY: the stored figure and the scoring are
 * unchanged. The fallback is now named, and the documents' total is shown beside it.
 */
import { screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'

installCockpitConsoleGuard()

const income = (over: object) => ({
  household_check: {
    income: { documented_total: null, all_known: true, genuine: false, stated: 2000, matches: false, ...over },
    size: { described: 5, stated: 5, accounted: true, overcount: false, confirmed: false },
  },
})

describe('the household income card when the documents are not fully trusted', () => {
  it('names the declared figure and shows what the documents add up to', async () => {
    renderCockpit({ role: 'reviewer', stage: 'submitted', build: {
      household_income: 2000, ...income({ documented_partial: 5320 }) } })
    await screen.findByText('Test Student 07')
    expect(screen.getByText('RM 2,000')).toBeTruthy()
    expect(screen.getByText('admin.scholarship.verified.declaredByStudentDocs')).toBeTruthy()
  })

  it('still says the figure is the student\'s when nothing could be read', async () => {
    renderCockpit({ role: 'reviewer', stage: 'submitted', build: {
      household_income: 2000, ...income({ all_known: false, documented_partial: null }) } })
    await screen.findByText('Test Student 07')
    expect(screen.getByText('admin.scholarship.verified.declaredByStudent')).toBeTruthy()
  })
})
