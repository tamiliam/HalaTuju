/**
 * @jest-environment jsdom
 *
 * Third results route S2b — the reviewer's Academic card for a Matriculation / Asasi / Diploma
 * holder: "Matriculation · CGPA 3.47" (the SERVER's overall CGPA — the same line the sponsor card
 * carries), the CGPA as printed and the co-curriculum score beside it (a Diploma: where it is
 * from, instead), the MUET band, the served 0-100 merit, and her SPM grades under "SPM prerequisites".
 * Never "MATRIC", never an STPM grade list, never the SPM exam year on a merit SPM did not produce.
 */
import { cleanup, render, screen } from '@testing-library/react'

import enMessages from '@/messages/en.json'
import type { AdminScholarshipDetail } from '@/lib/admin-api'
import { ApplicantCards } from './ApplicantCards'
import type { T } from './shared'

// The two merit-bracket templates are the REAL English ones; every other key stays a bare key.
const sch = (enMessages as unknown as { admin: { scholarship: Record<string, string> } }).admin.scholarship
const t = ((k: string, p?: Record<string, string>) => {
  const tpl = k === 'admin.scholarship.meritExam' ? sch.meritExam : null
  return tpl ? tpl.replace(/\{(\w+)\}/g, (_m, n) => p?.[n] ?? '') : k
}) as unknown as T

function renderWith(extra: Partial<AdminScholarshipDetail> & Record<string, unknown>,
  vtip: (f: string) => string | undefined = () => undefined) {
  const app = {
    status: 'shortlisted', qualification: 'spm', grades: {}, documents: [], guardians: [],
    consents: [], top_choices: [], chosen_pathway: '', chosen_programme: {},
    pathway_certainty: 'sure', pathways_considered: [], uncertainty_reasons: [],
    stpm_grades: {}, spm_prereq_grades: {},
    ...extra,
  } as unknown as AdminScholarshipDetail
  return render(
    <ApplicantCards
      app={app} t={t} vtip={vtip as never}
      incomeValue={null} incomeTip={undefined} incomeNote={undefined}
      sizeValue={null} sizeTip={undefined} sizeNote={undefined} sizeNoteTone="muted"
      perCapita={null}
    />,
  )
}

const value = (label: string) =>
  screen.getByText(label).parentElement?.querySelector('dd')?.textContent
const sub = (label: string) =>
  screen.getByText(label).parentElement?.querySelector('p')?.textContent ?? undefined

const MATRIC = {
  qualification: 'matric', merit_score: 86.75, overall_cgpa: 3.47, higher_cgpa: 3.5, higher_koko: 8,
  higher_institution_type: '', muet_band: 4, spm_prereq_grades: { bm: 'A', math: 'B+' },
}

it('shows the bare merit, no exam bracket (no year read), with ONE CGPA slot and the MUET band', () => {
  renderWith(MATRIC)
  expect(value('admin.scholarship.meritScore')).toBe('86.75')
  expect(sub('admin.scholarship.meritScore')).toBeUndefined()   // no grey line under it any more
  expect(screen.getAllByText('admin.scholarship.cgpa')).toHaveLength(1)
  expect(value('admin.scholarship.cgpa')).toBe('3.50')
  expect(value('MUET')).toBe('4')
  for (const gone of ['admin.scholarship.heldResults', 'admin.scholarship.higherCgpaEntered',
    'admin.scholarship.higherKoko', 'admin.scholarship.diplomaFrom', 'admin.scholarship.stpmCgpa',
    'admin.scholarship.stpmGrades']) expect(screen.queryByText(gone)).toBeNull()
})

const READ_DOC = (institution: string) => ({
  doc_type: 'higher_results', superseded_at: null, higher_check: { institution },
})

it('a Matriculation card shows the college read off the results, with the muted note and no tick (TD-734)', () => {
  renderWith({ ...MATRIC, documents: [READ_DOC('KOLEJ MATRIKULASI PAHANG')] } as never)
  expect(value('admin.scholarship.preUCollegeRead')).toBe('KOLEJ MATRIKULASI PAHANG')
  expect(screen.getByText('admin.scholarship.readFromResults')).toBeTruthy()
  expect(screen.queryByText('admin.scholarship.preUInstitution')).toBeNull()
  expect(screen.queryAllByRole('img')).toHaveLength(0)
})

it('with no college read, the slot says N/A and shows no note (the typed college is not shown there)', () => {
  renderWith({ ...MATRIC, pre_u_institution: 'KM Selangor' } as never)
  expect(value('admin.scholarship.preUCollegeRead')).toBe('admin.scholarship.na')
  expect(screen.queryByText('admin.scholarship.readFromResults')).toBeNull()
})

it('the typed college (the NEXT one) moves to the Institution row, Stated by student', () => {
  renderWith({ ...MATRIC, pre_u_institution: 'KM Selangor' } as never)
  expect(value('admin.scholarship.institution')).toBe('Kolej Matrikulasi Selangor')   // via expandMatricInstitution
  expect(screen.getAllByText('admin.scholarship.statedByStudent').length).toBeGreaterThan(0)
})

