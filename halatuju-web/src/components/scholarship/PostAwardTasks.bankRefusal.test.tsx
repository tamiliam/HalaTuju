/**
 * @jest-environment jsdom
 *
 * TD-462: the bank-statement upload refuses, before uploading, a file the server would refuse
 * (too big for the served limit, or not a photo / PDF) — the same rule as the Action Centre.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { BankDetailsTask } from './PostAwardTasks'
import type { ResolutionItem } from '@/lib/api'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({
    t: (k: string, p?: Record<string, string>) => (p?.mb ? `${k}:${p.mb}` : k), locale: 'en',
  }),
}))
jest.mock('@/components/DocumentHelpCoach', () => () => null)
const mockSign = jest.fn()
jest.mock('@/lib/api', () => ({
  signUploadDocument: (...a: unknown[]) => mockSign(...a),
  uploadFileToSignedUrl: jest.fn(),
  recordDocument: jest.fn(),
  confirmBankAccount: jest.fn(),
}))

const ITEM = { id: 1 } as ResolutionItem
const pick = (file: File) => {
  const { container } = render(<BankDetailsTask item={ITEM} token="tok" onResolved={() => {}} limits={{ max_doc_size_mb: 1 }} />)
  fireEvent.change(container.querySelector('input[type=file]') as HTMLInputElement, { target: { files: [file] } })
}

beforeEach(() => mockSign.mockReset())

it('refuses a file over the served limit without uploading it', async () => {
  pick(new File([new Uint8Array(2 * 1024 * 1024)], 'big.pdf', { type: 'application/pdf' }))
  expect((await screen.findByText('scholarship.docs.file_too_large:1'))).toBeTruthy()
  expect(mockSign).not.toHaveBeenCalled()
})

it('refuses a file that is not a photo or PDF without uploading it', async () => {
  pick(new File(['x'], 'statement.docx', { type: 'application/msword' }))
  expect(await screen.findByText('scholarship.docs.unsupportedFormat')).toBeTruthy()
  expect(mockSign).not.toHaveBeenCalled()
})

it('lets a good file go to the upload', async () => {
  mockSign.mockRejectedValue(new Error('stop here'))
  pick(new File(['x'], 'statement.pdf', { type: 'application/pdf' }))
  await waitFor(() => expect(mockSign).toHaveBeenCalledTimes(1))
})
