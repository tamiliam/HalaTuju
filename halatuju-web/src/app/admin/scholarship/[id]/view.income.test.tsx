/**
 * @jest-environment jsdom
 *
 * WHAT THE OFFICER SEES WHEN A FAMILY SENDS SOMETHING THAT CANNOT CARRY THEIR INCOME.
 *
 * TD-262 chunks 2+3, findings W2 / W3 / W4. The cockpit's income panel decided evidence for
 * itself — `slip || epfDoc || supportFor(m)`, which is document PRESENCE — while the submission
 * gate asked whether the document could be READ. So a `not_salary` photo, a blank EPF and an
 * unbacked support letter each filled the earner's slot and the red *Missing* row never appeared,
 * about households the gate was holding shut. The panel now reads the SERVED per-earner answer
 * (`apps/scholarship/income_shown.py`), the same one the gate, the chase list and the AI verdict
 * read.
 *
 * Two rules are asserted here because both are easy to get wrong in the other direction:
 *   * an unusable document is STILL LISTED, marked not usable with its reason — the officer must
 *     see what the family sent, and a hidden document is a worse screen than a red one;
 *   * with NO served answer (an old or cached payload — the two services deploy together but not
 *     atomically) the panel falls back to the presence reading and never paints a screen of red.
 */
import { screen, within } from '@testing-library/react'

import { installCockpitConsoleGuard, renderCockpit } from '@/test/renderCockpit'
import { buildDocument } from '@/test/adminApplicationDetail'
import type { AdminApplicantDocument } from '@/lib/admin-api'
import type { IncomeShownAnswer, IncomeShownMap } from '@/lib/incomeShown'

installCockpitConsoleGuard()

const loaded = () => screen.findByText('Test Student 07')

const MISSING = 'admin.scholarship.docsDrawer.pill.missing'
const NOT_USABLE = 'admin.scholarship.docsDrawer.notUsable.label'
const REASON = (code: string) => `admin.scholarship.docsDrawer.notUsable.reason.${code}`
/** A row is addressed by its FILENAME: every member-tagged income document renders its
 *  label through the possessive key (`ofMember` / `parentIcOf`), so under the key-echoing `t`
 *  of this harness the labels are not distinguishable from one another. */
const FILE = (docType: string) => `test-${docType}.pdf`

/** The income group's block — its heading's parent holds every income row. */
const incomeBlock = (): HTMLElement => {
  const heading = screen.getByText('admin.scholarship.docsDrawer.group.income')
  const block = heading.parentElement
  if (!block) throw new Error('the income group heading has no block around it')
  return block
}

/** The father's IC, so the ONLY Missing row a test can produce is the income one. */
const fatherIc = () => buildDocument('parent_ic', { id: 400, household_member: 'father' })

/** The api's served answer for the father. */
const shownFor = (answer: Partial<IncomeShownAnswer>): IncomeShownMap => ({
  father: { shown: false, way: null, documents: [], unusable: [], ...answer },
})

