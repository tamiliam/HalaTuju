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

import { ResultsSlipChecklist } from './checklists'
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
