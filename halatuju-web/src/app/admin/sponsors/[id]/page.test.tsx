/**
 * @jest-environment jsdom
 *
 * Sponsor detail — the wallet-credit controls (S2, 2026-07-28).
 *
 * The endpoints have been live and org-fenced since P4b; until this sprint nothing called
 * them, so every credit on production was keyed in by a developer. What these tests protect
 * is the WIRING: that the right endpoint is called with the typed signature, that the record
 * re-reads after a mutation (so the tiles cannot disagree with the database), and that a
 * control is never drawn for a step this viewer's role cannot take.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import AdminSponsorDetailPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
jest.mock('next/navigation', () => ({ useParams: () => ({ id: '5' }) }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

let viewerRole: { role: string; is_super_admin?: boolean } = { role: 'admin' }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: viewerRole }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const credit = (over: Partial<api.AdminSponsorCredit> = {}): api.AdminSponsorCredit => ({
  id: 11,
  programme_id: 7,
  programme_name: 'BrightPath Bursary',
  amount: '10000.00',
  source: 'admin_recorded',
  external_reference: 'TRF-88214',
  status: 'draft',
  is_spendable: false,
  recorded_by: '',
  recorded_at: null,
  finance_checked_by: '',
  finance_checked_at: null,
  confirmed_by: '',
  confirmed_at: null,
  created_at: '2026-07-27T02:00:00Z',
  ...over,
})

const detail = (over: Partial<api.AdminSponsorDetail> = {}): api.AdminSponsorDetail => ({
  id: 5,
  name: 'Bharathan Nair',
  email: 'nair@example.com',
  phone: '',
  organisation: '',
  source: '',
  note: '',
  status: 'approved',
  is_trusted: false,
  created_at: '2026-07-15T00:00:00Z',
  reviewed_at: null,
  reviewed_by: '',
  last_seen_at: null,
  consent_at: null,
  consent_version: '',
  notify_frequency: 'weekly',
  last_digest_sent_at: null,
  programmes: [{
    programme_id: 7, programme_name: 'BrightPath Bursary',
    given: '20000.00', committed: '0.00', available: '20000.00', credits: 2, students: 0,
  }],
  credits: [credit()],
  sponsorships: [],
  referrals: [],
  memberships: [{
    programme_id: 7, programme_name: 'BrightPath Bursary',
    status: 'approved', vetted_by: '', vetted_at: null,
  }],
  // Two gifts, one held and one NOT — the only shape that can prove the accept panel offers a
  // gift the benefactor is not yet in. A one-gift fixture would pass either way.
  assignable_programmes: [
    { id: 7, code: 'flagship', name: 'BrightPath Bursary', is_active: true },
    { id: 9, code: 'sabah', name: 'Sabah Bursary', is_active: false },
  ],
  finance_check_required: false,
  fenced: false,
  ...over,
})

beforeEach(() => {
  jest.clearAllMocks()
  viewerRole = { role: 'admin' }
  mockApi.getSponsorDetail.mockResolvedValue(detail())
})

const open = async () => {
  render(<AdminSponsorDetailPage />)
  await waitFor(() => expect(screen.getByText('Bharathan Nair')).toBeTruthy())
}

describe('recording a credit', () => {
  it('offers it to the maker', async () => {
    await open()
    expect(screen.getByRole('button', { name: /recordCredit/ })).toBeTruthy()
  })

  it('never offers it to the approver — they have to stay free to countersign', async () => {
    viewerRole = { role: 'org_admin' }
    await open()
    expect(screen.queryByRole('button', { name: /recordCredit/ })).toBeNull()
  })

  it('offers it to a super', async () => {
    viewerRole = { role: 'reviewer', is_super_admin: true }
    await open()
    expect(screen.getByRole('button', { name: /recordCredit/ })).toBeTruthy()
  })

  it('posts the sponsor, the gift, the amount and the bank ref, then re-reads the record', async () => {
    mockApi.recordSponsorCredit.mockResolvedValue(credit())
    await open()
    fireEvent.click(screen.getByRole('button', { name: /recordCredit/ }))

    fireEvent.change(screen.getByPlaceholderText('10000'), { target: { value: '3000' } })
    fireEvent.change(screen.getByPlaceholderText('TRF-88214'), { target: { value: 'TRF-99001' } })
    fireEvent.click(screen.getByRole('button', { name: /recordSave/ }))

    await waitFor(() => expect(mockApi.recordSponsorCredit).toHaveBeenCalledWith(
      { sponsor_id: 5, programme_id: 7, amount: '3000', external_reference: 'TRF-99001' },
      { token: 'tok' },
    ))
    // Confirming money moves the wallet tiles too, so the whole record is re-fetched.
    await waitFor(() => expect(mockApi.getSponsorDetail).toHaveBeenCalledTimes(2))
  })

  it('will not submit without the bank reference — it is the only thread back to the money', async () => {
    await open()
    fireEvent.click(screen.getByRole('button', { name: /recordCredit/ }))
    fireEvent.change(screen.getByPlaceholderText('10000'), { target: { value: '3000' } })
    expect((screen.getByRole('button', { name: /recordSave/ }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('does not offer it at all when the sponsor is in no gift', async () => {
    mockApi.getSponsorDetail.mockResolvedValue(detail({ memberships: [] }))
    await open()
    expect(screen.queryByRole('button', { name: /recordCredit/ })).toBeNull()
  })
})

/**
 * Accepting a benefactor into a gift (S-ASSIGN, 2026-09-04).
 *
 * This panel is what unblocks the money: `record_admin_credit` refuses
 * `sponsor_not_in_programme` without an approved row, and before it existed the only writer
 * hard-coded the flagship — so a second gift's first credit needed an engineer writing SQL.
 */
