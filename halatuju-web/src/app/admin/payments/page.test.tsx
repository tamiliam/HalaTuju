/**
 * @jest-environment jsdom
 *
 * The funding summary's "Last paid" column (BrightPath request #5, 2026-08-01).
 *
 * It used to read `PR-2026-07-26-01 · 26/07/2026` — the payment run's reference and the date it
 * was paid, joined by a dot. The column is headed with a question about WHEN, and the reference
 * answered a different one while earning very little (it is not clickable), so the requester asked
 * for the date alone. What this pins is the pair that is easy to regress together: the date must
 * still be there, and the reference must not creep back beside it.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import PaymentsLandingPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
// ⚠ `owning_org_id` matters — the picker filters the scope list on it, because the server reads
// `org = admin.owning_organisation` even for a super.
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({
    token: 'tok', role: { role: 'admin', is_super_admin: true, owning_org_id: 11 },
  }),
}))
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn() }) }))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const FUNDING = {
  rows: [
    {
      application_id: 1, name: 'RASEKA A/P MURUGESE', ref: 'B40-0119', status: 'active',
      award_amount: '3000', paid_to_date: '1000', remaining: '2000', vircle_id: '1234567890123',
      last_run: { reference: 'PR-2026-07-26-01', payment_date: '2026-07-26' },
      programme: 'B40',
    },
    {
      application_id: 2, name: 'NEVER PAID', ref: 'B40-0200', status: 'active',
      award_amount: '3000', paid_to_date: '0', remaining: '3000', vircle_id: '',
      last_run: null, programme: 'B40',
    },
  ],
  totals: { students: 2, award_total: '6000', paid_total: '1000', remaining_total: '5000' },
} as unknown as api.FundingSummary

// `is_active` arrived on the scopes payload on 2026-09-03, when the endpoint started offering
// gifts that are not switched on yet (they are configured before they are switched on). These
// fixtures are all ACTIVE gifts — a payment run is only ever made against one — so the flag is
// true and this file's behaviour is unchanged.
const programme = (id: number, code: string, name: string, organisation_id = 11) =>
  ({ id, code, name, organisation_id, is_active: true })

const scopes = (...programmes: ReturnType<typeof programme>[]) =>
  ({ organisations: [{ id: 11, code: 'brightpath', name: 'BrightPath' }], programmes })

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getPaymentRuns.mockResolvedValue({ runs: [] } as unknown as Awaited<ReturnType<typeof api.getPaymentRuns>>)
  mockApi.getFundingSummary.mockResolvedValue(FUNDING)
  // One gift, which is BrightPath's world today.
  mockApi.getAdminScopes.mockResolvedValue(scopes(programme(1, 'brightpath-flagship', 'BrightPath Bursary')))
})

/**
 * Which gift a run pays from (Sabah S1, 2026-09-02).
 *
 * ⚠ THE DEFECT THIS CLOSES IS IN THE LIVE PAYOUT PATH, AND IT IS NOT A SABAH FEATURE.
 * `create_run` takes the programme positionally and required (P2b), and the endpoint refuses with
 * `programme_required` when the organisation runs more than one — never a silent pick. The screen
 * never sent one and did not know that error code, so **the day a second programme row exists,
 * BrightPath's own monthly run fails here with an unexplained message.**
 */
