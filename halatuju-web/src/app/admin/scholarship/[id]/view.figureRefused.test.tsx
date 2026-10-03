/**
 * @jest-environment jsdom
 *
 * A CHIP MAY NOT BE GREEN ON A FIGURE THE ENGINE THREW AWAY — Later-tier batch 1 (2026-10-03).
 *
 *   · TD-323 — the income engine refuses a payslip amount that is inconsistent (net > gross) or
 *     outside RM100–20,000 a month, and (since this batch) an EPF statement whose implied salary
 *     falls under the RM100 floor (no ceiling). The api SERVES that refusal, officer-only, as the document's `figure_refused`
 *     (`income_engine/salary_figures.py`); the drawer colours the chip from it and never re-derives
 *     the window. A refused figure shows an amber "looks misread" chip; an accepted one stays green.
 *   · TD-320 — an EPF statement whose identity was read exactly and whose contribution figures came
 *     from Gemini carries `capture: 'mixed'` and the badge says "Exact + AI", not "AI".
 *
 * `t` echoes its key (the cockpit harness), so the drawer is read by key.
 */
import { screen } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import { buildDocument } from '@/test/adminApplicationDetail'
import type { IncomeProofCheck } from '@/lib/api'
import enMessages from '@/messages/en.json'
import msMessages from '@/messages/ms.json'
import taMessages from '@/messages/ta.json'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')
const FACT = (k: string) => `admin.scholarship.docsDrawer.fact.${k}`
const proof = (points: IncomeProofCheck['points']): IncomeProofCheck => ({
  name: 'RAVI', nric: '', name_status: 'match', nric_status: 'no_ref', member: 'father',
  ic_present: true, points,
})
const refused = (figure_refused?: boolean) => (figure_refused === undefined ? {} : { figure_refused })
const one = (doc: ReturnType<typeof buildDocument>) =>
  renderCockpit({ role: 'super', stage: 'interviewing', build: { documents: [doc] } })

describe('TD-323 — the payslip Amount chip follows the engine', () => {
  it('a refused amount is amber "looks misread", and the green Amount chip is gone', async () => {
    one(buildDocument('salary_slip', { id: 501, household_member: 'father',
      ...refused(true), income_proof_check: proof([{ key: 'amount', value: 'RM 32,600.00' }]) }))
    await loaded()
    const chip = screen.getByText(FACT('amount_unusable'))
    expect(chip.className).not.toMatch(/positive/)
    expect(screen.queryByText(FACT('amount'))).toBeNull()
  })

  it('an accepted amount stays green — and so does an older payload with no refusal field', async () => {
    for (const [id, was] of [[502, false], [503, undefined]] as const) {
      const { unmount } = one(buildDocument('salary_slip', { id, household_member: 'father',
        ...refused(was), income_proof_check: proof([{ key: 'amount', value: 'RM 1,800.00' }]) }))
      await loaded()
      expect(screen.getByText(FACT('amount')).className).toMatch(/positive/)
      expect(screen.queryByText(FACT('amount_unusable'))).toBeNull()
      unmount()
    }
  })
})

describe('TD-323 — the EPF Contribution chip follows the engine', () => {
  it('a refused estimate is amber "looks misread"; an accepted one is green', async () => {
    const { unmount } = one(buildDocument('epf', { id: 504, household_member: 'father',
      ...refused(true), income_proof_check: proof([{ key: 'avgContribution', value: 'RM 9.00' }]) }))
    await loaded()
    expect(screen.getByText(FACT('contribution_unusable')).className).not.toMatch(/positive/)
    expect(screen.queryByText(FACT('contribution'))).toBeNull()
    unmount()
    one(buildDocument('epf', { id: 505, household_member: 'father',
      ...refused(false), income_proof_check: proof([{ key: 'avgContribution', value: 'RM 480.00' }]) }))
    await loaded()
    expect(screen.getByText(FACT('contribution')).className).toMatch(/positive/)
  })
})

describe('TD-320 — a mixed EPF capture says both halves', () => {
  it('the badge reads the mixed label, never the all-AI one', async () => {
    one(buildDocument('epf', { id: 506, household_member: 'father',
      vision_fields: { fields: { name: 'RAVI' }, capture: 'mixed' },
      income_proof_check: proof([]) }))
    await loaded()
    expect(screen.getByText('admin.scholarship.docsDrawer.capture.mixed.label')).toBeTruthy()
    expect(screen.queryByText('admin.scholarship.docsDrawer.capture.ai.label')).toBeNull()
  })

  it('every language carries the three new labels', () => {
    for (const m of [enMessages, msMessages, taMessages]) {
      const d = m.admin.scholarship.docsDrawer
      expect(d.capture.mixed.label).toBeTruthy()
      expect(d.capture.mixed.hint).toBeTruthy()
      expect(d.fact.amount_unusable).toBeTruthy()
      expect(d.fact.contribution_unusable).toBeTruthy()
    }
  })
})
