/**
 * @jest-environment jsdom
 *
 * THIRD RESULTS ROUTE S3a + S3b — the higher-results card, rendered (2026-10-26, rulings D9 D12 D13).
 *
 * What is drawn follows the SERVER's per-applicant answer on the payload (D12) — this file never
 * decides it, it asserts the cards obey it. Then the card itself: the read-only "Type of results ·
 * Change" line (D13: no picker), the one-line read, and the ONE note with its one action, each
 * driven by a real click (the lessons' rule: a source-shape guard is not evidence for behaviour).
 * `t` echoes its key, so assertions read against i18n keys rather than English copy.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ScholarshipDocuments from './ScholarshipDocuments'
import type { ApplicantDocument, ApplicationRequirements, HigherCheck, ScholarshipApplication } from '@/lib/api'
import { sandboxApplication } from '@/sandbox/fixtures/scholarship'
import * as api from '@/lib/api'
import { KEY_RESULTS_EXAM_TYPE, KEY_STPM_CGPA, KEY_STPM_GRADES } from '@/lib/storage'

const push = jest.fn()
jest.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))
jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  listDocuments: jest.fn(),
  getConsentStatus: jest.fn(),
  refileToSpm: jest.fn(),
  continueWithSpmOnly: jest.fn(),
}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string) => k, locale: 'en' }),
}))
jest.mock('./DocumentHelpCoach', () => ({ __esModule: true, default: () => null }))
jest.mock('./IncomeClusterCoach', () => ({ __esModule: true, default: () => null }))

const mockApi = api as jest.Mocked<typeof api>

const DEGREE_STPM: ApplicationRequirements = {
  documents: { required: ['ic', 'higher_results', 'offer_letter'], optional: ['results_slip'] },
}
const POST_SPM: ApplicationRequirements = {
  documents: { required: ['ic', 'results_slip', 'offer_letter'], optional: [] },
}

const appWith = (requirements: ApplicationRequirements, exam_type = 'stpm'): ScholarshipApplication =>
  ({ ...sandboxApplication, requirements, exam_type } as ScholarshipApplication)

const CLEAN: HigherCheck = {
  name: 'match', candidate_name: 'PRIYA', exam: 'SIJIL TINGGI PERSEKOLAHAN MALAYSIA', kind_held: 'stpm',
  kind_detected: 'stpm', kind_status: 'match', cgpa_slip: 3.67, cgpa_entered: 3.67,
  cgpa_status: 'match', grades_status: 'match', missing: [], mismatched: [], readable: true,
  note: '', note_kind: '', note_path: '',
}

const higherDoc = (chk: Partial<HigherCheck>): ApplicantDocument => ({
  id: 41, doc_type: 'higher_results', household_member: '', original_filename: 'results.pdf',
  results_kind: 'stpm', higher_check: { ...CLEAN, ...chk },
} as unknown as ApplicantDocument)

beforeEach(() => {
  jest.clearAllMocks()
  localStorage.clear()
  mockApi.listDocuments.mockResolvedValue({ documents: [] })
  mockApi.getConsentStatus.mockResolvedValue({ is_minor: false, consents: [] } as unknown as api.ConsentStatus)
  mockApi.refileToSpm.mockResolvedValue({ status: 'refiled' })
  mockApi.continueWithSpmOnly.mockResolvedValue({ status: 'cleared', cleared: 'stpm', refiled: true })
})

const mount = async (app: ScholarshipApplication) => {
  render(<ScholarshipDocuments token="t" app={app} />)
  await waitFor(() => expect(screen.getByText('scholarship.docs.section.identity.title')).toBeTruthy())
}

describe('D12: the cards follow the server\'s answer', () => {
  it('a university-bound STPM applicant sees the higher card (required) and an optional SPM slip', async () => {
    await mount(appWith(DEGREE_STPM))
    expect(screen.getByText('scholarship.docs.type.higher_results')).toBeTruthy()
    expect(screen.getByText('documentsTab.help.higher_results')).toBeTruthy()
    expect(screen.getByText('scholarship.docs.type.results_slip')).toBeTruthy()
    expect(screen.getByText('documentsTab.help.results_slip_optional')).toBeTruthy()
    // the read-only type line, from the results held (D13: no picker)
    expect(await screen.findByText(/documentsTab\.higher\.typeLabel/)).toBeTruthy()
    expect(screen.getByText('documentsTab.higher.kind.stpm')).toBeTruthy()
    expect(screen.queryByRole('combobox')).toBeNull()
  })

  it('a post-SPM pathway shows only the SPM slip, with its usual help', async () => {
    await mount(appWith(POST_SPM))
    expect(screen.queryByText('scholarship.docs.type.higher_results')).toBeNull()
    expect(screen.getByText('scholarship.docs.help.results_slip')).toBeTruthy()
    expect(screen.queryByText('documentsTab.help.results_slip_optional')).toBeNull()
  })

  it('owner ruling: SPM only + a degree → both cards required, with why and the two ways out', async () => {
    const BOTH: ApplicationRequirements = {
      documents: { required: ['ic', 'higher_results', 'results_slip', 'offer_letter'], optional: [] },
    }
    await mount(appWith(BOTH, 'spm'))
    expect(await screen.findByText('documentsTab.higher.spmOnlyHelp')).toBeTruthy()
    expect(screen.getByText('scholarship.docs.help.results_slip')).toBeTruthy()      // SPM slip required, usual help
    fireEvent.click(screen.getByText('documentsTab.higher.updateResults'))
    expect(push).toHaveBeenCalledWith('/onboarding/exam-type')
    fireEvent.click(screen.getByText('documentsTab.higher.choosePathway'))
    expect(push).toHaveBeenCalledWith('/profile#pathway')
  })

  it('"Change" opens the results page and returns to the application', async () => {
    await mount(appWith(DEGREE_STPM, 'diploma'))
    fireEvent.click(await screen.findByText('documentsTab.higher.change'))
    expect(push).toHaveBeenCalledWith('/onboarding/higher-grades')
  })
})

describe('D13: the one-line read and the one note', () => {
  it('a clean read says so in one line, with no note', async () => {
    mockApi.listDocuments.mockResolvedValue({ documents: [higherDoc({})] })
    await mount(appWith(DEGREE_STPM))
    expect(await screen.findByText('documentsTab.higher.readOk')).toBeTruthy()
    expect(screen.queryByText('documentsTab.higher.moveToSpm')).toBeNull()
  })

  it('(B) another kind → "Update your results" opens that results page', async () => {
    mockApi.listDocuments.mockResolvedValue({ documents: [higherDoc({
      kind_status: 'different', kind_detected: 'matric', note: 'kind_differs', note_kind: 'matric',
      note_path: '/onboarding/higher-grades' })] })
    await mount(appWith(DEGREE_STPM))
    expect(await screen.findByText('documentsTab.higher.note.kindDiffers')).toBeTruthy()
    fireEvent.click(screen.getByText('documentsTab.higher.updateResults'))
    expect(push).toHaveBeenCalledWith('/onboarding/higher-grades')
  })

  it('(C) differences → "Correct your … results" opens the held kind\'s page', async () => {
    mockApi.listDocuments.mockResolvedValue({ documents: [higherDoc({
      grades_status: 'mismatch', note: 'grades_differ', note_kind: 'stpm',
      note_path: '/onboarding/stpm-grades' })] })
    await mount(appWith(DEGREE_STPM))
    fireEvent.click(await screen.findByText('documentsTab.higher.correctResults'))
    expect(push).toHaveBeenCalledWith('/onboarding/stpm-grades')
  })

  it('(D) after submit the note offers no action (the server refuses it too)', async () => {
    mockApi.listDocuments.mockResolvedValue({ documents: [higherDoc({
      kind_status: 'spm', kind_detected: 'spm', note: 'spm_slip', note_kind: 'stpm', actions_open: false })] })
    await mount(appWith(DEGREE_STPM))
    expect(await screen.findByText('documentsTab.higher.note.spmSlip')).toBeTruthy()
    expect(screen.queryByText('documentsTab.higher.moveToSpm')).toBeNull()
    expect(screen.queryByText('documentsTab.higher.noHigher')).toBeNull()
  })

  it('(D) an SPM slip → "Move it to SPM results slip" re-files it and refreshes the cards', async () => {
    mockApi.listDocuments.mockResolvedValue({ documents: [higherDoc({
      kind_status: 'spm', kind_detected: 'spm', note: 'spm_slip', note_kind: 'stpm' })] })
    await mount(appWith(DEGREE_STPM))
    expect(await screen.findByText('documentsTab.higher.note.spmSlip')).toBeTruthy()
    const before = mockApi.listDocuments.mock.calls.length
    fireEvent.click(screen.getByText('documentsTab.higher.moveToSpm'))
    await waitFor(() => expect(mockApi.refileToSpm).toHaveBeenCalledWith(41, { token: 't' }))
    await waitFor(() => expect(mockApi.listDocuments.mock.calls.length).toBeGreaterThan(before))
  })

  it('(D) the rare case → the confirm box → SPM only, this browser cleared, sent to choose a pathway', async () => {
    localStorage.setItem(KEY_STPM_CGPA, '3.71')
    localStorage.setItem(KEY_STPM_GRADES, '{"PA":"A"}')
    localStorage.setItem(KEY_RESULTS_EXAM_TYPE, 'stpm')
    localStorage.setItem('halatuju_grades', '{"bm":"A"}')
    mockApi.listDocuments.mockResolvedValue({ documents: [higherDoc({
      kind_status: 'spm', kind_detected: 'spm', note: 'spm_slip', note_kind: 'stpm' })] })
    await mount(appWith(DEGREE_STPM))
    fireEvent.click(await screen.findByText('documentsTab.higher.noHigher'))
    expect(screen.getByRole('alertdialog')).toBeTruthy()
    expect(screen.getByText('documentsTab.higher.confirm.title')).toBeTruthy()
    // Cancel changes nothing
    fireEvent.click(screen.getByText('documentsTab.higher.confirm.cancel'))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(mockApi.continueWithSpmOnly).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText('documentsTab.higher.noHigher'))
    fireEvent.click(screen.getByText('documentsTab.higher.confirm.go'))
    await waitFor(() => expect(mockApi.continueWithSpmOnly).toHaveBeenCalledWith(41, { token: 't' }))
    await waitFor(() => expect(push).toHaveBeenCalledWith('/profile#pathway'))
    expect(localStorage.getItem(KEY_STPM_CGPA)).toBeNull()
    expect(localStorage.getItem(KEY_STPM_GRADES)).toBeNull()
    expect(localStorage.getItem(KEY_RESULTS_EXAM_TYPE)).toBe('spm')
    expect(localStorage.getItem('halatuju_grades')).toBe('{"bm":"A"}')
  })
})
