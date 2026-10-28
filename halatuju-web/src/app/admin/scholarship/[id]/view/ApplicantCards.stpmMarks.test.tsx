/**
 * @jest-environment jsdom
 *
 * STPM CGPA C3 (owner 2026-10-28): the cockpit's STPM grade chips and CGPA are counter-checked
 * against the uploaded STPM results (served as `stpm_marks`). A match carries the same tick the SPM
 * grades carry ("Matches the STPM results"); a difference carries a marker whose hover names the
 * document's grade; no mark when the document has nothing to say. Rendered, not a source guard.
 */
import { render, screen, within } from '@testing-library/react'

import type { AdminScholarshipDetail } from '@/lib/admin-api'
import { ApplicantCards } from './ApplicantCards'
import type { T } from './shared'

const t = ((k: string, p?: Record<string, unknown>) =>
  (p && Object.keys(p).length ? `${k}|${Object.values(p).join('|')}` : k)) as unknown as T

const TICK = 'admin.scholarship.verified.tooltip|admin.scholarship.verified.source.stpmResults'
const differs = (v: string) => `admin.scholarship.verified.stpmDiffers|${v}`

function renderStpm(extra: Partial<AdminScholarshipDetail> = {}) {
  const app = {
    status: 'profile_complete', qualification: 'stpm', grades: {}, documents: [], guardians: [],
    consents: [], top_choices: [], chosen_pathway: '', chosen_programme: {},
    pathway_certainty: 'sure', pathways_considered: [], uncertainty_reasons: [],
    stpm_grades: { PA: 'A', MATH_T: 'A-', PHYSICS: 'B', CHEMISTRY: 'B+' }, stpm_pngk: 3.5,
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

const chip = (key: string) => screen.getByText(key.replace(/_/g, ' ')).parentElement as HTMLElement

describe('ApplicantCards — STPM check marks', () => {
  it('ticks a matching grade, marks a differing one with the document grade, leaves the rest bare', () => {
    renderStpm({ stpm_marks: {
      grades: { PA: { status: 'match', doc: 'A' }, PHYSICS: { status: 'differ', doc: 'B-' } },
      cgpa: 'match', cgpa_doc: 3.5,
    } })
    expect(within(chip('PA')).getByRole('img').getAttribute('title')).toBe(TICK)
    expect(within(chip('PHYSICS')).getByRole('img').getAttribute('title')).toBe(differs('B-'))
    expect(within(chip('MATH_T')).queryByRole('img')).toBeNull()       // not on the document
    expect(within(chip('CHEMISTRY')).queryByRole('img')).toBeNull()
  })

  it('ticks the CGPA when the document PNGK matches', () => {
    renderStpm({ stpm_marks: { grades: {}, cgpa: 'match', cgpa_doc: 3.5 } })
    const cgpa = screen.getByText('3.50').closest('dd') as HTMLElement
    expect(within(cgpa).getByRole('img').getAttribute('title')).toBe(TICK)
  })

  it('marks the CGPA with the document figure when it differs', () => {
    renderStpm({ stpm_marks: { grades: {}, cgpa: 'differ', cgpa_doc: 3.42 } })
    const cgpa = screen.getByText('3.50').closest('dd') as HTMLElement
    expect(within(cgpa).getByRole('img').getAttribute('title')).toBe(differs('3.42'))
  })

  it('labels a CGPA that could not be calculated, with no mark', () => {
    renderStpm({ stpm_marks: { grades: {}, cgpa: 'not_calculated', cgpa_doc: null } })
    const cgpa = screen.getByText('3.50').closest('dd') as HTMLElement
    expect(within(cgpa).getByText('(admin.scholarship.stpmCgpaNotCalculated)')).toBeTruthy()
    expect(within(cgpa).queryByRole('img')).toBeNull()
  })

  it('shows no marks at all without stpm_marks (no document, or an older api)', () => {
    renderStpm({ stpm_marks: null })
    expect(screen.queryAllByRole('img')).toHaveLength(0)
  })

  it('never puts STPM marks on an SPM student', () => {
    renderStpm({ qualification: 'spm', grades: { bm: 'A' },
      stpm_marks: { grades: { bm: { status: 'match', doc: 'A' } }, cgpa: 'match', cgpa_doc: 3.5 } })
    expect(screen.queryAllByRole('img')).toHaveLength(0)
  })
})