describe('which gift the run pays from', () => {
  const openDialog = async () => {
    render(<PaymentsLandingPage />)
    await screen.findByText('26/07/2026')
    fireEvent.click(screen.getByText(/admin.payments.newRun/))
  }

  /*
   * ⚠⚠ **THREE TESTS WERE REPLACED HERE, NOT DELETED — TD-241, owner, 2026-09-11.**
   *
   * Payments moved from the Organisation section to the PROGRAMME section, so the BREADCRUMB
   * names the gift and the page's own picker was removed. The old three asserted the picker:
   * that it stayed hidden with one gift, that it appeared and blocked submission with two, and
   * that it offered only the caller's own organisation's gifts. There is no picker to assert.
   *
   * **What must NOT be lost with it is the SAFETY those tests protected**, and it is all still
   * here, one layer down:
   *   * nothing is guessed — the page sends whatever the breadcrumb resolved, and `undefined`
   *     when it could not say;
   *   * the SERVER refuses `programme_required` rather than picking between two gifts, and the
   *     screen still explains that in words (the test below this block, untouched);
   *   * a gift from another tenant is a 404, proved at the endpoint in `test_payment_programme`.
   *
   * Do not "restore" the picker. Two controls answering "which gift" is two chances to create a
   * run against a gift you are not looking at, on the one screen where that moves money.
   */
  it('sends the gift the BREADCRUMB resolved, without asking again', async () => {
    await openDialog()
    // No picker: the crumb above the page already says which gift, and it is not repeated here.
    expect(screen.queryByLabelText('admin.payments.programme')).toBeNull()

    fireEvent.change(screen.getByLabelText('admin.payments.paymentDate'),
                     { target: { value: '2999-01-05' } })
    fireEvent.click(screen.getByText('admin.payments.createDraft'))

    await waitFor(() => expect(mockApi.createPaymentRun).toHaveBeenCalled())
    // A CODE now, not an id — and `undefined` here because the harness mounts outside the shell,
    // so `useProgrammeParam` has no scope to read. That is the "could not say" case, and the
    // server answers it by resolving the org's only gift or refusing. Never by guessing.
    expect(mockApi.createPaymentRun.mock.calls[0][2]).toBeUndefined()
  })

  it('⚠ THE CREATE BUTTON IS NO LONGER BLOCKED BY A GIFT CONTROL', async () => {
    // It was disabled until the picker had a value. With the picker gone, only the DATE can
    // block it — and if a gift is genuinely missing the server says so in words, which is a
    // better failure than a button that will not press with nothing explaining why.
    await openDialog()
    const create = screen.getByText('admin.payments.createDraft') as HTMLButtonElement
    expect(create.disabled).toBe(true)                       // no date yet
    fireEvent.change(screen.getByLabelText('admin.payments.paymentDate'),
                     { target: { value: '2999-01-05' } })
    expect(create.disabled).toBe(false)
  })

  it('asks the server for the runs and the funding of the SAME gift', async () => {
    // ⚠ One gift, or the list and the money summary on one screen describe two different funds.
    render(<PaymentsLandingPage />)
    await screen.findByText('26/07/2026')
    expect(mockApi.getPaymentRuns.mock.calls[0][0])
      .toEqual(mockApi.getFundingSummary.mock.calls[0][0])
  })

  it('explains `programme_required` in words instead of failing blankly', async () => {
    // Reachable even with the picker shipped: a programme created after this page loaded is not
    // in the list, so the screen sends nothing and the server refuses.
    mockApi.createPaymentRun.mockRejectedValueOnce(
      Object.assign(new Error('bad'), { code: 'programme_required' }))
    await openDialog()
    fireEvent.change(screen.getByLabelText('admin.payments.paymentDate'), { target: { value: '2999-01-05' } })
    fireEvent.click(screen.getByText('admin.payments.createDraft'))
    // TWO nodes, and that is pre-existing: one `error` state feeds both the page banner and the
    // dialog, so every create failure has always appeared twice while the dialog is open. Pinned
    // as-is rather than "fixed" — it is not this sprint's, and asserting one would hide it.
    expect((await screen.findAllByText('admin.payments.programmeRequired')).length).toBe(2)
  })

  it('falls back SAFELY when the scope list cannot be fetched', async () => {
    // No list → no picker → nothing sent → the server resolves the single gift, or refuses.
    // A failed fetch can never cause a run to be paid from the wrong fund.
    mockApi.getAdminScopes.mockRejectedValue(new Error('offline'))
    await openDialog()
    expect(screen.queryByLabelText('admin.payments.programme')).toBeNull()
    fireEvent.change(screen.getByLabelText('admin.payments.paymentDate'), { target: { value: '2999-01-05' } })
    expect((screen.getByText('admin.payments.createDraft') as HTMLButtonElement).disabled).toBe(false)
  })
})

describe('the Last paid column', () => {
  it('shows the date on its own', async () => {
    render(<PaymentsLandingPage />)
    expect(await screen.findByText('26/07/2026')).toBeTruthy()
  })

  it('no longer shows the payment run reference beside it', async () => {
    render(<PaymentsLandingPage />)
    await screen.findByText('26/07/2026')
    // Neither joined to the date nor standing alone in that cell.
    expect(screen.queryByText(/PR-2026-07-26-01/)).toBeNull()
  })

  it('still says nothing at all for a student who has never been paid', async () => {
    render(<PaymentsLandingPage />)
    await screen.findByText('26/07/2026')
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })
})