describe('accepting into a gift', () => {
  const asOrgAdmin = async () => {
    viewerRole = { role: 'org_admin' }
    await open()
  }

  it('offers the gift the benefactor is NOT in yet — the whole point of the panel', async () => {
    await asOrgAdmin()
    // Two buttons, one per gift: Accept for Sabah (no membership), Take back for the flagship
    // (already approved). A panel built from `memberships` alone could draw only the second.
    expect(screen.getAllByRole('button', { name: /giftAccept/ }).length).toBe(1)
    expect(screen.getAllByRole('button', { name: /giftTakeBack/ }).length).toBe(1)
  })

  it('says a gift is not open yet rather than leaving it blank', async () => {
    await asOrgAdmin()
    expect(screen.getByText(/giftNotOpen/)).toBeTruthy()
  })

  it('posts the gift and the status, then re-reads the whole record', async () => {
    mockApi.setSponsorMembership.mockResolvedValue(
      { programme_id: 9, programme: 'sabah', status: 'approved' })
    await asOrgAdmin()
    fireEvent.click(screen.getByRole('button', { name: /giftAccept/ }))

    await waitFor(() => expect(mockApi.setSponsorMembership).toHaveBeenCalledWith(
      5, { programme_id: 9, status: 'approved' }, { token: 'tok' }))
    // An acceptance changes what may be CREDITED, so a local row patch would leave the credit
    // form offering a gift the database disagrees about.
    await waitFor(() => expect(mockApi.getSponsorDetail).toHaveBeenCalledTimes(2))
  })

  it('takes an acceptance back with `rejected`, never by deleting the row', async () => {
    mockApi.setSponsorMembership.mockResolvedValue(
      { programme_id: 7, programme: 'flagship', status: 'rejected' })
    await asOrgAdmin()
    fireEvent.click(screen.getByRole('button', { name: /giftTakeBack/ }))
    await waitFor(() => expect(mockApi.setSponsorMembership).toHaveBeenCalledWith(
      5, { programme_id: 7, status: 'rejected' }, { token: 'tok' }))
  })

  it('draws no control for a plain admin — who may fund your students is the org admin’s call', async () => {
    // ⚠ The OPPOSITE gate to recording a credit, which this same `admin` may do. Deliberate:
    // recording is bookkeeping; deciding who may fund your students is the organisation's.
    await open()   // role 'admin'
    expect(screen.queryByRole('button', { name: /giftAccept/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /giftTakeBack/ })).toBeNull()
    // …but the gifts are still LISTED, so they can see where the benefactor stands.
    expect(screen.getByText('Sabah Bursary')).toBeTruthy()
  })

  it('names the reason when the server refuses', async () => {
    mockApi.setSponsorMembership.mockRejectedValue({ code: 'account_not_approved' })
    await asOrgAdmin()
    fireEvent.click(screen.getByRole('button', { name: /giftAccept/ }))
    await waitFor(() => expect(
      screen.getByText(/giftError\.account_not_approved/)).toBeTruthy())
  })

  it('falls back to a plain message on an unrecognised code, never a raw key path', async () => {
    // `t()` returns the key on a miss, so interpolating a new server code would print
    // `admin.sponsors.detail.giftError.some_new_code` on screen. That has shipped here before.
    mockApi.setSponsorMembership.mockRejectedValue({ code: 'some_new_code' })
    await asOrgAdmin()
    fireEvent.click(screen.getByRole('button', { name: /giftAccept/ }))
    await waitFor(() => expect(screen.getByText(/giftError\.unknown/)).toBeTruthy())
  })
})

