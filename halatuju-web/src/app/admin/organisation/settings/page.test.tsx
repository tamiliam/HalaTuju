/**
 * @jest-environment jsdom
 *
 * NAVKEYS review (2026-11-16): Organisation → Settings wires the Billing tab to the served doors, at PAGE
 * level, so a wrong door here fails this file:
 *   · the tab is offered only with `billing_read` (`billing.view`) — the server's read of the bill-to;
 *   · inside it the bill-to is read-only, with no Save, without `billing_write` (`billing.edit`) — the
 *     server's write (O15: an organisation admin holds it by role, a team member never can).
 * The other three tabs are stubbed: this file is about the Billing tab's wiring only.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'

import AdminOrganisationSettingsPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
let mockViewer: Record<string, unknown> = {}
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: mockViewer }) }))
jest.mock('next/navigation', () => ({ useSearchParams: () => ({ get: () => null }) }))
jest.mock('@/lib/admin-api')
jest.mock('@/components/admin/OrganisationColoursTab', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/admin/OrganisationConfigurationTab', () => ({ __esModule: true, default: () => null }))
jest.mock('@/components/admin/StudentCommsTab', () => ({ __esModule: true, default: () => null }))
const mockApi = api as jest.Mocked<typeof api>

beforeEach(() => {
  jest.clearAllMocks()
  mockViewer = jest.requireActual('@/test/staffPresets').servedViewer('org_admin')
  mockApi.getOrgBillingDetails.mockResolvedValue({
    organisation_id: 11, organisation: 'BrightPath', organisation_code: 'brightpath',
    bill_to_name: 'BrightPath Bursary', address: 'Desa ParkCity', emails: ['finance@bp.example'], missing: [],
  })
})

const openBilling = async () => {
  render(<AdminOrganisationSettingsPage />)
  fireEvent.click(screen.getByTestId('tab-billing'))
  const tab = await waitFor(() => screen.getByTestId('org-billing-tab'))
  await waitFor(() => expect((tab.querySelector('input') as HTMLInputElement).value).toBe('BrightPath Bursary'))
  return tab
}
const boxesReadOnly = (tab: HTMLElement) =>
  Array.from(tab.querySelectorAll('input, textarea')).map((b) => (b as HTMLInputElement).readOnly)

describe('NAVKEYS review: the Settings Billing tab follows the billing doors', () => {
  it('an organisation admin (served billing.view + billing.edit) gets the tab and saves the bill-to', async () => {
    const tab = await openBilling()
    expect(boxesReadOnly(tab).every((r) => r === false)).toBe(true)
    expect(within(tab).getByText('admin.orgBilling.save')).toBeTruthy()
  })

  it('settings.edit + billing.view: the tab shows, read-only, with no Save', async () => {
    mockViewer = { role: 'admin', is_super_admin: false, permissions: [], page_keys: ['settings.edit', 'billing.view'] }
    const tab = await openBilling()
    expect(boxesReadOnly(tab).length).toBeGreaterThan(0)
    expect(boxesReadOnly(tab).every((r) => r === true)).toBe(true)
    expect(within(tab).queryByText('admin.orgBilling.save')).toBeNull()
  })

  it('settings.edit alone: no Billing tab (its read would be refused), the other tabs stay', () => {
    mockViewer = { role: 'admin', is_super_admin: false, permissions: [], page_keys: ['settings.edit'] }
    render(<AdminOrganisationSettingsPage />)
    expect(screen.queryByTestId('tab-billing')).toBeNull()
    expect(screen.getByTestId('tab-colours')).toBeTruthy()
    expect(mockApi.getOrgBillingDetails).not.toHaveBeenCalled()
  })
})
