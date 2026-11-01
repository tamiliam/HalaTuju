/**
 * @jest-environment jsdom
 *
 * Mobile M4 — the document card's doors. Remove ASKS first (a sheet, loaded lazily) and sends ONE
 * delete however many taps; Cancel sends none; if the sheet's chunk cannot load, the phone's own
 * confirm asks instead (a lazy way OUT needs an eager fallback — lessons.md, Mobile M2). Uploads are
 * busy PER CARD. Replace / Remove / Choose are 44 px buttons, never text links.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
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
const REQ: ApplicationRequirements = { documents: { required: ['ic', 'results_slip', 'offer_letter'], optional: [] } }
const app = { ...sandboxApplication, requirements: REQ } as ScholarshipApplication
const SLIP = { id: 41, doc_type: 'results_slip', original_filename: 'keputusan-spm.pdf', size: 1200,
  household_member: '', download_url: 'https://x/slip' } as unknown as ApplicantDocument

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.listDocuments.mockResolvedValue({ documents: [SLIP] })
  mockApi.getConsentStatus.mockResolvedValue({ is_minor: false, consents: [] } as unknown as api.ConsentStatus)
  mockApi.deleteDocument.mockResolvedValue(undefined as never)
})

async function mount() {
  render(<ScholarshipDocuments token="tkn" app={app} />)
  await screen.findByText('keputusan-spm.pdf')
}
const removeButton = () => screen.getByRole('button', { name: 'scholarship.docs.remove' })

describe('Remove asks first, then deletes once', () => {
  it('opens the sheet naming the file — and nothing is deleted yet', async () => {
    await mount()
    fireEvent.click(removeButton())
    const sheet = await screen.findByTestId('remove-confirm')
    expect(sheet.textContent).toContain('documentsTab.card.removeBody:keputusan-spm.pdf')
    expect(mockApi.deleteDocument).not.toHaveBeenCalled()
  })

  it('Keep it: no delete, the sheet closes', async () => {
    await mount()
    fireEvent.click(removeButton())
    await screen.findByTestId('remove-confirm')
    fireEvent.click(screen.getByRole('button', { name: 'documentsTab.card.keep' }))
    await waitFor(() => expect(screen.queryByTestId('remove-confirm')).toBeNull())
    expect(mockApi.deleteDocument).not.toHaveBeenCalled()
  })

  it('Remove, tapped twice in the sheet: ONE delete', async () => {
    let finish: () => void = () => {}
    mockApi.deleteDocument.mockImplementation(() => new Promise((r) => { finish = () => r(undefined as never) }))
    await mount()
    fireEvent.click(removeButton())
    const sheet = await screen.findByTestId('remove-confirm')
    const confirm = sheet.querySelectorAll('button')
    const go = Array.from(confirm).find((b) => b.textContent === 'scholarship.docs.remove') as HTMLButtonElement
    fireEvent.click(go)
    fireEvent.click(go)
    await act(async () => { finish() })
    expect(mockApi.deleteDocument).toHaveBeenCalledTimes(1)
    expect(mockApi.deleteDocument).toHaveBeenCalledWith(41, { token: 'tkn' })
  })

  it('the card button tapped again while a delete is in flight opens nothing new and deletes nothing more', async () => {
    let finish: () => void = () => {}
    mockApi.deleteDocument.mockImplementation(() => new Promise((r) => { finish = () => r(undefined as never) }))
    await mount()
    fireEvent.click(removeButton())
    const sheet = await screen.findByTestId('remove-confirm')
    const go = Array.from(sheet.querySelectorAll('button')).find((b) => b.textContent === 'scholarship.docs.remove') as HTMLButtonElement
    fireEvent.click(go)
    fireEvent.click(screen.getAllByRole('button', { name: 'scholarship.docs.remove' })[0])
    await act(async () => { finish() })
    expect(mockApi.deleteDocument).toHaveBeenCalledTimes(1)
  })
})

// The lazy chunk's FAILURE path: ScholarshipDocuments.removeFallback.test.tsx (its own module graph).

describe('44 px buttons, busy per card', () => {
  it('Replace and Remove are full-width 44 px buttons; an empty card offers one big camera-friendly button', async () => {
    await mount()
    expect(removeButton().className).toMatch(/\bmin-h-11\b/)
    const replace = screen.getByText('scholarship.docs.replace').closest('label') as HTMLLabelElement
    expect(replace.className).toMatch(/\bmin-h-11\b/)
    const choose = screen.getAllByText('documentsTab.card.choose')[0].closest('label') as HTMLLabelElement
    expect(choose.className).toMatch(/\bmin-h-12\b/)
    const input = choose.querySelector('input[type=file]') as HTMLInputElement
    expect(input.getAttribute('accept')).toContain('image/*')
    expect(input.hasAttribute('capture')).toBe(false)        // never force the camera: PDFs must stay choosable
    expect(input.className).toContain('sr-only')
  })

  it('two uploads at once: each card keeps its own "Uploading…" until its own file lands', async () => {
    const pending: Array<() => void> = []
    mockApi.signUploadDocument.mockResolvedValue({ upload_url: 'u', storage_path: 'p' } as never)
    mockApi.uploadFileToSignedUrl.mockImplementation(() => new Promise((r) => { pending.push(() => r(undefined as never)) }))
    mockApi.recordDocument.mockResolvedValue({} as never)
    await mount()
    const inputs = Array.from(document.querySelectorAll('input[type=file]')) as HTMLInputElement[]
    const file = new File(['x'], 'a.pdf', { type: 'application/pdf' })
    await act(async () => { fireEvent.change(inputs[0], { target: { files: [file] } }) })
    await act(async () => { fireEvent.change(inputs[inputs.length - 1], { target: { files: [file] } }) })
    await waitFor(() => expect(pending.length).toBe(2))
    expect(screen.getAllByText('scholarship.docs.uploading')).toHaveLength(2)
    await act(async () => { pending[0]() })
    await waitFor(() => expect(screen.getAllByText('scholarship.docs.uploading')).toHaveLength(1))
    await act(async () => { pending[1]() })
  })
})
