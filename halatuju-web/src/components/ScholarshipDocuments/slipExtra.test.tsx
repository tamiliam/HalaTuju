/**
 * @jest-environment jsdom
 *
 * REQUEST #62 — the STUDENT sees an entered subject the results slip does not show (rendered).
 *
 * Both readings come from the server: the checklist from `academic_check.extra`, the coach from
 * the help response's `extra_subjects` (`slip_coach.coach_detail`), so they cannot disagree. The
 * tone is "please check", never "you are wrong". `t` echoes its key.
 */
import { render, screen, waitFor } from '@testing-library/react'

import { ResultsSlipChecklist, SLIP_STATUSES, slipStatusLabelKey } from './checklists'
import enMessages from '@/messages/en.json'
import msMessages from '@/messages/ms.json'
import taMessages from '@/messages/ta.json'
import DocumentHelpCoach from '../DocumentHelpCoach'
import type { AcademicCheck, ApplicantDocument } from '@/lib/api'
import * as api from '@/lib/api'

jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  getDocumentHelp: jest.fn(),
}))
const mockApi = api as jest.Mocked<typeof api>

const t = (k: string) => k
/** Echoes every key but the coach's per-subject line, so the NAMED subject can be asserted. */
const tSubject = (k: string) => (k === 'scholarship.docs.help.extraSubject' ? 'entered {subject}, please check' : k)

const check = (over: Partial<AcademicCheck>): AcademicCheck => ({
  name: 'match', subjects: 'match', results: 'match', candidate_name: 'PRIYA',
  exam: '', exam_year: '', missing: [], extra: [], mismatched: [], uncertain: [], slip_count: 2,
  ...over,
})

const slipDoc = (academic: AcademicCheck, id = 401) => ({
  id, doc_type: 'results_slip', academic_check: academic, vision_run_at: null,
  vision_fields: { student_verdict: 'ok' },
}) as unknown as ApplicantDocument

describe('the results-slip checklist', () => {
  it('⚠ NAMES AN ENTERED SUBJECT THE SLIP DOES NOT SHOW, without a broken count', () => {
    render(<ResultsSlipChecklist doc={slipDoc(check({ subjects: 'mismatch', extra: ['Fizik'] }))} t={t} />)
    expect(screen.getByText('scholarship.docs.slipCheck.notOnSlip: Fizik')).toBeTruthy()
    expect(screen.queryByText(/\(2\/2\)/)).toBeNull()
  })

  it('shows missing AND extra together when both are served', () => {
    render(<ResultsSlipChecklist
      doc={slipDoc(check({ subjects: 'mismatch', missing: ['KIMIA'], extra: ['Fizik'] }))} t={t} />)
    expect(screen.getByText(
      'scholarship.docs.slipCheck.missing: KIMIA; scholarship.docs.slipCheck.notOnSlip: Fizik')).toBeTruthy()
    expect(screen.getByText(/\(1\/2\)/)).toBeTruthy()
  })
})

describe('the document coach', () => {
  beforeEach(() => {
    window.localStorage.clear()
    mockApi.getDocumentHelp.mockReset()
  })

  it('⚠ NAMES THE EXTRA SUBJECT AND LINKS TO THE GRADES PAGE', async () => {
    mockApi.getDocumentHelp.mockResolvedValue({
      message: '', source: 'fallback', verdict: 'slip_subjects_extra', extra_subjects: ['Fizik'] })
    render(<DocumentHelpCoach doc={slipDoc(check({ subjects: 'mismatch', extra: ['Fizik'] }), 402)}
                              token="tok" t={tSubject} lang="en" />)
    await waitFor(() => expect(screen.getByText('entered Fizik, please check')).toBeTruthy())
    expect(screen.getByText('scholarship.docs.help.fallback.slip_subjects_extra')).toBeTruthy()
    const link = screen.getByText('scholarship.docs.help.adjustGrades').closest('a')
    expect(link?.getAttribute('href')).toBe('/onboarding/grades')
  })
})

describe('request #62 review 2: nothing compared, nothing shown', () => {
  it('every slip status renders a real label in en/ms/ta, or nothing at all (never a raw key)', () => {
    const lookup = (m: unknown, key: string) =>
      key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown> | undefined)?.[k], m)
    for (const s of SLIP_STATUSES) {
      const key = slipStatusLabelKey(s)
      if (key === null) continue
      for (const m of [enMessages, msMessages, taMessages]) expect(typeof lookup(m, key)).toBe('string')
    }
    expect(slipStatusLabelKey('not_compared')).toBeNull()
  })

  it('a not-compared slip draws no Subjects or Results row and no badge key', () => {
    const { container } = render(
      <ResultsSlipChecklist doc={slipDoc(check({ subjects: 'not_compared', results: 'not_compared' }))} t={t} />)
    expect(container.textContent).not.toContain('not_compared')
    expect(screen.queryByText(/scholarship\.docs\.slipCheck\.subjects/)).toBeNull()
    expect(screen.queryByText(/scholarship\.docs\.slipCheck\.results/)).toBeNull()
    expect(screen.getByText(/scholarship\.docs\.slipCheck\.name/)).toBeTruthy()
  })
})
