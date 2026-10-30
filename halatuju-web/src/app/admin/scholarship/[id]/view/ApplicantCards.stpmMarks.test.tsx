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
  it('marks a differing grade with the document grade; a match no longer ticks its own chip', () => {
    // Owner, 2026-10-30: "to be consistent with SPM" — one tick for the set, never one per chip.
    renderStpm({ stpm_marks: {
      grades: { PA: { status: 'match', doc: 'A' }, PHYSICS: { status: 'differ', doc: 'B-' } },
      cgpa: 'differ', cgpa_doc: 3.42,
    } })
    expect(within(chip('PA')).queryByRole('img')).toBeNull()
    expect(within(chip('PHYSICS')).getByRole('img').getAttribute('title')).toBe(differs('B-'))
    expect(within(chip('MATH_T')).queryByRole('img')).toBeNull()       // not on the document
    // Not every subject matched (one differs, two unread), so no tick for the set either.
    expect(screen.queryAllByRole('img').filter((i) => i.getAttribute('title') === TICK)).toHaveLength(0)
  })

  it('ONE tick after the chips when every subject matches, as the SPM grades carry', () => {
    renderStpm({ stpm_marks: {
      grades: { PA: { status: 'match', doc: 'A' }, MATH_T: { status: 'match', doc: 'A-' },
        PHYSICS: { status: 'match', doc: 'B' }, CHEMISTRY: { status: 'match', doc: 'B+' } },
      cgpa: 'differ', cgpa_doc: 3.42,
    } })
    for (const k of ['PA', 'MATH_T', 'PHYSICS', 'CHEMISTRY']) {
      expect(within(chip(k)).queryByRole('img')).toBeNull()
    }
    expect(screen.queryAllByRole('img').filter((i) => i.getAttribute('title') === TICK)).toHaveLength(1)
  })

  it('ticks the SPM prerequisites once when the SPM slip matched (owner, 2026-10-30)', () => {
    const SLIP = 'Matches the results slip'
    const app = {
      status: 'profile_complete', qualification: 'stpm', grades: {}, documents: [], guardians: [],
      consents: [], top_choices: [], chosen_pathway: '', chosen_programme: {},
      pathway_certainty: 'sure', pathways_considered: [], uncertainty_reasons: [],
      stpm_grades: { PA: 'A' }, spm_prereq_grades: { BM: 'A', ENG: 'B' }, stpm_marks: null,
    } as unknown as AdminScholarshipDetail
    render(
      <ApplicantCards
        app={app} t={t} vtip={(f) => (f === 'grades' ? SLIP : undefined)}
        incomeValue={null} incomeTip={undefined} incomeNote={undefined}
        sizeValue={null} sizeTip={undefined} sizeNote={undefined} sizeNoteTone="muted"
        perCapita={null}
      />,
    )
    const prereq = screen.getByText('admin.scholarship.spmPrereq').parentElement as HTMLElement
    expect(within(prereq).getAllByRole('img').map((i) => i.getAttribute('title'))).toEqual([SLIP])
    // …and never on the STPM grades: that tick belongs to the SPM slip.
    expect(within(chip('PA')).queryByRole('img')).toBeNull()
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

  it('shows the school in capitals, however it was typed', () => {
    renderStpm({ school: 'sekolah menengah kebangsaan labuan' })
    expect(screen.getByText('SEKOLAH MENENGAH KEBANGSAAN LABUAN')).toBeTruthy()
  })

  it('never puts STPM marks on an SPM student', () => {
    renderStpm({ qualification: 'spm', grades: { bm: 'A' },
      stpm_marks: { grades: { bm: { status: 'match', doc: 'A' } }, cgpa: 'match', cgpa_doc: 3.5 } })
    expect(screen.queryAllByRole('img')).toHaveLength(0)
  })
})
