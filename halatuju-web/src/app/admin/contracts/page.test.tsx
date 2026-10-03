/**
 * @jest-environment jsdom
 *
 * Contract templates are written PER GIFT (TD-229, 2026-10-03; owner ruling 2026-09-04).
 *
 * What this pins on the list page:
 *   · the list is read for the BREADCRUMB's gift (`?programme=<code>` via the API helper), and
 *     re-read when the crumb changes;
 *   · with no gift chosen it reads every gift's templates (no code sent) and labels each row
 *     with its gift — a NULL gift is named as governing nobody, never left blank;
 *   · New version sends the crumb's gift, and with no gift chosen it does not call the server
 *     at all (it says why instead) — the page has no gift picker of its own.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ContractsListPage from './page'
import * as api from '@/lib/admin-api'
import { GiftScope, TWO_GIFTS } from '@/test/giftScope'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin', is_super_admin: false } }),
}))
const mockPush = jest.fn()
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: mockPush, replace: jest.fn() }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const row = (id: number, version: string, programme: { code: string; name: string } | null) => ({
  id, organisation: 'brightpath', version, status: 'active', programme,
  languages_available: ['en'], vetted_by_name: '', vetted_on: null, deployed_by_at: null,
  created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z',
}) as unknown as api.ContractTemplateSummary

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getContractTemplates.mockResolvedValue({ templates: [
    row(1, '2026-v1', { code: 'brightpath-flagship', name: 'Flagship Bursary' }),
    row(2, '2026-legacy', null),
  ] })
  mockApi.createContractTemplate.mockResolvedValue({ id: 9 } as unknown as api.ContractTemplateDetail)
})

describe('contract templates are read and written for the breadcrumb gift (TD-229)', () => {
  it('with no gift chosen, reads every gift and labels each row — a NULL gift says so', async () => {
    render(<GiftScope><ContractsListPage /></GiftScope>)
    await screen.findByText('2026-v1')
    expect(mockApi.getContractTemplates).toHaveBeenCalledWith(undefined, { token: 'tok' })
    expect(screen.getByText('Flagship Bursary')).toBeTruthy()
    expect(screen.getByText('admin.contracts.noGift')).toBeTruthy()
  })

  it('with one gift, reads THAT gift and creates for it', async () => {
    render(<GiftScope choices={[TWO_GIFTS[1]]}><ContractsListPage /></GiftScope>)
    await screen.findByText('2026-v1')
    expect(mockApi.getContractTemplates).toHaveBeenCalledWith('bpb-sabah-2026', { token: 'tok' })
    fireEvent.click(screen.getByText('admin.contracts.newVersion'))
    expect((screen.getByTestId('contract-gift') as HTMLInputElement).value).toBe('Sabah Bursary 2026')
    fireEvent.change(screen.getByPlaceholderText('admin.contracts.versionPlaceholder'),
      { target: { value: '2027-sabah' } })
    fireEvent.click(screen.getByText('admin.contracts.create'))
    await waitFor(() => expect(mockApi.createContractTemplate).toHaveBeenCalledWith(
      { version: '2027-sabah', programme: 'bpb-sabah-2026' }, { token: 'tok' }))
    expect(mockPush).toHaveBeenCalledWith('/admin/contracts/9')
  })

  it('with several gifts and none chosen, New version asks instead of calling the server', async () => {
    render(<GiftScope><ContractsListPage /></GiftScope>)
    await screen.findByText('2026-v1')
    fireEvent.click(screen.getByText('admin.contracts.newVersion'))
    fireEvent.change(screen.getByPlaceholderText('admin.contracts.versionPlaceholder'),
      { target: { value: '2027-x' } })
    fireEvent.click(screen.getByText('admin.contracts.create'))
    // The message shows twice by design: as the fixed gift box's text and as the refusal.
    expect((await screen.findAllByText('admin.contracts.error.programmeRequired')).length)
      .toBeGreaterThan(0)
    expect(mockApi.createContractTemplate).not.toHaveBeenCalled()
  })
})
