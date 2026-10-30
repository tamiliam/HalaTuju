/**
 * @jest-environment jsdom
 *
 * Third results route S2b — the reviewer's Academic card for a Matriculation / Asasi / Diploma
 * holder: "Matriculation · CGPA 3.47" (the SERVER's overall CGPA — the same line the sponsor card
 * carries), the CGPA as printed and the co-curriculum score beside it (a Diploma: where it is
 * from, instead), the MUET band, the served 0-100 merit, and her SPM grades under an SPM label.
 * Never "MATRIC", never an STPM grade list, never the SPM exam year on a merit SPM did not produce.
 */
import { render, screen } from '@testing-library/react'

import type { AdminScholarshipDetail } from '@/lib/admin-api'
import { ApplicantCards } from './ApplicantCards'
import type { T } from './shared'

const t = ((k: string) => k) as unknown as T

function renderWith(extra: Partial<AdminScholarshipDetail> & Record<string, unknown>) {
  const app = {
    status: 'shortlisted', qualification: 'spm', grades: {}, documents: [], guardians: [],
    consents: [], top_choices: [], chosen_pathway: '', chosen_programme: {},
    pathway_certainty: 'sure', pathways_considered: [], uncertainty_reasons: [],
    stpm_grades: {}, spm_prereq_grades: {},
    ...extra,
  } as unknown as AdminScholarshipDetail
  return render(
    <ApplicantCards
      app={app} t={t} vtip={() => undefined}
      incomeValue={null} incomeTip={undefined} incomeNote={undefined}
      sizeValue={null} sizeTip={undefined} sizeNote={undefined} sizeNoteTone="muted"
      perCapita={null}
    />,
  )
}

const value = (label: string) =>
  screen.getByText(label).parentElement?.querySelector('dd')?.textContent

const MATRIC = {
  qualification: 'matric', merit_score: 86.75, overall_cgpa: 3.47, higher_cgpa: 3.5, higher_koko: 8,
  higher_institution_type: '', muet_band: 4, spm_prereq_grades: { bm: 'A', math: 'B+' },
}

it('names the qualification with the overall CGPA, and shows the merit as served', () => {
  renderWith(MATRIC)
  expect(value('admin.scholarship.heldResults')).toBe('admin.scholarship.qualificationLabel.matric · CGPA 3.47')
  expect(value('admin.scholarship.meritScore')).toBe('86.75')
  expect(value('admin.scholarship.higherCgpaEntered')).toBe('3.50')
  expect(value('admin.scholarship.higherKoko')).toBe('8')
  expect(value('MUET')).toBe('4')
  expect(screen.queryByText('admin.scholarship.stpmCgpa')).toBeNull()
  expect(screen.queryByText('admin.scholarship.stpmGrades')).toBeNull()
})

it('shows her SPM grades (the block) under the SPM label', () => {
  renderWith(MATRIC)
  expect(screen.getByText('admin.scholarship.spmGrades')).toBeTruthy()
  expect(screen.getByText(/B\+/)).toBeTruthy()
})

it('her SPM chips carry the slip tick, as an SPM student\'s do (owner, 2026-10-30)', () => {
  const app = {
    status: 'shortlisted', grades: {}, documents: [], guardians: [], consents: [], top_choices: [],
    chosen_pathway: '', chosen_programme: {}, pathway_certainty: 'sure', pathways_considered: [],
    uncertainty_reasons: [], stpm_grades: {}, ...MATRIC,
  } as unknown as AdminScholarshipDetail
  render(
    <ApplicantCards
      app={app} t={t} vtip={(f) => (f === 'grades' ? 'slip' : undefined)}
      incomeValue={null} incomeTip={undefined} incomeNote={undefined}
      sizeValue={null} sizeTip={undefined} sizeNote={undefined} sizeNoteTone="muted"
      perCapita={null}
    />,
  )
  expect(screen.getAllByRole('img').map((i) => i.getAttribute('title'))).toEqual(['slip'])
})

it('a Diploma shows where it is from and no co-curriculum score', () => {
  renderWith({ ...MATRIC, qualification: 'diploma', overall_cgpa: 2.8, higher_cgpa: 2.8,
    higher_koko: null, higher_institution_type: 'public', merit_score: 70 })
  expect(value('admin.scholarship.heldResults')).toBe('admin.scholarship.qualificationLabel.diploma · CGPA 2.80')
  expect(value('admin.scholarship.diplomaFrom')).toBe('admin.scholarship.diplomaInst.public')
  expect(screen.queryByText('admin.scholarship.higherKoko')).toBeNull()
})

it('an unusable CGPA shows the bare name, never a made-up figure', () => {
  renderWith({ ...MATRIC, qualification: 'asasi', overall_cgpa: null, merit_score: null })
  expect(value('admin.scholarship.heldResults')).toBe('admin.scholarship.qualificationLabel.asasi')
  expect(value('admin.scholarship.meritScore')).toBe('—')
})

it('SPM and STPM cards are untouched: no third-route lines', () => {
  renderWith({ qualification: 'stpm', merit_score: 92.5, stpm_pngk: 3.7 })
  expect(screen.queryByText('admin.scholarship.heldResults')).toBeNull()
  expect(screen.getByText('admin.scholarship.stpmCgpa')).toBeTruthy()
})
