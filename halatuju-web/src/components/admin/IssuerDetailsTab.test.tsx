/**
 * @jest-environment jsdom
 *
 * "Your details" on Platform → Billing (2026-10-28).
 *
 * ⚠ THE TEST THAT CARRIES THIS FILE is `the bank boxes are their own group`. The owner filled the
 * old flat form by typing an address straight down it: the postcode landed in Phone and the city
 * landed in Bank, because nine boxes in one column read as one continuous thing. The grouping is
 * the fix, so it is asserted rather than left to survive the next person who tidies the layout.
 */
import { fireEvent, render, waitFor, within } from '@testing-library/react'
import IssuerDetailsTab from './IssuerDetailsTab'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/admin-api')
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k}:${Object.values(v).join('|')}` : k), locale: 'en' }) }))
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok' }) }))

const mockApi = api as jest.Mocked<typeof api>

function issuer(over: Partial<api.InvoiceIssuerSettings> = {}): api.InvoiceIssuerSettings {
  return {
    legal_name: 'Elanjelian Venugopal', registration_no: '',
    address: '2, JALAN P18K 1/2\n62150 PUTRAJAYA', email: 'tamiliam@gmail.com', phone: '',
    bank_name: 'Maybank', bank_account_name: 'ELANJELIAN A/L VENUGOPAL',
    bank_account_no: '102103109179', payment_terms_days: 30, missing: [], ...over,
  }
}

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getInvoiceIssuer.mockResolvedValue({ issuer: issuer() })
  mockApi.saveInvoiceIssuer.mockResolvedValue({ issuer: issuer() })
})

describe('the form that caused this sprint', () => {
  it('puts the bank boxes in their own group, so the address column visibly ends', async () => {
    const { container } = render(<IssuerDetailsTab />)
    await waitFor(() => within(container).getByTestId('issuer-tab'))
    const bank = within(container).getByTestId('issuer-group-bank')
    // The three bank boxes are together, and the address is NOT among them.
    for (const f of ['bank_name', 'bank_account_name', 'bank_account_no']) {
      expect(within(bank).getByText(`admin.issuer.field.${f}`)).not.toBeNull()
    }
    expect(within(bank).queryByText('admin.issuer.field.address')).toBeNull()
    expect(within(bank).queryByText('admin.issuer.field.phone')).toBeNull()
    // ...and the address sits with the name, under its own heading.
    const who = within(container).getByTestId('issuer-group-who')
    expect(within(who).getByText('admin.issuer.field.address')).not.toBeNull()
  })

  it('names the bank field as a NAME, never the bare word that invited a city', async () => {
    const { container } = render(<IssuerDetailsTab />)
    await waitFor(() => within(container).getByTestId('issuer-tab'))
    // The label key itself carries the fix; a later rename back to "Bank" fails here.
    expect(within(container).getByText('admin.issuer.field.bank_name')).not.toBeNull()
  })
})

describe('what it tells the reader', () => {
  it('says nothing can be issued while required fields are blank, and names them', async () => {
    mockApi.getInvoiceIssuer.mockResolvedValue({
      issuer: issuer({ legal_name: '', bank_name: '', missing: ['legal_name', 'bank_name'] }) })
    const { container } = render(<IssuerDetailsTab />)
    const note = await waitFor(() => within(container).getByTestId('issuer-missing'))
    expect(note.textContent).toContain('admin.issuer.field.legal_name')
    expect(note.textContent).toContain('admin.issuer.field.bank_name')
  })

  it('shows no warning once everything required is filled in', async () => {
    const { container } = render(<IssuerDetailsTab />)
    await waitFor(() => within(container).getByTestId('issuer-tab'))
    expect(within(container).queryByTestId('issuer-missing')).toBeNull()
  })
})

describe('saving', () => {
  it('sleeps until something actually changes', async () => {
    const { container } = render(<IssuerDetailsTab />)
    await waitFor(() => within(container).getByTestId('issuer-tab'))
    const save = within(container).getByText('admin.issuer.save') as HTMLButtonElement
    expect(save.disabled).toBe(true)
    fireEvent.change(container.querySelectorAll('input')[0], { target: { value: 'New Name' } })
    expect(save.disabled).toBe(false)
  })

  it('leaves a blank "days to pay" OUT rather than sending zero', async () => {
    // A zero would make every future invoice due on the day it is issued — an aggressive term
    // nobody chose, arrived at by clearing a box.
    const { container } = render(<IssuerDetailsTab />)
    await waitFor(() => within(container).getByTestId('issuer-tab'))
    const inputs = container.querySelectorAll('input')
    fireEvent.change(inputs[inputs.length - 1], { target: { value: '' } })
    fireEvent.click(within(container).getByText('admin.issuer.save'))
    await waitFor(() => expect(mockApi.saveInvoiceIssuer).toHaveBeenCalled())
    expect(mockApi.saveInvoiceIssuer.mock.calls[0][0]).not.toHaveProperty('payment_terms_days')
  })

  it('says what the server refused, in the server own words', async () => {
    const err = Object.assign(new Error('400'), { body: { code: 'bad_email' } })
    mockApi.saveInvoiceIssuer.mockRejectedValue(err)
    const { container } = render(<IssuerDetailsTab />)
    await waitFor(() => within(container).getByTestId('issuer-tab'))
    fireEvent.change(container.querySelectorAll('input')[0], { target: { value: 'X' } })
    fireEvent.click(within(container).getByText('admin.issuer.save'))
    await waitFor(() => expect(within(container).getByTestId('issuer-outcome').textContent)
      .toBe('admin.issuer.bad_email'))
  })

  it('says nothing at all before anything has happened', async () => {
    // The console's idle rule: a greyed button already says there is nothing to save.
    const { container } = render(<IssuerDetailsTab />)
    await waitFor(() => within(container).getByTestId('issuer-tab'))
    expect(within(container).getByTestId('issuer-outcome').textContent).toBe('')
  })
})