describe('signing a credit', () => {
  it('sends the TYPED name, and refuses to submit an empty one', async () => {
    mockApi.signSponsorCredit.mockResolvedValue(credit({ status: 'admin_signed' }))
    await open()
    const sign = screen.getByRole('button', { name: /sign\.recorded/ })
    expect((sign as HTMLButtonElement).disabled).toBe(true)   // a click alone is not a signature

    fireEvent.change(screen.getByLabelText(/fullName/), { target: { value: 'Poongulali Veeran' } })
    fireEvent.click(sign)
    await waitFor(() => expect(mockApi.signSponsorCredit)
      .toHaveBeenCalledWith(11, 'Poongulali Veeran', { token: 'tok' }))
    await waitFor(() => expect(mockApi.getSponsorDetail).toHaveBeenCalledTimes(2))
  })

  it('shows the approver WHY they cannot countersign while finance is outstanding', async () => {
    viewerRole = { role: 'org_admin' }
    mockApi.getSponsorDetail.mockResolvedValue(detail({
      credits: [credit({ status: 'admin_signed', recorded_by: 'Poongulali Veeran', recorded_at: '2026-07-27T02:30:00Z' })],
      finance_check_required: true,
    }))
    await open()
    expect(screen.getByText('admin.sponsors.detail.awaitingFinanceCheck')).toBeTruthy()
    expect(screen.queryByRole('button', { name: /sign\./ })).toBeNull()
  })

  it('renders a mapped message for a server refusal, never a raw key path', async () => {
    const err = Object.assign(new Error('same_signer'), { code: 'same_signer' })
    mockApi.signSponsorCredit.mockRejectedValue(err)
    await open()
    fireEvent.change(screen.getByLabelText(/fullName/), { target: { value: 'Poongulali Veeran' } })
    fireEvent.click(screen.getByRole('button', { name: /sign\.recorded/ }))
    await waitFor(() => expect(
      screen.getByText('admin.sponsors.detail.creditError.same_signer')).toBeTruthy())
  })

  it('falls back to known copy for a code it has never seen', async () => {
    const err = Object.assign(new Error('nope'), { code: 'a_brand_new_code' })
    mockApi.signSponsorCredit.mockRejectedValue(err)
    await open()
    fireEvent.change(screen.getByLabelText(/fullName/), { target: { value: 'Poongulali Veeran' } })
    fireEvent.click(screen.getByRole('button', { name: /sign\.recorded/ }))
    await waitFor(() => expect(
      screen.getByText('admin.sponsors.detail.creditError.unknown')).toBeTruthy())
  })
})

describe('voiding a credit', () => {
  it('voids an unconfirmed credit and re-reads', async () => {
    mockApi.voidSponsorCredit.mockResolvedValue(credit({ status: 'cancelled' }))
    await open()
    fireEvent.click(screen.getByRole('button', { name: /detail\.void/ }))
    await waitFor(() => expect(mockApi.voidSponsorCredit).toHaveBeenCalledWith(11, { token: 'tok' }))
    await waitFor(() => expect(mockApi.getSponsorDetail).toHaveBeenCalledTimes(2))
  })

  it('is never offered on confirmed money — that is reversed by a compensating entry', async () => {
    mockApi.getSponsorDetail.mockResolvedValue(detail({
      credits: [credit({
        status: 'confirmed',
        recorded_by: 'Poongulali Veeran', recorded_at: '2026-07-27T02:00:00Z',
        confirmed_by: 'Suresh Thirugnanam', confirmed_at: '2026-07-27T03:00:00Z',
      })],
    }))
    await open()
    expect(screen.queryByRole('button', { name: /detail\.void/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /sign\./ })).toBeNull()
  })
})
