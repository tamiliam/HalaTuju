/**
 * @jest-environment jsdom
 *
 * Request #64 — the exam year on the officer Academic card. STPM shows the STPM year beside the
 * merit only; a third-route student shows the SPM year
 * beside her SPM grades; an SPM-only student is unchanged (year beside the merit).
 */
import { render, screen } from '@testing-library/react'

import type { AdminScholarshipDetail } from '@/lib/admin-api'
import { ApplicantCards } from './ApplicantCards'
import type { T } from './shared'

const t = ((k: string, v?: Record<string, string>) => (v?.year ? `${k}:${v.year}` : k)) as unknown as T

const slip = { id: 1, doc_type: 'results_slip', academic_check: { exam_year: '2023', exam_year_status: 'off' } }
const higher = { id: 2, doc_type: 'higher_results', higher_check: { exam_year: '2025', exam_year_status: 'current' } }

function renderWith(extra: Record<string, unknown>) {
  const app = {
    status: 'shortlisted', qualification: 'spm', grades: {}, documents: [], guardians: [],
    consents: [], top_choices: [], chosen_pathway: '', chosen_programme: {},
    pathway_certainty: 'sure', pathways_considered: [], uncertainty_reasons: [],
    stpm_grades: {}, spm_prereq_grades: {}, merit_score: 90,
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

const dd = (label: string) => screen.getByText(label).parentElement?.querySelector('dd')?.textContent
const heading = (label: string) => screen.getByText(label, { exact: false }).textContent

it('STPM shows the STPM year by the merit only, never an SPM year by the STPM grades heading', () => {
  renderWith({ qualification: 'stpm', stpm_pngk: 3.7, documents: [slip, higher] })
  expect(dd('admin.scholarship.meritScore')).toContain('admin.scholarship.docsDrawer.stpmExamYear:2025')
  expect(heading('admin.scholarship.stpmGrades')).not.toContain('examYear')
  expect(dd('admin.scholarship.meritScore')).not.toContain('docsDrawer.examYear')
})

it('a third-route student shows the SPM year by her SPM grades, merit stays bare', () => {
  renderWith({ qualification: 'matric', overall_cgpa: 3.4, documents: [slip] })
  expect(heading('admin.scholarship.spmGrades')).toContain('admin.scholarship.docsDrawer.examYear:2023')
  expect(dd('admin.scholarship.meritScore')).toBe('90')
})

it('an SPM-only student is unchanged: year by the merit, none by the heading', () => {
  renderWith({ qualification: 'spm', documents: [slip] })
  expect(dd('admin.scholarship.meritScore')).toContain('admin.scholarship.docsDrawer.examYear:2023')
  expect(heading('admin.scholarship.spmGrades')).not.toContain('examYear')
})

it('an STPM student with no readable years shows bare merit', () => {
  renderWith({ qualification: 'stpm', stpm_pngk: 3.7, documents: [] })
  expect(dd('admin.scholarship.meritScore')).toBe('90')
})