describe('an unusable income document is listed, marked, and chased', () => {
  it('⚠ A not_salary PHOTO: listed, "not usable", and the red Missing row beside it', async () => {
    // Real student: application 73 — a MyKad photographed into the payslip slot. The gate emitted
    // `income_evidence_missing:father` while this panel showed the father satisfied.
    const slip = buildDocument('salary_slip', {
      id: 401, household_member: 'father',
      authenticity: { status: 'not_salary', reason: 'reads as a MyKad' },
    })
    renderCockpit({ role: 'super', stage: 'interviewing', build: {
      documents: [fatherIc(), slip],
      income_shown: shownFor({
        unusable: [{ doc_id: 401, doc_type: 'salary_slip', reason: 'not_salary' }] }),
    } })
    await loaded()
    const income = within(incomeBlock())
    expect(income.getByTitle(FILE('salary_slip'))).toBeTruthy()   // still listed
    expect(income.getByText(NOT_USABLE, { exact: false })).toBeTruthy()
    expect(income.getByText(REASON('not_salary'), { exact: false })).toBeTruthy()
    expect(income.getAllByText(MISSING)).toHaveLength(1)                // the income slot
  })

  it('⚠ A BLANK EPF: the same treatment — nothing could be read off it', async () => {
    const epf = buildDocument('epf', { id: 402, household_member: 'father' })
    renderCockpit({ role: 'super', stage: 'interviewing', build: {
      documents: [fatherIc(), epf],
      income_shown: shownFor({
        unusable: [{ doc_id: 402, doc_type: 'epf', reason: 'no_value' }] }),
    } })
    await loaded()
    const income = within(incomeBlock())
    expect(income.getByTitle(FILE('epf'))).toBeTruthy()
    expect(income.getByText(REASON('no_value'), { exact: false })).toBeTruthy()
    expect(income.getAllByText(MISSING)).toHaveLength(1)
  })

  it('a DECLARED amount + a letter that READ is evidence — no Missing row, no reason', async () => {
    // The owner's third way (2026-07-25). This household could submit and was chased for a payslip
    // it cannot produce (F1, application 144 / Janani); the panel now agrees it is evidenced.
    const letter = buildDocument('income_support_doc', { id: 403, household_member: 'father' })
    renderCockpit({ role: 'super', stage: 'interviewing', build: {
      documents: [fatherIc(), letter],
      income_shown: shownFor({ shown: true, way: 'declared_letter', documents: [403] }),
    } })
    await loaded()
    const income = within(incomeBlock())
    expect(income.getByTitle(FILE('income_support_doc'))).toBeTruthy()
    expect(income.queryByText(NOT_USABLE, { exact: false })).toBeNull()
    expect(income.queryByText(MISSING)).toBeNull()
  })

  it('⚠ AN STR HOUSEHOLD: the father is NOT evidenced, and no red row is drawn (F3)', async () => {
    // The owner, 2026-09-19: a current STR predicts green and the working adults' income proofs
    // are ADDITIONAL to it. So the per-earner answer stays FALSE for the father — a household STR
    // never ticks an earner — while the panel draws no red Missing row, because on an STR
    // household the salary documents are supportive, not required (owner 2026-07-05). The ask
    // survives as a SOFT Check-2 follow-up, which is exactly what F3 pins.
    const str = buildDocument('str', {
      id: 404, household_member: 'father',
      str_check: { current_status: 'current' } as AdminApplicantDocument['str_check'],
    })
    renderCockpit({ role: 'super', stage: 'interviewing', build: {
      income_route: 'str', income_earner: 'father',
      documents: [fatherIc(), str],
      income_shown: shownFor({}),      // shown: false — no STR arm, by the owner's ruling
    } })
    await loaded()
    const income = within(incomeBlock())
    expect(income.getByTitle(FILE('str'))).toBeTruthy()
    expect(income.queryByTitle(FILE('salary_slip'))).toBeNull()
    expect(income.queryByText(MISSING)).toBeNull()
    expect(income.queryByText(NOT_USABLE, { exact: false })).toBeNull()
  })

  it('⚠ NO SERVED ANSWER: the panel reads as it did before, and nothing breaks', async () => {
    // A cached payload, or an api revision behind the web one. The `not_salary` slip fills the
    // slot exactly as it used to — an absent answer means "we were not told", never "nothing is
    // evidenced". (The console guard in this file is the other half of the claim: no React
    // warning, no crash.)
    const slip = buildDocument('salary_slip', {
      id: 405, household_member: 'father',
      authenticity: { status: 'not_salary', reason: 'reads as a MyKad' },
    })
    renderCockpit({ role: 'super', stage: 'interviewing', build: {
      documents: [fatherIc(), slip],
    } })
    await loaded()
    const income = within(incomeBlock())
    expect(income.getByTitle(FILE('salary_slip'))).toBeTruthy()
    expect(income.queryByText(NOT_USABLE, { exact: false })).toBeNull()
    expect(income.queryByText(MISSING)).toBeNull()
  })
})
