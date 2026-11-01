/**
 * @jest-environment jsdom
 *
 * Mobile M4 — the remove sheet is a LAZY chunk, and a lazy chunk that carries a way out needs an eager
 * fallback (lessons.md, Mobile M2): when the chunk cannot load (a deploy between page load and the
 * tap), the phone's own confirm asks instead. Never a delete without a question; still one delete.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import ScholarshipDocuments from './ScholarshipDocuments'
import type { ApplicantDocument, ScholarshipApplication } from '@/lib/api'
import { sandboxApplication } from '@/sandbox/fixtures/scholarship'
import * as api from '@/lib/api'

jest.mock('./ScholarshipDocuments/RemoveConfirm', () => { throw new Error('ChunkLoadError') })
jest.mock('@/lib/api', () => ({
  __esModule: true,
  ...jest.requireActual('@/lib/api'),
  listDocuments: jest.fn(),
  getConsentStatus: jest.fn(),
  deleteDocument: jest.fn(),
  updateScholarshipDetails: jest.fn(),
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('./DocumentHelpCoach', () => ({ __esModule: true, default: () => null }))
jest.mock('./IncomeClusterCoach', () => ({ __esModule: true, default: () => null }))

const mockApi = api as jest.Mocked<typeof api>
const app = { ...sandboxApplication,
  requirements: { documents: { required: ['ic', 'results_slip'], optional: [] } } } as ScholarshipApplication
const SLIP = { id: 41, doc_type: 'results_slip', original_filename: 'keputusan-spm.pdf', size: 1200,
  household_member: '', download_url: 'https://x/slip' } as unknown as ApplicantDocument

beforeEach(() => { jest.clearAllMocks() })

it('chunk fails → the phone\'s own confirm: Cancel deletes nothing, OK deletes once', async () => {
  mockApi.listDocuments.mockResolvedValue({ documents: [SLIP] })
  mockApi.getConsentStatus.mockResolvedValue({ is_minor: false, consents: [] } as unknown as api.ConsentStatus)
  mockApi.deleteDocument.mockResolvedValue(undefined as never)
  const ask = jest.spyOn(window, 'confirm')
  render(<ScholarshipDocuments token="tkn" app={app} />)
  await screen.findByText('keputusan-spm.pdf')
  const remove = () => screen.getByRole('button', { name: 'scholarship.docs.remove' })

  ask.mockReturnValueOnce(false)
  await act(async () => { fireEvent.click(remove()) })
  await waitFor(() => expect(ask).toHaveBeenCalledWith('documentsTab.card.removeTitle'))
  expect(mockApi.deleteDocument).not.toHaveBeenCalled()

  ask.mockReturnValueOnce(true)
  await act(async () => { fireEvent.click(remove()) })
  await waitFor(() => expect(mockApi.deleteDocument).toHaveBeenCalledTimes(1))
  expect(screen.queryByTestId('remove-confirm')).toBeNull()
  ask.mockRestore()
})

it('the fallback path, tapped twice while the first delete is in flight: ONE delete (the latch, not a disabled button)', async () => {
  mockApi.listDocuments.mockResolvedValue({ documents: [SLIP] })
  mockApi.getConsentStatus.mockResolvedValue({ is_minor: false, consents: [] } as unknown as api.ConsentStatus)
  let finish: () => void = () => {}
  mockApi.deleteDocument.mockImplementation(() => new Promise((r) => { finish = () => r(undefined as never) }))
  const ask = jest.spyOn(window, 'confirm').mockReturnValue(true)
  render(<ScholarshipDocuments token="tkn" app={app} />)
  await screen.findByText('keputusan-spm.pdf')
  const remove = screen.getByRole('button', { name: 'scholarship.docs.remove' })
  await act(async () => { fireEvent.click(remove) })
  await waitFor(() => expect(mockApi.deleteDocument).toHaveBeenCalledTimes(1))
  await act(async () => { fireEvent.click(remove) })
  await act(async () => { await new Promise((r) => setTimeout(r, 0)) })
  await act(async () => { finish() })
  expect(mockApi.deleteDocument).toHaveBeenCalledTimes(1)
  ask.mockRestore()
})
