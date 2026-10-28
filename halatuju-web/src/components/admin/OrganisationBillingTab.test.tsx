/**
 * @jest-environment jsdom
 *
 * "Billing" — the third tab of ORGANISATION → Settings (2026-10-28).
 *
 * The owner's ruling put this tab on a page an org_admin can open, which moves one write from
 * super-only to tenant-writable. The SERVER holds that fence (proven through the endpoint from the
 * widening side in `test_invoice_settings_homes.py`); what this file holds is the screen's half of
 * the bargain — it never sends an organisation the read did not resolve, and it says plainly that
 * an edit reaches the NEXT invoice only.
 */
import { fireEvent, render, waitFor, within } from '@testing-library/react'
import OrganisationBillingTab from './OrganisationBillingTab'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/admin-api')
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok' }) }))
let linkParam: string | null = null
jest.mock('next/navigation', () => ({ useSearchParams: () => ({ get: () => linkParam }) }))

const mockApi = api as jest.Mocked<typeof api>

function details(over: Partial<api.TenantBillingDetails> = {}): api.TenantBillingDetails {
  return {
    organisation_id: 11, organisation: 'BrightPath', organisation_code: 'brightpath',
    bill_to_name: 'BrightPath Bursary', address: 'Desa ParkCity',
    emails: ['finance@bp.example'], missing: [], ...over,
  }
}

beforeEach(() => {
  jest.clearAllMocks()
  linkParam = null
  mockApi.getOrgBillingDetails.mockResolvedValue(details())
  mockApi.saveOrgBillingDetails.mockResolvedValue(details())
})

describe('the organisation editing its own', () => {
  it('loads with no code and shows what is stored', async () => {
    const { container } = render(<OrganisationBillingTab />)
    await waitFor(() => within(container).getByTestId('org-billing-tab'))
    expect(mockApi.getOrgBillingDetails).toHaveBeenCalledWith(undefined, { token: 'tok' })
    expect(container.querySelector('input')?.value).toBe('BrightPath Bursary')
  })

  it('says an edit reaches the NEXT invoice only', async () => {
    // Without this the tab reads as "edit your past invoices", which it is not: an issued invoice
    // carries a frozen copy and nothing here can reach it.
    const { container } = render(<OrganisationBillingTab />)
    await waitFor(() => within(container).getByTestId('org-billing-tab'))
    expect(within(container).getByText('admin.orgBilling.nextInvoiceOnly')).not.toBeNull()
  })

  it('sends back the code the READ resolved, never an empty guess', async () => {
    // ⚠ The save must name the same organisation that is on screen. Sending nothing would let the
    // server resolve a different one the day a second tenant exists.
    const { container } = render(<OrganisationBillingTab />)
    await waitFor(() => within(container).getByTestId('org-billing-tab'))
    fireEvent.change(container.querySelectorAll('input')[0], { target: { value: 'BrightPath Berhad' } })
    fireEvent.click(within(container).getByText('admin.orgBilling.save'))
    await waitFor(() => expect(mockApi.saveOrgBillingDetails).toHaveBeenCalled())
    expect(mockApi.saveOrgBillingDetails.mock.calls[0][0]).toMatchObject({
      organisation: 'brightpath', bill_to_name: 'BrightPath Berhad',
    })
  })

  it('splits the inbox list into addresses on the wire', async () => {
    const { container } = render(<OrganisationBillingTab />)
    await waitFor(() => within(container).getByTestId('org-billing-tab'))
    const inputs = container.querySelectorAll('input')
    fireEvent.change(inputs[inputs.length - 1],
      { target: { value: 'a@bp.example; b@bp.example , a@bp.example' } })
    fireEvent.click(within(container).getByText('admin.orgBilling.save'))
    await waitFor(() => expect(mockApi.saveOrgBillingDetails).toHaveBeenCalled())
    expect(mockApi.saveOrgBillingDetails.mock.calls[0][0].emails)
      .toEqual(['a@bp.example', 'b@bp.example'])
  })

  it('sleeps until something changes', async () => {
    const { container } = render(<OrganisationBillingTab />)
    await waitFor(() => within(container).getByTestId('org-billing-tab'))
    const save = within(container).getByText('admin.orgBilling.save') as HTMLButtonElement
    expect(save.disabled).toBe(true)
    fireEvent.change(container.querySelectorAll('input')[0], { target: { value: 'Changed' } })
    expect(save.disabled).toBe(false)
  })

  it('reports a refused email rather than looking saved', async () => {
    mockApi.saveOrgBillingDetails.mockRejectedValue(
      Object.assign(new Error('400'), { body: { code: 'bad_email' } }))
    const { container } = render(<OrganisationBillingTab />)
    await waitFor(() => within(container).getByTestId('org-billing-tab'))
    fireEvent.change(container.querySelectorAll('input')[0], { target: { value: 'X' } })
    fireEvent.click(within(container).getByText('admin.orgBilling.save'))
    await waitFor(() => expect(within(container).getByTestId('org-billing-outcome').textContent)
      .toBe('admin.orgBilling.bad_email'))
  })
})

describe('a super with more than one tenant', () => {
  it('is asked WHICH, and never shown a guess', async () => {
    // The server refuses rather than picking. The tab must show the choice, not an empty form
    // that would save against whichever organisation the server happened to resolve.
    mockApi.getOrgBillingDetails.mockRejectedValueOnce(Object.assign(new Error('400'), {
      body: { code: 'organisation_required', organisations: ['alpha', 'brightpath'] } }))
    const { container } = render(<OrganisationBillingTab />)
    const picker = await waitFor(() => within(container).getByTestId('billing-org-picker'))
    expect(within(container).queryByTestId('org-billing-tab')).toBeNull()

    fireEvent.click(within(picker).getByText('brightpath'))
    await waitFor(() => within(container).getByTestId('org-billing-tab'))
    expect(mockApi.getOrgBillingDetails).toHaveBeenLastCalledWith('brightpath', { token: 'tok' })
  })

  it('shows a plain failure when the read fails for any other reason', async () => {
    mockApi.getOrgBillingDetails.mockRejectedValue(new Error('500'))
    const { container } = render(<OrganisationBillingTab />)
    await waitFor(() => within(container).getByRole('alert'))
    expect(within(container).queryByTestId('billing-org-picker')).toBeNull()
  })
})

describe('arriving from the Billing & usage card', () => {
  it('opens the organisation the link names, with no picker in between', async () => {
    // The card already said WHICH organisation is blocked. Asking again would be the console
    // forgetting what it just told the reader.
    // With a code in hand the FIRST call already names the organisation, so the server never
    // asks — which is the whole point. (Mocking a refusal here would be testing a server that
    // was given a code and asked anyway.)
    linkParam = 'brightpath'
    const { container } = render(<OrganisationBillingTab />)
    await waitFor(() => within(container).getByTestId('org-billing-tab'))
    expect(mockApi.getOrgBillingDetails).toHaveBeenCalledWith('brightpath', { token: 'tok' })
    expect(within(container).queryByTestId('billing-org-picker')).toBeNull()
  })
})
