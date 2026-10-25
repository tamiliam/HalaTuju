/**
 * @jest-environment jsdom
 *
 * Request #45 (2026-10-25). Two faults on the Family & finances card, each pinned here as the
 * officer sees it:
 *
 *  1. The student's "About your family" answers were saved and served but shown nowhere — the
 *     card held only the parent CONTACT box, which officers took for the family.
 *  2. The tick beside the contact's name meant "some parent IC was read", not "this name is on an
 *     IC". On application 171 the IC was the father's and the contact name the mother's, and the
 *     tick showed. The ticks here come from the real `fieldVerifications`, not a stub.
 *
 * Every name below is invented.
 */
import { render, screen, within } from '@testing-library/react'

import type { AdminScholarshipDetail } from '@/lib/admin-api'
import { fieldVerifications, type VerifiableField } from '@/lib/fieldVerification'
import { ApplicantCards } from './ApplicantCards'
import type { T } from './shared'

// Key-echoing t that also shows its params, so a test can read "…declared{"amount":"900"}".
const t = ((k: string, p?: Record<string, unknown>) => (p ? `${k}${JSON.stringify(p)}` : k)) as unknown as T

const FATHER_IC = {
  id: 31, doc_type: 'parent_ic', household_member: 'father', vision_name: 'ARUNAN A/L KOVALAN',
  income_ic_check: { readable: true, member: 'father', name_status: 'match' },
}

function renderCard(extra: Partial<AdminScholarshipDetail> = {}) {
  const app = {
    status: 'interviewing', qualification: 'spm', grades: {}, documents: [], guardians: [],
    consents: [], top_choices: [], chosen_pathway: '', chosen_programme: {},
    pathways_considered: [], uncertainty_reasons: [],
    ...extra,
  } as unknown as AdminScholarshipDetail
  const fv = fieldVerifications(app)
  const vtip = (f: VerifiableField) => (fv[f] ? `tick:${fv[f]!.source}` : undefined)
  return render(
    <ApplicantCards
      app={app} t={t} vtip={vtip}
      incomeValue={null} incomeTip={undefined} incomeNote={undefined}
      sizeValue={null} sizeTip={undefined} sizeNote={undefined} sizeNoteTone="muted"
      perCapita={null}
    />,
  )
}

const section = () => within(screen.getByTestId('family-answers'))

describe('ApplicantCards — the student\'s family answers (request #45)', () => {
  it('lists each member with relationship, occupation, earning, declared income and why not working', () => {
    renderCard({
      father_name: 'ARUNAN A/L KOVALAN', father_occupation: 'unemployed',
      mother_name: 'MEENA A/P SELVAM', mother_occupation: 'hawker',
      other_family_members: [{ role: 'brother', occupation: 'other', occupation_other: 'Lorry helper' }],
      income_route: 'salary', income_working_members: ['mother', 'brother'],
      income_declared: { mother: 900 },
      income_nonearning: { father: { reason: 'Factory closed', since: '2025-03' } },
    })
    const s = section()
    expect(s.getByText('admin.scholarship.familyAnswers.title')).toBeTruthy()
    expect(s.getByText('scholarship.nextSteps.story.cardA.father')).toBeTruthy()
    expect(s.getByText('scholarship.nextSteps.story.cardA.prof.unemployed', { exact: false })).toBeTruthy()
    expect(s.getByText('scholarship.nextSteps.story.cardA.prof.hawker', { exact: false })).toBeTruthy()
    expect(s.getByText('Lorry helper', { exact: false })).toBeTruthy()
    // who earns: a badge on each working member, and the household line
    expect(s.getAllByText('admin.scholarship.familyAnswers.earns')).toHaveLength(2)
    expect(s.getByText(/scholarship\.nextSteps\.story\.cardA\.mother, scholarship\.nextSteps\.story\.cardA\.role\.brother/)).toBeTruthy()
    // the declared monthly wage and the non-earning reason + since
    expect(s.getByText('admin.scholarship.familyAnswers.declared{"amount":"900"}')).toBeTruthy()
    expect(s.getByText(/notWorkingSince\{"since":"03\/2025"\}/)).toBeTruthy()
    expect(s.getByText(/familyAnswers\.reason\{"reason":"Factory closed"\}/)).toBeTruthy()
  })

  it('names the single STR-route earner', () => {
    renderCard({ mother_occupation: 'cleaner', income_route: 'str', income_earner: 'mother' })
    expect(section().getAllByText('admin.scholarship.familyAnswers.earns')).toHaveLength(1)
  })

  it('says "Not filled in yet" when the student has not answered, with no earners line', () => {
    renderCard()
    expect(section().getByText('admin.scholarship.familyAnswers.notFilled')).toBeTruthy()
    expect(section().queryByText(/familyAnswers\.earners/)).toBeNull()
  })
})

describe('ApplicantCards — the parent contact line (request #45)', () => {
  it('labels the name as the parent CONTACT, and keeps the guardian wording for a non-parent', () => {
    const { unmount } = renderCard({ guardians: [{ name: 'MEENA A/P SELVAM', phone: '0123456789' }] })
    expect(screen.getByText('admin.scholarship.parentContactLabel')).toBeTruthy()
    expect(screen.queryByText('admin.scholarship.parentLabel')).toBeNull()
    unmount()
    renderCard({
      guardians: [{ name: 'X' }],
      consents: [{ is_active: true, granted_by: 'guardian', guardian_relationship: 'grandparent' }] as never,
    })
    expect(screen.getByText('admin.scholarship.guardianContactLabel')).toBeTruthy()
  })

  it('shows NO tick for the app-171 shape: the father\'s IC on file, the mother as the contact', () => {
    renderCard({
      guardians: [{ name: 'MEENA A/P SELVAM' }],
      documents: [FATHER_IC] as never,
      guardian_ic_name_match: [],               // the server matched nothing
    })
    expect(screen.queryByRole('img', { name: 'tick:parentIc' })).toBeNull()
  })

  it('shows the tick when the contact name matches a read parent IC', () => {
    renderCard({
      guardians: [{ name: 'ARUNAN A/L KOVALAN' }],
      documents: [FATHER_IC] as never,
      guardian_ic_name_match: [31],
    })
    expect(screen.getByRole('img', { name: 'tick:parentIc' })).toBeTruthy()
  })
})
