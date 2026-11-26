/**
 * @jest-environment jsdom
 *
 * Academic box, owner mock 2026-11-24 + phone check 2026-11-25: the approved slot ROWS per route. The
 * exam and its year sit in brackets after the merit score, an empty required slot says N/A, the reporting date always shows, and a
 * programme / institution no offer letter confirms says "Stated by student".
 */
import { render, screen } from '@testing-library/react'

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
// The label of every slot, in document order - pins the row order.
const labels = () => Array.from(document.querySelectorAll('dt')).map((d) => d.textContent)
// A slot's row (marked `acad-row`). Only the plans row carries the one thin divider.
const rowOf = (label: string) => screen.getByText(label).closest('div.acad-row')

const slip = { doc_type: 'results_slip', academic_check: { exam_year: '2025', exam_year_status: 'current' } }
const higher = { doc_type: 'higher_results', higher_check: { exam_year: '2025', exam_year_status: 'current' } }

const SCHOOL = 'admin.scholarship.school'
const MERIT = 'admin.scholarship.meritScore'
const GRADES = 'admin.scholarship.spmGrades'
const PREREQ = 'admin.scholarship.spmPrereq'
const STPMG = 'admin.scholarship.stpmGrades'
const CGPA = 'admin.scholarship.cgpa'
const PRE_U = 'admin.scholarship.preUStudiedAt'   // pre-U sprint: where she COMPLETED it (board 6)
const PLANS = ['admin.scholarship.chosenProgramme', 'admin.scholarship.reportingDate', 'admin.scholarship.institution']
const slotOrder = () => labels().slice(labels().indexOf(SCHOOL), labels().indexOf(PLANS[2]) + 1)

