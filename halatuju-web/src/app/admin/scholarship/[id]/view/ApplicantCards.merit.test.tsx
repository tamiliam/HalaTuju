/**
 * @jest-environment jsdom
 *
 * Third results route S1 (2026-10-25): every route ranks on ONE 0-100 merit, served by the api
 * (`exam_questions.merit_100`; STPM = overall CGPA / 4 x 100). The cockpit shows the served figure
 * as it is — never re-derived here — and its label says the scale, in all three languages, so a
 * reviewer never reads 92.5 as a CGPA or 3.7 as a merit. The list column says the same.
 */
import { render, screen } from '@testing-library/react'

import enMessages from '@/messages/en.json'
import msMessages from '@/messages/ms.json'
import taMessages from '@/messages/ta.json'
import type { AdminScholarshipDetail } from '@/lib/admin-api'
import { ApplicantCards } from './ApplicantCards'
import type { T } from './shared'

// The two merit-bracket templates are the REAL English ones; every other key stays a bare key.
const sch = (enMessages as unknown as { admin: { scholarship: Record<string, string> } }).admin.scholarship
const t = ((k: string, p?: Record<string, string>) => {
  const tpl = k === 'admin.scholarship.meritExam' ? sch.meritExam
    : k === 'admin.scholarship.meritExamNoYear' ? sch.meritExamNoYear : null
  return tpl ? tpl.replace(/\{(\w+)\}/g, (_m, n) => p?.[n] ?? '') : k
}) as unknown as T

function renderWith(extra: Partial<AdminScholarshipDetail>) {
  const app = {
    status: 'shortlisted', qualification: 'spm', grades: {}, documents: [], guardians: [],
    consents: [], top_choices: [], chosen_pathway: '', chosen_programme: {},
    pathway_certainty: 'sure', pathways_considered: [], uncertainty_reasons: [],
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

function meritValue() {
  const dt = screen.getByText('admin.scholarship.meritScore')
  return dt.parentElement?.querySelector('dd')?.textContent
}

describe('ApplicantCards — merit on one 0-100 scale', () => {
  it('shows an STPM holder the served 0-100 figure, not the PNGK', () => {
    renderWith({ qualification: 'stpm', merit_score: 92.5, stpm_pngk: 3.7 })
    expect(meritValue()).toBe('92.5 (admin.scholarship.examName.stpm)')
  })

  it('shows an SPM holder the served figure unchanged', () => {
    renderWith({ qualification: 'spm', merit_score: 54.2 })
    expect(meritValue()).toBe('54.2 (admin.scholarship.examName.spm)')
  })

  it('keeps the STPM CGPA on its own line, since the merit no longer carries it', () => {
    renderWith({ qualification: 'stpm', merit_score: 92.5, stpm_pngk: 3.7 })
    const dt = screen.getByText('admin.scholarship.cgpa')
    expect(dt.parentElement?.querySelector('dd')?.textContent).toBe('3.70')
  })

  it('shows no CGPA line for an SPM holder', () => {
    renderWith({ qualification: 'spm', merit_score: 54.2 })
    expect(screen.queryByText('admin.scholarship.cgpa')).toBeNull()
  })

  it('shows an absent merit as N/A, never 0 (#106)', () => {
    renderWith({ qualification: 'stpm', merit_score: null, stpm_pngk: null })
    expect(meritValue()).toBe('admin.scholarship.na')
  })
})

describe('the merit label is just "Merit score" and its bracket is a template, in every language', () => {
  it.each([
    ['en', enMessages, 'Merit score'], ['ms', msMessages, 'Skor merit'], ['ta', taMessages, 'தகுதி மதிப்பெண்'],
  ] as const)('%s', (_lang, messages, label) => {
    const s = (messages as unknown as { admin: { scholarship: Record<string, string> } })
      .admin.scholarship
    expect(s.meritScore).toBe(label)        // cockpit card: no "(out of 100)" any more (owner 2026-11-25)
    expect(s.meritExam).toContain('{exam}') // "(SPM 2024)"
    expect(s.meritExam).toContain('{year}')
    expect(s.meritExamNoYear).toContain('{exam}')
    expect(s.meritExamNoYear).not.toContain('{year}')
    expect(s.merit).toContain('100')        // applicant list column + mobile card
  })
})