it('shows her SPM grades (the block) under "SPM prerequisites", as an STPM card names them (owner, 2026-11-16)', () => {
  renderWith(MATRIC)
  expect(screen.getByText('admin.scholarship.spmPrereq')).toBeTruthy()
  expect(screen.queryByText('admin.scholarship.spmGrades')).toBeNull()
  expect(screen.getByText(/B\+/)).toBeTruthy()
})

it('an SPM student keeps the plain "SPM grades" label', () => {
  renderWith({ qualification: 'spm', grades: { bm: 'A' } })
  expect(screen.getByText('admin.scholarship.spmGrades')).toBeTruthy()
  expect(screen.queryByText('admin.scholarship.spmPrereq')).toBeNull()
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

it('a Diploma: the bare merit, no bracket, no year, no "Diploma from" or co-curriculum line', () => {
  renderWith({ ...MATRIC, qualification: 'diploma', overall_cgpa: 2.8, higher_cgpa: 2.8,
    higher_koko: null, higher_institution_type: 'public', merit_score: 70 })
  expect(value('admin.scholarship.meritScore')).toBe('70')
  expect(value('admin.scholarship.cgpa')).toBe('2.80')
  expect(screen.getByText('admin.scholarship.preUCollegeRead')).toBeTruthy()
  expect(screen.queryByText('admin.scholarship.diplomaFrom')).toBeNull()
  expect(screen.queryByText('admin.scholarship.higherKoko')).toBeNull()
})

it('an unusable merit and CGPA read N/A, never a made-up figure', () => {
  renderWith({ ...MATRIC, qualification: 'asasi', overall_cgpa: null, merit_score: null, higher_cgpa: null })
  expect(value('admin.scholarship.meritScore')).toBe('admin.scholarship.na')
  expect(value('admin.scholarship.cgpa')).toBe('admin.scholarship.na')
})

it('an STPM card has one CGPA slot, the MUET band and no Pre-U institution row', () => {
  renderWith({ qualification: 'stpm', merit_score: 92.5, stpm_pngk: 3.7 })
  expect(screen.getAllByText('admin.scholarship.cgpa')).toHaveLength(1)
  expect(screen.queryByText('admin.scholarship.preUInstitution')).toBeNull()
  expect(screen.getByText('admin.scholarship.stpmGrades')).toBeTruthy()
})

// Request #62, owner 2026-11-06: three exclusive routes. A third-route student's SPM chips are her
// SPM prereq ONLY — an earlier SPM-page entry in `grades` is never drawn, never merged over it.
it('draws only her SPM prereq, never her earlier `grades` (three exclusive routes)', () => {
  renderWith({ ...MATRIC, grades: { math: 'D', eng: 'C' } })
  expect(screen.getByText('math')).toBeTruthy()
  expect(screen.getByText('B+')).toBeTruthy()          // the prereq's Matematik, not `grades`' D
  expect(screen.queryByText('D')).toBeNull()
  expect(screen.queryByText('eng')).toBeNull()          // a subject only in `grades` is not drawn
  expect(screen.queryByText('C')).toBeNull()
})

it('no SPM prereq: no SPM chips at all, even with an earlier `grades` entry', () => {
  renderWith({ ...MATRIC, spm_prereq_grades: {}, grades: { math: 'D' } })
  expect(screen.queryByText('math')).toBeNull()
  expect(screen.queryByText('D')).toBeNull()
})

it("draws the student's results notes and never the team's (owner 2026-11-06)", () => {
  // The server serves the student's notes only (`results_route.cockpit_notes`); an old cached
  // payload's team split has no line on this card any more.
  renderWith({ ...MATRIC, results_change_notes: [
    { at: '2026-10-26T00:00:00', kind: 'refiled_higher', by: 'student', results_kind: 'matric' },
    { at: '2026-10-28T00:00:00', kind: 'team_split', by: 'team', slot: 'results_slip', pages: [1] },
  ] } as never)
  const notes = screen.getAllByTestId('results-change-note').map((p) => p.textContent)
  expect(notes).toEqual(['admin.scholarship.resultsChanged.refiledHigher'])
  expect(screen.queryByText(/teamSplit|Team/)).toBeNull()
})

it('ticks the CGPA entered when the uploaded results read the same CGPA, and only it (owner 2026-11-06)', () => {
  renderWith(MATRIC, (f) => (f === 'higherCgpa' ? 'Matches the uploaded results' : undefined))
  const cgpa = screen.getByText('admin.scholarship.cgpa').parentElement as HTMLElement
  expect(cgpa.querySelector('[title="Matches the uploaded results"]')).not.toBeNull()
})

it('no CGPA tick without a matching read', () => {
  renderWith(MATRIC)
  const cgpa = screen.getByText('admin.scholarship.cgpa').parentElement as HTMLElement
  expect(cgpa.querySelector('[title]')).toBeNull()
})