describe('Academic box slots', () => {
  it('SPM: [school | merit] / SPM grades / [programme | reporting date] / institution, with "(SPM 2025)"', () => {
    renderWith({ merit_score: 54.2, school: 'smk abc', documents: [slip] })
    expect(slotOrder()).toEqual([SCHOOL, MERIT, GRADES, PLANS[0], PLANS[1], PLANS[2]])
    expect(dd(SCHOOL)).toBe('SMK ABC')
    expect(dd(MERIT)).toBe('54.2 (admin.scholarship.examName.spm 2025)')
    expect(rowOf(SCHOOL)).toBe(rowOf(MERIT))
    expect(rowOf(PLANS[0])).toBe(rowOf(PLANS[1]))
    expect(rowOf(SCHOOL)).not.toBe(rowOf(GRADES))
    expect(rowOf(GRADES)).not.toBe(rowOf(PLANS[0]))
    expect(rowOf(PLANS[0])).not.toBe(rowOf(PLANS[2]))
    const rows = Array.from(screen.getByText(SCHOOL).closest('dl')!.children)
    expect(rows).toHaveLength(4)
    // ONE divider only, above the plans (owner 2026-11-25); no row has its own padding.
    expect(rows.filter((r) => r.className.includes('border-t'))).toEqual([rowOf(PLANS[0])])
    for (const r of rows) expect(r.className).not.toMatch(/\bpy-/)
    for (const k of [CGPA, 'MUET', PRE_U, STPMG, PREREQ]) expect(screen.queryByText(k)).toBeNull()
  })

  it('STPM: [school] / [pre-U institution | merit] / [CGPA | MUET] / STPM grades / SPM prerequisites / plans', () => {
    renderWith({ qualification: 'stpm', merit_score: 92.5, stpm_pngk: 3.7, muet_band: 4, pre_u_studied_at: 'SMK Form Six',
      stpm_grades: { pa: 'A' }, spm_prereq_grades: { bm: 'B' }, documents: [higher, slip] })
    expect(slotOrder()).toEqual([SCHOOL, PRE_U, MERIT, CGPA, 'MUET', STPMG, PREREQ, PLANS[0], PLANS[1], PLANS[2]])
    expect(dd(MERIT)).toBe('92.5 (admin.scholarship.examName.stpm 2025)')
    expect(rowOf(SCHOOL)?.children).toHaveLength(1)     // the secondary school sits alone on a full row
    expect(rowOf(PRE_U)).toBe(rowOf(MERIT))
    expect(rowOf(CGPA)).toBe(rowOf('MUET'))
    expect(rowOf(STPMG)).not.toBe(rowOf(PREREQ))
    expect(dd(CGPA)).toBe('3.70')
    expect(dd('MUET')).toBe('4')
    expect(dd(PRE_U)).toBe('SMK FORM SIX')
  })

  it('an older STPM case with no pre-U field shows the typed Form 6 school (TD-734), with no note', () => {
    renderWith({ qualification: 'stpm', pre_u_institution: 'SMK Tingkatan Enam X' })
    expect(dd(PRE_U)).toBe('SMK TINGKATAN ENAM X')
  })

  it('Diploma: [school] / [pre-U institution | merit] / [CGPA | MUET] / SPM prerequisites / plans; bare 96.5, no bracket', () => {
    renderWith({ qualification: 'diploma', merit_score: 96.5, higher_cgpa: 3.86, muet_band: 3,
      pre_u_institution: 'Politeknik Z', pre_u_studied_at: 'Politeknik Ungku Omar', spm_prereq_grades: { bm: 'A' } })
    expect(slotOrder()).toEqual([SCHOOL, PRE_U, MERIT, CGPA, 'MUET', PREREQ, PLANS[0], PLANS[1], PLANS[2]])
    expect(dd(MERIT)).toBe('96.5')
    expect(rowOf(SCHOOL)).not.toBe(rowOf(PRE_U))
    expect(rowOf(SCHOOL)?.children).toHaveLength(1)
    expect(rowOf(PRE_U)).toBe(rowOf(MERIT))
    expect(rowOf(CGPA)).toBe(rowOf('MUET'))
    expect(dd(PRE_U)).toBe('POLITEKNIK UNGKU OMAR')
  })

  it('a third-route case with no pre-U field reads N/A: its typed pre_u_institution is the NEXT college', () => {
    renderWith({ qualification: 'diploma', pre_u_institution: 'Politeknik Z' })
    expect(dd(PRE_U)).toBe(NA)
  })

  it.each(['matric', 'asasi'])('%s has the same rows as Diploma, a bare merit (no year read)', (q) => {
    renderWith({ qualification: q, merit_score: 80, spm_prereq_grades: { bm: 'A' } })
    expect(slotOrder()).toEqual([SCHOOL, PRE_U, MERIT, CGPA, 'MUET', PREREQ, PLANS[0], PLANS[1], PLANS[2]])
    expect(dd(MERIT)).toBe('80')
  })

  // TD-735: a Matriculation / Asasi / Diploma transcript year, named by the qualification, never "SPM".
  it.each(['matric', 'asasi', 'diploma'])('%s with a transcript year read: "(<qualification> 2025)"', (q) => {
    renderWith({ qualification: q, merit_score: 80, documents: [higher, slip] })
    expect(dd(MERIT)).toBe(`80 (admin.scholarship.qualificationLabel.${q} 2025)`)
  })

  it('a third-route year off the expected sitting keeps the caution tint', () => {
    const off = { doc_type: 'higher_results', higher_check: { exam_year: '2023', exam_year_status: 'off' } }
    renderWith({ qualification: 'diploma', merit_score: 70, documents: [off] })
    expect(screen.getByText('(admin.scholarship.qualificationLabel.diploma 2023)').className).toContain('caution')
  })

  it('a third-route student never borrows the SPM slip year', () => {
    renderWith({ qualification: 'matric', merit_score: 80, documents: [slip] })
    expect(dd(MERIT)).toBe('80')
  })

  it('STPM without a read year shows the bare merit, no bracket', () => {
    renderWith({ qualification: 'stpm', merit_score: 92.5, stpm_pngk: 3.7, documents: [slip] })
    expect(dd(MERIT)).toBe('92.5')
  })

  it('an off-sitting year keeps its caution tint', () => {
    const off = { doc_type: 'results_slip', academic_check: { exam_year: '2023', exam_year_status: 'off' } }
    renderWith({ merit_score: 54.2, documents: [off] })
    expect(screen.getByText('(admin.scholarship.examName.spm 2023)').className).toContain('caution')
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

  it('a third-route student: the typed (next) college shows under Institution, the Pre-U institution row is N/A', () => {
    renderWith({ qualification: 'diploma', pre_u_institution: 'Politeknik Z', chosen_programme: {} })
    expect(dd(PRE_U)).toBe(NA)
    expect(dd('admin.scholarship.institution')).toBe('Politeknik Z')
  })

  it('an SPM student on the matriculation pathway: pre_u_institution is her destination, so Institution shows it', () => {
    renderWith({ qualification: 'spm', chosen_pathway: 'matric', pre_u_institution: 'Politeknik Pahang', chosen_programme: {} })
    expect(dd('admin.scholarship.institution')).toBe('Politeknik Pahang')
    expect(screen.getAllByText('admin.scholarship.statedByStudent').length).toBeGreaterThan(0)
  })
})
