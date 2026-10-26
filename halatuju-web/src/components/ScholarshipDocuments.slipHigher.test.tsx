/**
 * @jest-environment jsdom
 *
 * THIRD RESULTS ROUTE S4 — a HIGHER result in the SPM card, rendered (2026-10-27; #43, rulings D12
 * D15). The server reads the SPM card's document as STPM / Matriculation / Asasi / Diploma results
 * (`academic_check.higher_kind`) and says whether the move is on offer (`move_offered`: the higher
 * card is shown, and not yet submitted). This file asserts the card obeys it, with a real click:
 *   - the note "This appears to be your STPM results …" and "Move it to STPM results" → re-filed;
 *   - after submit the note offers no action; where no higher card is shown, nothing is said;
 *   - NEVER the SPM checklist (no "missing subjects", no "you typed / slip says") on such a document.
 * `t` echoes its key, so assertions read against i18n keys rather than English copy.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ScholarshipDocuments from './ScholarshipDocuments'
import type { AcademicCheck, ApplicantDocument, ApplicationRequirements, ScholarshipApplication } from '@/lib/api'
import { sandboxApplication } from '@/sandbox/fixtures/scholarship'
import * as api from '@/lib/api'
import * as documentsApi from '@/lib/api/documents'

jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn() }) }))
jest.mock('@/lib/api/documents', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api/documents'),
  refileToHigher: jest.fn(),
}))
jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  listDocuments: jest.fn(),
  getConsentStatus: jest.fn(),
}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k, locale: 'en' }),
}))
jest.mock('./DocumentHelpCoach', () => ({ __esModule: true, default: () => null }))
jest.mock('./IncomeClusterCoach', () => ({ __esModule: true, default: () => null }))

const mockApi = api as jest.Mocked<typeof api>
const mockDocs = documentsApi as jest.Mocked<typeof documentsApi>

const DEGREE_STPM: ApplicationRequirements = {
  documents: { required: ['ic', 'higher_results', 'offer_letter'], optional: ['results_slip'] },
}
const app = { ...sandboxApplication, requirements: DEGREE_STPM, exam_type: 'stpm' } as ScholarshipApplication

const HIGHER_IN_SPM_CARD: AcademicCheck = {
  name: 'match', subjects: 'not_spm', results: 'not_spm', candidate_name: 'PRIYA',
  exam: 'MALAYSIA HIGHER SCHOOL CERTIFICATE 2025', exam_year: '', exam_year_status: '',
  missing: [], mismatched: [], uncertain: [], slip_count: 0,
  higher_kind: 'stpm', move_offered: true, actions_open: true,
}

const slip = (chk: Partial<AcademicCheck>): ApplicantDocument => ({
  id: 77, doc_type: 'results_slip', household_member: '', original_filename: 'stpm.pdf',
  academic_check: { ...HIGHER_IN_SPM_CARD, ...chk },
} as unknown as ApplicantDocument)

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getConsentStatus.mockResolvedValue({ is_minor: false, consents: [] } as unknown as api.ConsentStatus)
  mockDocs.refileToHigher.mockResolvedValue({ status: 'refiled', results_kind: 'stpm' })
})

const mount = async () => {
  render(<ScholarshipDocuments token="t" app={app} />)
  await waitFor(() => expect(screen.getByText('scholarship.docs.section.identity.title')).toBeTruthy())
}

describe('D15: "Move it to STPM results"', () => {
  it('says what the document is and moves it in one tap, then refreshes the cards', async () => {
    mockApi.listDocuments.mockResolvedValue({ documents: [slip({})] })
    await mount()
    expect(await screen.findByText('documentsTab.higher.note.slipIsHigher')).toBeTruthy()
    const before = mockApi.listDocuments.mock.calls.length
    fireEvent.click(screen.getByText('documentsTab.higher.moveToHigher'))
    await waitFor(() => expect(mockDocs.refileToHigher).toHaveBeenCalledWith(77, { token: 't' }))
    await waitFor(() => expect(mockApi.listDocuments.mock.calls.length).toBeGreaterThan(before))
  })

  it('never shows the SPM comparison on a higher result', async () => {
    mockApi.listDocuments.mockResolvedValue({ documents: [slip({})] })
    await mount()
    await screen.findByText('documentsTab.higher.note.slipIsHigher')
    expect(screen.queryByText(/scholarship\.docs\.slipCheck\./)).toBeNull()
  })

  it('after submit the note offers no action (the server refuses it too)', async () => {
    mockApi.listDocuments.mockResolvedValue({ documents: [slip({ actions_open: false })] })
    await mount()
    expect(await screen.findByText('documentsTab.higher.note.slipIsHigher')).toBeTruthy()
    expect(screen.queryByText('documentsTab.higher.moveToHigher')).toBeNull()
  })

  it('where the page shows no higher card (D12) the student is told nothing here', async () => {
    mockApi.listDocuments.mockResolvedValue({ documents: [slip({ move_offered: false })] })
    await mount()
    await waitFor(() => expect(mockApi.listDocuments).toHaveBeenCalled())
    await new Promise((r) => setTimeout(r, 30))
    expect(screen.queryByText('documentsTab.higher.note.slipIsHigher')).toBeNull()
    expect(screen.queryByText(/scholarship\.docs\.slipCheck\./)).toBeNull()
  })

  it('an SPM slip keeps its usual checklist', async () => {
    mockApi.listDocuments.mockResolvedValue({ documents: [slip({
      higher_kind: '', subjects: 'match', results: 'pending', slip_count: 9 })] })   // not 'done', so open
    await mount()
    expect(await screen.findByText(/scholarship\.docs\.slipCheck\.name/)).toBeTruthy()
    expect(screen.queryByText('documentsTab.higher.note.slipIsHigher')).toBeNull()
  })
})
