/**
 * @jest-environment jsdom
 *
 * H5 (from H4) — once documents are locked (the interview stage), the Documents tab hides Upload,
 * Replace and Remove and says why; a type the server still takes (the exempt asks) stays open; and if
 * the server refuses anyway (409 documents_locked) its message is shown plainly.
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
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p?.name ? `${k}:${p.name}` : k), locale: 'en' }),
}))
jest.mock('./DocumentHelpCoach', () => ({ __esModule: true, default: () => null }))
jest.mock('./IncomeClusterCoach', () => ({ __esModule: true, default: () => null }))

const mockApi = api as jest.Mocked<typeof api>
const REQ: ApplicationRequirements = { documents: { required: ['ic', 'results_slip'], optional: [] } }
const app = { ...sandboxApplication, requirements: REQ } as ScholarshipApplication
const SLIP = { id: 41, doc_type: 'results_slip', original_filename: 'keputusan-spm.pdf', size: 1200,
  household_member: '', download_url: 'https://x/slip' } as unknown as ApplicantDocument

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getConsentStatus.mockResolvedValue({ is_minor: false, consents: [] } as unknown as api.ConsentStatus)
})

const mount = async (lock: { locked: boolean; open_doc_types: string[] }) => {
  mockApi.listDocuments.mockResolvedValue({ documents: [SLIP], lock } as never)
  render(<ScholarshipDocuments token="tkn" app={app} />)
  await screen.findByText('keputusan-spm.pdf')
}

describe('locked documents tab', () => {
  it('hides Remove on a held document and says why', async () => {
    await mount({ locked: true, open_doc_types: [] })
    expect(screen.queryByRole('button', { name: 'scholarship.docs.remove' })).toBeNull()
    expect(screen.getAllByText('scholarship.docs.lockedNote').length).toBeGreaterThan(0)
  })

  it('an exempt type stays open: its card keeps Remove', async () => {
    await mount({ locked: true, open_doc_types: ['results_slip'] })
    expect(screen.getByRole('button', { name: 'scholarship.docs.remove' })).toBeTruthy()
  })

  it('unlocked: Remove is there as ever, with no lock note', async () => {
    await mount({ locked: false, open_doc_types: [] })
    expect(screen.getByRole('button', { name: 'scholarship.docs.remove' })).toBeTruthy()
    expect(screen.queryByText('scholarship.docs.lockedNote')).toBeNull()
  })

  it('a 409 documents_locked shows the server message plainly', async () => {
    await mount({ locked: false, open_doc_types: [] })
    mockApi.deleteDocument.mockRejectedValue(Object.assign(new Error('Documents are closed now.'), { code: 'documents_locked' }))
    fireEvent.click(screen.getByRole('button', { name: 'scholarship.docs.remove' }))
    const sheet = await screen.findByTestId('remove-confirm')
    const go = Array.from(sheet.querySelectorAll('button')).find((b) => b.textContent === 'scholarship.docs.remove') as HTMLButtonElement
    fireEvent.click(go)
    await waitFor(() => expect(screen.getByText('Documents are closed now.')).toBeTruthy())
  })
})
