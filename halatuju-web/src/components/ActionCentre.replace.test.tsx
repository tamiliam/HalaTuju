/**
 * @jest-environment jsdom
 *
 * H6: Replace on a Done document in the Action Centre. Shown with how many replaces are left, hidden
 * once documents are locked (unless the type is exempt) and after the third, and the server's refusal
 * of a fourth is shown plainly. A replace is recorded with `replace: true`.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import ActionCentre from './ActionCentre'
import * as api from '@/lib/api'
import type { ApplicantDocument, ResolutionItem } from '@/lib/api'

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
  useT: () => ({ t: (k: string, p?: Record<string, string>) => (p?.n ? `${k}:${p.n}` : k), locale: 'en' }),
}))
jest.mock('./DocumentHelpCoach', () => ({ __esModule: true, default: () => null, CoachCard: () => null }))
jest.mock('./IncomeClusterCoach', () => ({ __esModule: true, default: () => null }))

const mockApi = api as jest.Mocked<typeof api>
const DONE: ResolutionItem = {
  id: 3, fact: 'academic', code: 'results_slip_missing', params: {}, prompt: '', kind: 'doc', doc_type: 'results_slip',
  status: 'resolved', source: 'system', resolution_text: '', created_at: '2026-11-01T09:00:00.000Z', resolved_at: '2026-11-02T09:00:00.000Z',
}
const doc = (replace_count: number): ApplicantDocument => ({
  id: 9, doc_type: 'results_slip', household_member: '', original_filename: 'slip.pdf', replace_count, replace_limit: 3,
} as unknown as ApplicantDocument)

const mount = async (replaceCount: number, lock = { locked: false, open_doc_types: [] as string[] }) => {
  mockApi.getResolutionItems.mockResolvedValue({ open: [], resolved: [DONE] })
  mockApi.listDocuments.mockResolvedValue({ documents: [doc(replaceCount)], lock } as never)
  render(<ActionCentre token="tkn" studentName="Test Student" applicationId={6} />)
  await screen.findByText('scholarship.actionCentre.section.done')
}

const pick = (name: string) => {
  const input = screen.getByText('scholarship.actionCentre.replace').querySelector('input') as HTMLInputElement
  fireEvent.change(input, { target: { files: [new File(['x'], name, { type: 'application/pdf' })] } })
}

beforeEach(() => { jest.clearAllMocks() })

describe('Replace on a Done document', () => {
  it('shows Replace and how many are left', async () => {
    await mount(1)
    expect(screen.getByText('scholarship.actionCentre.replace')).toBeTruthy()
    expect(screen.getByText('scholarship.actionCentre.replacesLeft:2')).toBeTruthy()
    expect(screen.getByText('slip.pdf')).toBeTruthy()
  })

  it('says one more time when one is left', async () => {
    await mount(2)
    expect(screen.getByText('scholarship.actionCentre.replacesLeftOne:1')).toBeTruthy()
  })

  it('after three replaces there is no button, only a plain line', async () => {
    await mount(3)
    expect(screen.queryByText('scholarship.actionCentre.replace')).toBeNull()
    expect(screen.getByText('scholarship.actionCentre.replaceLimit')).toBeTruthy()
  })

  it('is hidden once documents are locked', async () => {
    await mount(0, { locked: true, open_doc_types: [] })
    expect(screen.queryByText('scholarship.actionCentre.replace')).toBeNull()
    expect(screen.queryByText('scholarship.actionCentre.replaceLimit')).toBeNull()
  })

  it('a locked case still shows Replace for an exempt type', async () => {
    await mount(0, { locked: true, open_doc_types: ['results_slip'] })
    expect(screen.getByText('scholarship.actionCentre.replace')).toBeTruthy()
  })

  it('a replace is recorded with replace: true and the list is reloaded', async () => {
    await mount(0)
    mockApi.signUploadDocument.mockResolvedValue({ upload_url: 'u', storage_path: 'p' } as never)
    mockApi.uploadFileToSignedUrl.mockResolvedValue(undefined as never)
    mockApi.recordDocument.mockResolvedValue({ id: 10 } as never)
    pick('new.pdf')
    await waitFor(() => expect(mockApi.recordDocument).toHaveBeenCalled())
    expect(mockApi.recordDocument.mock.calls[0][0]).toMatchObject({ doc_type: 'results_slip', replace: true, storage_path: 'p' })
    await waitFor(() => expect(mockApi.listDocuments.mock.calls.length).toBeGreaterThan(1))
  })

  it("an officer request's Replace sends its code and the request's own member", async () => {
    const OFFICER: ResolutionItem = { ...DONE, id: 5, code: 'officer_7', source: 'officer', params: {} }
    mockApi.getResolutionItems.mockResolvedValue({ open: [], resolved: [OFFICER] })
    mockApi.listDocuments.mockResolvedValue({
      documents: [{ ...doc(0), household_member: 'father', replaces_left: 2 }], lock: { locked: false, open_doc_types: [] },
    } as never)
    render(<ActionCentre token="tkn" studentName="Test Student" applicationId={6} />)
    await screen.findByText('scholarship.actionCentre.section.done')
    mockApi.signUploadDocument.mockResolvedValue({ upload_url: 'u', storage_path: 'p' } as never)
    mockApi.uploadFileToSignedUrl.mockResolvedValue(undefined as never)
    mockApi.recordDocument.mockResolvedValue({ id: 10 } as never)
    pick('new.pdf')
    await waitFor(() => expect(mockApi.recordDocument).toHaveBeenCalled())
    expect(mockApi.recordDocument.mock.calls[0][0]).toMatchObject({ request_code: 'officer_7', household_member: '' })
  })

  it('a refused fourth shows the server message plainly', async () => {
    await mount(0)
    mockApi.signUploadDocument.mockResolvedValue({ upload_url: 'u', storage_path: 'p' } as never)
    mockApi.uploadFileToSignedUrl.mockResolvedValue(undefined as never)
    mockApi.recordDocument.mockRejectedValue(Object.assign(new Error('You have already replaced this 3 times.'), { code: 'replace_limit_reached' }))
    pick('new.pdf')
    expect(await screen.findByText('You have already replaced this 3 times.')).toBeTruthy()
  })
})

describe('"I don\'t have this" after the interview lock', () => {
  const OPEN: ResolutionItem = {
    id: 4, fact: 'income', code: 'water_bill_recheck', params: {}, prompt: '', kind: 'doc', doc_type: 'water_bill',
    status: 'open', source: 'check2', resolution_text: '', created_at: '2026-11-01T09:00:00.000Z', resolved_at: null,
    decline_reasons: ['no_water_bill', 'other'],
  } as unknown as ResolutionItem
  const mountOpen = async (lock: { locked: boolean; open_doc_types: string[] }) => {
    mockApi.getResolutionItems.mockResolvedValue({ open: [OPEN], resolved: [] })
    mockApi.listDocuments.mockResolvedValue({ documents: [], lock } as never)
    render(<ActionCentre token="tkn" studentName="Test Student" applicationId={6} />)
    await waitFor(() => expect(mockApi.listDocuments).toHaveBeenCalled())
    await screen.findByText('scholarship.actionCentre.toDo')
  }

  it('is offered while documents are open', async () => {
    await mountOpen({ locked: false, open_doc_types: [] })
    expect(screen.getByText('scholarship.actionCentre.decline.button')).toBeTruthy()
  })

  it('is hidden once locked, even for an exempt type (the server refuses it: querying_closed)', async () => {
    await mountOpen({ locked: true, open_doc_types: ['water_bill'] })
    expect(screen.queryByText('scholarship.actionCentre.decline.button')).toBeNull()
  })
})
