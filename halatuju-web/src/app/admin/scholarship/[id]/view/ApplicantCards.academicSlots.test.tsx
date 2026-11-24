/**
 * @jest-environment jsdom
 *
 * Academic box, owner mock 2026-11-24: ONE slot layout for every route. The exam and its year sit
 * under the merit score, an empty required slot says N/A, the reporting date always shows, and a
 * programme / institution no offer letter confirms says "Stated by student".
 */
import { render, screen } from '@testing-library/react'

import type { AdminScholarshipDetail } from '@/lib/admin-api'
import { ApplicantCards } from './ApplicantCards'
import type { T } from './shared'

const t = ((k: string, p?: Record<string, string>) => (p?.year ? `${k}:${p.year}` : k)) as unknown as T
const NA = 'admin.scholarship.na'

function renderWith(extra: Record<string, unknown>, vtip: (f: string) => string | undefined = () => undefined) {
  const app = {
    status: 'shortlisted', qualification: 'spm', grades: { bm: 'A' }, documents: [], guardians: [],
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
const dd = (label: string) => screen.getByText(label).parentElement?.querySelector('dd')?.textContent
const sub = (label: string) => screen.getByText(label).parentElement?.querySelector('p')?.textContent

const slip = { doc_type: 'results_slip', academic_check: { exam_year: '2025', exam_year_status: 'current' } }
const higher = { doc_type: 'higher_results', higher_check: { exam_year: '2025', exam_year_status: 'current' } }

describe('Academic box slots', () => {
  it('SPM: secondary school, merit with "SPM <year>" under it, SPM grades, no CGPA / MUET / pre-U', () => {
    renderWith({ merit_score: 54.2, school: 'smk abc', documents: [slip] })
    expect(dd('admin.scholarship.school')).toBe('SMK ABC')
    expect(dd('admin.scholarship.meritScore')).toBe('54.2')
    expect(sub('admin.scholarship.meritScore')).toBe('admin.scholarship.examName.spm 2025')
    expect(screen.getByText('admin.scholarship.spmGrades')).toBeTruthy()
    for (const k of ['admin.scholarship.cgpa', 'MUET', 'admin.scholarship.preUInstitution',
      'admin.scholarship.stpmGrades', 'admin.scholarship.spmPrereq']) expect(screen.queryByText(k)).toBeNull()
  })

  it('STPM: the year comes from the higher-results document; STPM grades and SPM prerequisites rows; no pre-U row', () => {
    renderWith({ qualification: 'stpm', merit_score: 92.5, stpm_pngk: 3.7, muet_band: 4,
      stpm_grades: { pa: 'A' }, spm_prereq_grades: { bm: 'B' }, documents: [higher, slip] })
    expect(sub('admin.scholarship.meritScore')).toBe('admin.scholarship.examName.stpm 2025')
    expect(dd('admin.scholarship.cgpa')).toBe('3.70')
    expect(dd('MUET')).toBe('4')
    expect(screen.getByText('admin.scholarship.stpmGrades')).toBeTruthy()
    expect(screen.getByText('admin.scholarship.spmPrereq')).toBeTruthy()
    expect(screen.queryByText('admin.scholarship.preUInstitution')).toBeNull()
  })

  it('STPM without a read year shows the bare exam name', () => {
    renderWith({ qualification: 'stpm', merit_score: 92.5, stpm_pngk: 3.7, documents: [slip] })
    expect(sub('admin.scholarship.meritScore')).toBe('admin.scholarship.examName.stpm')
  })

  it('an off-sitting year keeps its caution tint', () => {
    const off = { doc_type: 'results_slip', academic_check: { exam_year: '2023', exam_year_status: 'off' } }
    renderWith({ merit_score: 54.2, documents: [off] })
    expect(screen.getByText('2023').className).toContain('caution')
  })

  it('an empty post-SPM slot reads N/A, not a dash', () => {
    renderWith({ qualification: 'stpm', merit_score: 92.5, stpm_pngk: 3.7, muet_band: null, school: '' })
    expect(dd('MUET')).toBe(NA)
    expect(dd('admin.scholarship.school')).toBe(NA)
    expect(screen.getAllByText(NA).length).toBeGreaterThan(2)
  })
})

describe('Plans rows', () => {
  it('the reporting date always shows: N/A when empty, the date when stored', () => {
    renderWith({})
    expect(dd('admin.scholarship.reportingDate')).toBe(NA)
    expect(dd('admin.scholarship.chosenProgramme')).toBe(NA)
    expect(dd('admin.scholarship.institution')).toBe(NA)
  })

  it('says "Stated by student" under a programme and institution no offer letter confirms', () => {
    renderWith({ chosen_programme: { course_name: 'Diploma Akaun', institution: 'Politeknik X' } })
    expect(screen.getAllByText('admin.scholarship.statedByStudent')).toHaveLength(2)
  })

  it('drops "Stated by student" once the offer letter confirms the value', () => {
    renderWith({ chosen_programme: { course_name: 'Diploma Akaun', institution: 'Politeknik X' } },
      (f) => (f === 'chosenProgramme' || f === 'institution' ? 'offer' : undefined))
    expect(screen.queryByText('admin.scholarship.statedByStudent')).toBeNull()
  })

  it('an institution copied off the offer letter itself is not "stated by student"', () => {
    const offer = { doc_type: 'offer_letter', pathway_check: { institution: 'Politeknik Y' } }
    renderWith({ chosen_programme: { course_name: 'Diploma Akaun' }, documents: [offer] })
    expect(screen.getAllByText('admin.scholarship.statedByStudent')).toHaveLength(1) // the programme only
  })

  it('a third-route student: her college shows under Pre-U institution, Institution stays N/A', () => {
    renderWith({ qualification: 'diploma', pre_u_institution: 'Politeknik Z', chosen_programme: {} })
    expect(dd('admin.scholarship.preUInstitution')).toBe('Politeknik Z')
    expect(dd('admin.scholarship.institution')).toBe(NA)
  })

  it('an SPM student on the matriculation pathway: pre_u_institution is her destination, so Institution shows it', () => {
    renderWith({ qualification: 'spm', chosen_pathway: 'matric', pre_u_institution: 'KM Pahang', chosen_programme: {} })
    expect(dd('admin.scholarship.institution')).toBe('KM Pahang')
    expect(screen.getAllByText('admin.scholarship.statedByStudent').length).toBeGreaterThan(0)
  })
})
