/**
 * @jest-environment jsdom
 *
 * H5 — the Action Centre redesign: three sections, a sent state for typed answers, a "why we ask"
 * line, a returned document said plainly, a clear bad-file message, a load error with a retry, and a
 * "Take a photo" button beside the normal Upload.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import ActionCentre from './ActionCentre'
import * as api from '@/lib/api'
import type { ResolutionItem } from '@/lib/api'

jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  getResolutionItems: jest.fn(),
  resolveResolutionItem: jest.fn(),
  listDocuments: jest.fn(),
  signUploadDocument: jest.fn(),
  uploadFileToSignedUrl: jest.fn(),
  recordDocument: jest.fn(),
}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p?.mb ? `${k}:${p.mb}` : k), locale: 'en' }),
}))
jest.mock('./DocumentHelpCoach', () => ({ __esModule: true, default: () => null, CoachCard: () => null }))
jest.mock('./IncomeClusterCoach', () => ({ __esModule: true, default: () => null }))

const mockApi = api as jest.Mocked<typeof api>
const make = (over: Partial<ResolutionItem>): ResolutionItem => ({
  id: 1, fact: 'identity', code: 'ic_missing', params: {}, prompt: '', kind: 'doc', doc_type: 'ic',
  status: 'open', source: 'system', resolution_text: '', created_at: '2026-11-01T09:00:00.000Z', resolved_at: null,
  ...over,
})
const NEEDS = make({ id: 1 })
const SENT = make({ id: 2, kind: 'explanation', doc_type: '', code: 'transport_cost_unknown', status: 'resolved', resolution_text: 'It is a bus fare' })
const DONE = make({ id: 3, doc_type: 'results_slip', code: 'results_slip_missing', status: 'resolved' })

const mount = async (open: ResolutionItem[], resolved: ResolutionItem[]) => {
  mockApi.getResolutionItems.mockResolvedValue({ open, resolved })
  mockApi.listDocuments.mockResolvedValue({ documents: [] } as never)
  render(<ActionCentre token="tkn" studentName="Test Student" applicationId={6} />)
  await waitFor(() => expect(mockApi.getResolutionItems).toHaveBeenCalled())
}

beforeEach(() => { jest.clearAllMocks() })

describe('three sections', () => {
  it('shows Needs you, Sent and Done', async () => {
    await mount([NEEDS], [SENT, DONE])
    expect(await screen.findByText('scholarship.actionCentre.section.needs')).toBeTruthy()
    expect(screen.getByText('scholarship.actionCentre.section.sent')).toBeTruthy()
    expect(screen.getByText('scholarship.actionCentre.section.done')).toBeTruthy()
  })

  it('a typed answer is Sent: it quotes the answer and says a reviewer will read it', async () => {
    await mount([NEEDS], [SENT])
    expect(await screen.findByText('It is a bus fare')).toBeTruthy()
    expect(screen.getByText('scholarship.actionCentre.sentAnswer')).toBeTruthy()
  })

  it('every open item carries its why-we-ask line', async () => {
    await mount([NEEDS], [])
    expect(await screen.findByText('scholarship.actionCentre.why.ic')).toBeTruthy()
  })

  it('a section with nothing in it is not drawn', async () => {
    await mount([NEEDS], [])
    await screen.findByText('scholarship.actionCentre.section.needs')
    expect(screen.queryByText('scholarship.actionCentre.section.sent')).toBeNull()
    expect(screen.queryByText('scholarship.actionCentre.section.done')).toBeNull()
  })
})

describe('a returned document', () => {
  it('goes back to Needs you saying "We need this again"', async () => {
    await mount([make({ params: { attempts: 1 } })], [])
    expect(await screen.findByText('scholarship.actionCentre.needAgain')).toBeTruthy()
  })
})

describe('uploading', () => {
  it('offers Upload (photo or PDF) and Take a photo (back camera) side by side', async () => {
    await mount([NEEDS], [])
    await screen.findByText('scholarship.actionCentre.takePhoto')
    const inputs = Array.from(document.querySelectorAll('input[type="file"]')) as HTMLInputElement[]
    const camera = inputs.filter((i) => i.getAttribute('capture') === 'environment')
    const normal = inputs.filter((i) => !i.hasAttribute('capture'))
    expect(camera).toHaveLength(1)
    expect(normal).toHaveLength(1)
    expect(normal[0].getAttribute('accept')).toBe('image/*,.pdf')
  })

  it('an unreadable file gets the clear bad-file message', async () => {
    mockApi.signUploadDocument.mockResolvedValue({ upload_url: 'u', storage_path: 'p' } as never)
    mockApi.uploadFileToSignedUrl.mockResolvedValue(undefined as never)
    mockApi.recordDocument.mockRejectedValue(Object.assign(new Error('x'), { code: 'bad_file' }))
    await mount([NEEDS], [])
    await screen.findByText('scholarship.actionCentre.takePhoto')
    const input = document.querySelector('input[type="file"]:not([capture])') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(['x'], 'scan.pdf', { type: 'application/pdf' })] } })
    expect(await screen.findByText('scholarship.actionCentre.badFile')).toBeTruthy()
  })

  it('a locked-documents refusal shows the server message plainly', async () => {
    mockApi.signUploadDocument.mockRejectedValue(Object.assign(new Error('Documents are closed now.'), { code: 'documents_locked' }))
    await mount([NEEDS], [])
    await screen.findByText('scholarship.actionCentre.takePhoto')
    const input = document.querySelector('input[type="file"]:not([capture])') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(['x'], 'a.pdf', { type: 'application/pdf' })] } })
    expect(await screen.findByText('Documents are closed now.')).toBeTruthy()
  })
})

describe('load error', () => {
  it('says so, offers a retry, and recovers on it', async () => {
    mockApi.getResolutionItems.mockRejectedValueOnce(new Error('offline'))
    mockApi.listDocuments.mockResolvedValue({ documents: [] } as never)
    render(<ActionCentre token="tkn" studentName="Test Student" applicationId={6} />)
    expect(await screen.findByText('scholarship.actionCentre.loadError.title')).toBeTruthy()
    mockApi.getResolutionItems.mockResolvedValue({ open: [NEEDS], resolved: [] })
    fireEvent.click(screen.getByRole('button', { name: 'scholarship.actionCentre.loadError.retry' }))
    expect(await screen.findByText('scholarship.actionCentre.section.needs')).toBeTruthy()
    expect(screen.queryByText('scholarship.actionCentre.loadError.title')).toBeNull()
  })
})

describe('load error, second failure', () => {
  it('shows the error card again, with no all-done state between', async () => {
    mockApi.getResolutionItems.mockRejectedValue(new Error('offline'))
    mockApi.listDocuments.mockResolvedValue({ documents: [] } as never)
    render(<ActionCentre token="tkn" studentName="Test Student" applicationId={6} formLocked />)
    const retry = await screen.findByRole('button', { name: 'scholarship.actionCentre.loadError.retry' })
    fireEvent.click(retry)
    expect(screen.queryByText('scholarship.actionCentre.awaitTitle')).toBeNull()
    expect(await screen.findByText('scholarship.actionCentre.loadError.title')).toBeTruthy()
    expect(screen.queryByText('scholarship.actionCentre.awaitTitle')).toBeNull()
  })
})

describe('documents lock', () => {
  const withLock = async (lock: { locked: boolean; open_doc_types: string[] }, docType: string) => {
    mockApi.getResolutionItems.mockResolvedValue({ open: [make({ id: 9, doc_type: docType })], resolved: [] })
    mockApi.listDocuments.mockResolvedValue({ documents: [], lock } as never)
    render(<ActionCentre token="tkn" studentName="Test Student" applicationId={6} />)
    await screen.findByText('scholarship.actionCentre.section.needs')
  }
  it('locked: Upload and Take a photo are hidden', async () => {
    await withLock({ locked: true, open_doc_types: [] }, 'ic')
    expect(screen.queryByText('scholarship.actionCentre.upload')).toBeNull()
    expect(screen.queryByText('scholarship.actionCentre.takePhoto')).toBeNull()
  })
  it('locked but the type is exempt: buttons shown', async () => {
    await withLock({ locked: true, open_doc_types: ['bank_statement'] }, 'bank_statement')
    expect(screen.getByText('scholarship.actionCentre.upload')).toBeTruthy()
    expect(screen.getByText('scholarship.actionCentre.takePhoto')).toBeTruthy()
  })
  it('not locked: buttons shown', async () => {
    await withLock({ locked: false, open_doc_types: [] }, 'ic')
    expect(screen.getByText('scholarship.actionCentre.upload')).toBeTruthy()
  })
})
