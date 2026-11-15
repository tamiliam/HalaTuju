/**
 * @jest-environment jsdom
 *
 * NAVKEYS review (2026-11-16): the contract DETAIL page asks the served `contracts_write` door before it
 * offers a write. On the server every template write — config, clauses, quiz, schedule, vetting, submit,
 * deploy, revert — asks `contracts.edit` (`_ContractsBase._contract_admin`); a GET asks `contracts.view`.
 * Since NAVKEYS a `contracts.view` reader reaches this page from the list, so the page must read the door
 * (a wrong door here fails this file) and hand it to every editor.
 */
import { fireEvent, render, screen } from '@testing-library/react'

import ContractEditorPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
let mockViewer: Record<string, unknown> | null = null
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: mockViewer
    ?? jest.requireActual('@/test/staffPresets').withServedKeys({ role: 'org_admin', is_super_admin: false }) }),
}))
jest.mock('next/navigation', () => ({
  useParams: () => ({ id: '7' }), useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}))
jest.mock('@/lib/programmeScopeCore', () => ({ usePinProgramme: jest.fn() }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const DRAFT = {
  id: 7, organisation: 'brightpath', version: '2026-v1', status: 'draft',
  programme: { code: 'brightpath-flagship', name: 'Flagship Bursary' },
  title_en: 'Bursary agreement', title_ms: '', title_ta: '',
  preamble_en: '', preamble_ms: '', preamble_ta: '',
  progress_standard_en: '', progress_standard_ms: '', progress_standard_ta: '',
  counterparty_name: 'Example Foundation', counterparty_title: '', counterparty_nric: '',
  counterparty_address: '', counterparty_notify_emails: [], parent_role: 'guardian', witness_policy: 'required',
  vetted_by_name: '', vetted_on: null, schedule: [],
  clauses: [{ order: 1, level: 0, heading_en: 'Duties', heading_ms: '', heading_ta: '',
    body_en: 'The student shall study.', body_ms: '', body_ta: '',
    is_quiz_candidate: true, quiz_en: {}, quiz_ms: {}, quiz_ta: {} }],
} as unknown as api.ContractTemplateDetail

beforeEach(() => {
  jest.clearAllMocks()
  mockViewer = null
  mockApi.getContractTemplate.mockResolvedValue(DRAFT)
  mockApi.getContractValidation.mockResolvedValue({ ok: true, errors: [], warnings: [] })
  mockApi.getContractTemplates.mockResolvedValue({ templates: [] })
})

const open = async () => {
  render(<ContractEditorPage />)
  await screen.findByText('2026-v1')
}
const tab = (name: string) => fireEvent.click(screen.getByText(`admin.contracts.tab.${name}`))

describe('NAVKEYS review: the contract detail page offers a write only with contracts_write', () => {
  it('a contracts.view reader reads a DRAFT with no save, generate, vetting or submit anywhere', async () => {
    mockViewer = { role: 'admin', is_super_admin: false, permissions: [], page_keys: ['contracts.view'] }
    await open()
    expect(screen.getByTestId('contract-reader-note')).toBeTruthy()
    // Config (the first tab): read-only, no Save.
    expect((screen.getByDisplayValue('Bursary agreement') as HTMLInputElement).disabled).toBe(true)
    expect(screen.queryByText('admin.contracts.save')).toBeNull()
    tab('clauses')
    expect(screen.queryByText('admin.contracts.saveClauses')).toBeNull()
    tab('quiz')
    expect(screen.queryByText('admin.contracts.generateWithGemini')).toBeNull()
    expect(screen.queryByText('admin.contracts.save')).toBeNull()
    tab('schedule')
    expect(screen.queryByText('admin.contracts.save')).toBeNull()
    tab('deploy')
    await screen.findByText(/admin.contracts.allChecksPass/)    // the checklist is a read: a reader keeps it
    expect(screen.queryByText('admin.contracts.attestation')).toBeNull()
    expect(screen.queryByText('admin.contracts.submitForDeployment')).toBeNull()
  })

  it('a reader holding some OTHER write door still saves nothing here (the page asks contracts_write)', async () => {
    mockViewer = { role: 'admin', is_super_admin: false, permissions: [],
      page_keys: ['contracts.view', 'programmes.edit', 'settings.edit'] }
    await open()
    expect(screen.getByTestId('contract-reader-note')).toBeTruthy()
    expect(screen.queryByText('admin.contracts.save')).toBeNull()
  })

  it('an organisation admin (served contracts.edit) edits the draft as before', async () => {
    await open()
    expect(screen.queryByTestId('contract-reader-note')).toBeNull()
    expect((screen.getByDisplayValue('Bursary agreement') as HTMLInputElement).disabled).toBe(false)
    expect(screen.getByText('admin.contracts.save')).toBeTruthy()
    tab('clauses')
    expect(screen.getByText('admin.contracts.saveClauses')).toBeTruthy()
    tab('quiz')
    expect(screen.getByText('admin.contracts.generateWithGemini')).toBeTruthy()
    tab('deploy')
    expect(await screen.findByText('admin.contracts.submitForDeployment')).toBeTruthy()
    expect(screen.getByText('admin.contracts.attestation')).toBeTruthy()
  })
})
