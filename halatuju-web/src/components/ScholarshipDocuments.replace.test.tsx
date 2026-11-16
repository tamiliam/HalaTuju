/**
 * @jest-environment jsdom
 *
 * H6: Replace on the Documents tab. A document that reads fine shows how many replaces are left, loses
 * the button after the third, and sends `replace: true`; a returned one is the normal re-upload (no
 * count, no flag). Locked hides Replace (see ScholarshipDocuments.locked.test.tsx).
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ScholarshipDocuments from './ScholarshipDocuments'
import type { ApplicantDocument, ApplicationRequirements, ScholarshipApplication } from '@/lib/api'
import { sandboxApplication } from '@/sandbox/fixtures/scholarship'
import * as api from '@/lib/api'

jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  listDocuments: jest.fn(),
  getConsentStatus: jest.fn(),
  signUploadDocument: jest.fn(),
  uploadFileToSignedUrl: jest.fn(),
  recordDocument: jest.fn(),
  deleteDocument: jest.fn(),
  updateScholarshipDetails: jest.fn(),
}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p?.n ? `${k}:${p.n}` : k), locale: 'en' }),
}))
jest.mock('./DocumentHelpCoach', () => ({ __esModule: true, default: () => null }))
jest.mock('./IncomeClusterCoach', () => ({ __esModule: true, default: () => null }))

const mockApi = api as jest.Mocked<typeof api>
const REQ: ApplicationRequirements = { documents: { required: ['ic', 'results_slip'], optional: [] } }
const app = { ...sandboxApplication, requirements: REQ } as ScholarshipApplication
const slip = (over: Record<string, unknown>) => ({
  id: 41, doc_type: 'results_slip', original_filename: 'keputusan-spm.pdf', size: 1200,
  household_member: '', download_url: 'https://x/slip', replace_limit: 3, ...over,
}) as unknown as ApplicantDocument

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getConsentStatus.mockResolvedValue({ is_minor: false, consents: [] } as unknown as api.ConsentStatus)
})

const mount = async (d: ApplicantDocument) => {
  mockApi.listDocuments.mockResolvedValue({ documents: [d], lock: { locked: false, open_doc_types: [] } } as never)
  render(<ScholarshipDocuments token="tkn" app={app} />)
  await screen.findByText('keputusan-spm.pdf')
}

const swap = async () => {
  mockApi.signUploadDocument.mockResolvedValue({ upload_url: 'u', storage_path: 'p' } as never)
  mockApi.uploadFileToSignedUrl.mockResolvedValue(undefined as never)
  mockApi.recordDocument.mockResolvedValue({ id: 50 } as never)
  const input = screen.getByText('scholarship.docs.replace').querySelector('input') as HTMLInputElement
  fireEvent.change(input, { target: { files: [new File(['x'], 'new.pdf', { type: 'application/pdf' })] } })
  await waitFor(() => expect(mockApi.recordDocument).toHaveBeenCalled())
  return mockApi.recordDocument.mock.calls[0][0] as Record<string, unknown>
}

describe('replace on the documents tab', () => {
  it('a settled document shows Replace and the replaces left', async () => {
    await mount(slip({ replace_count: 1 }))
    expect(screen.getByText('scholarship.docs.replace')).toBeTruthy()
    expect(screen.getByText('scholarship.actionCentre.replacesLeft:2')).toBeTruthy()
  })

  it('after three replaces: no Replace, a plain line instead', async () => {
    await mount(slip({ replace_count: 3 }))
    expect(screen.queryByText('scholarship.docs.replace')).toBeNull()
    expect(screen.getByText('scholarship.actionCentre.replaceLimit')).toBeTruthy()
  })

  it('a returned document keeps an uncapped Replace and no count', async () => {
    await mount(slip({ replace_count: 3, vision_fields: { student_verdict: 'unreadable' } }))
    expect(screen.getByText('scholarship.docs.replace')).toBeTruthy()
    expect(screen.queryByText('scholarship.actionCentre.replaceLimit')).toBeNull()
  })

  it('sends replace: true for a settled document', async () => {
    await mount(slip({ replace_count: 0 }))
    expect((await swap()).replace).toBe(true)
  })

  it('does not send replace for a returned document', async () => {
    await mount(slip({ replace_count: 0, vision_fields: { student_verdict: 'unreadable' } }))
    expect((await swap()).replace).toBeUndefined()
  })
})
