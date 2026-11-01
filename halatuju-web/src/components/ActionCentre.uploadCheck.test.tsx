/**
 * @jest-environment jsdom
 *
 * Mobile M4: the Action Centre refuses, BEFORE uploading, a file the server would refuse — larger
 * than the organisation's served limit, or not a photo / PDF — exactly as the documents tab does
 * (`@/lib/uploadCheck`). It used to send any file and let the server say no after the upload.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'

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
const DOC_TASK: ResolutionItem = {
  id: 5, fact: 'identity', code: 'ic_missing', params: {}, prompt: '', kind: 'doc', doc_type: 'ic',
  status: 'open', source: 'system', resolution_text: '', created_at: '2026-11-01T09:00:00.000Z', resolved_at: null,
}

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getResolutionItems.mockResolvedValue({ open: [DOC_TASK], resolved: [] })
  // The organisation serves a 2 MB limit — the check must read THAT, not the platform default.
  mockApi.listDocuments.mockResolvedValue({ documents: [], limits: { max_doc_size_mb: 2 } } as never)
  mockApi.signUploadDocument.mockResolvedValue({ upload_url: 'u', storage_path: 'p' } as never)
  mockApi.uploadFileToSignedUrl.mockResolvedValue(undefined as never)
  mockApi.recordDocument.mockResolvedValue({ match_verdict: 'ok' } as never)
})

async function pick(file: File) {
  render(<ActionCentre token="tkn" studentName="Aina" applicationId={7} formLocked />)
  const input = (await screen.findByText('scholarship.actionCentre.upload')).closest('label')!
    .querySelector('input[type=file]') as HTMLInputElement
  await act(async () => { fireEvent.change(input, { target: { files: [file] } }) })
}
const sized = (name: string, type: string, bytes: number) => {
  const f = new File(['x'], name, { type })
  Object.defineProperty(f, 'size', { value: bytes })
  return f
}

it('too large for the served limit: refused with its number, nothing uploaded', async () => {
  await pick(sized('ic.jpg', 'image/jpeg', 3 * 1024 * 1024))
  expect(screen.getByText('scholarship.docs.file_too_large:2')).toBeTruthy()
  expect(mockApi.signUploadDocument).not.toHaveBeenCalled()
})

it('not a photo or a PDF: refused, nothing uploaded', async () => {
  await pick(sized('clip.mp4', 'video/mp4', 1000))
  expect(screen.getByText('scholarship.docs.unsupportedFormat')).toBeTruthy()
  expect(mockApi.signUploadDocument).not.toHaveBeenCalled()
})

it('a photo inside the limit goes up (control)', async () => {
  await pick(sized('ic.jpg', 'image/jpeg', 1024 * 1024))
  expect(mockApi.signUploadDocument).toHaveBeenCalledWith('ic', { token: 'tkn' })
})
