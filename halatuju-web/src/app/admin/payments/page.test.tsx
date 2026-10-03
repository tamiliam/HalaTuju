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
import GiftProgrammes from '@/components/admin/GiftProgrammes'
import { GiftScope, TWO_GIFTS, crumbText } from '@/test/giftScope'
import { hasGiftDoor } from '@/lib/navigation'

// `t` echoes its key — except "Pays from", whose NAME is the point of asserting it, and the
// TD-244 wallet line, whose count and NAMES are.
jest.mock('@/lib/i18n', () => ({ useT: () => ({
  t: (k: string, p?: Record<string, string>) => (k === 'admin.payments.paysFrom' ? `${k}:${p?.name}`
    : k === 'admin.payments.funding.walletNotLive' ? `${k}:${p?.count}:${p?.names}` : k),
  locale: 'en',
}) }))
// ⚠ `owning_org_id` matters — the picker filters the scope list on it, because the server reads
// `org = admin.owning_organisation` even for a super.
// The role is a mutable cell so the gift-gate tests can sign in as each role in turn; every older
// test in this file keeps the role it always had.
const DEFAULT_ROLE = { role: 'admin', is_super_admin: true, owning_org_id: 11 }
let mockRole: Record<string, unknown> = DEFAULT_ROLE
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: mockRole }),
}))
const mockPush = jest.fn()
const mockReplace = jest.fn()
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>
const asRole = (role: string) => { mockRole = { role, is_super_admin: role === 'super', owning_org_id: 11 } }
afterEach(() => { mockRole = DEFAULT_ROLE })

const FUNDING = {
  rows: [
    {
      application_id: 1, name: 'RASEKA A/P MURUGESE', ref: 'B40-0119', status: 'active',
      award_amount: '3000', paid_to_date: '1000', remaining: '2000', vircle_id: '1234567890123',
      last_run: { reference: 'PR-2026-07-26-01', payment_date: '2026-07-26' },
      programme: 'B40', wallet_not_live: false,
    },
    {
      application_id: 2, name: 'NEVER PAID', ref: 'B40-0200', status: 'active',
      award_amount: '3000', paid_to_date: '0', remaining: '3000', vircle_id: '',
      last_run: null, programme: 'B40', wallet_not_live: false,
    },
  ],
  totals: { students: 2, award_total: '6000', paid_total: '1000', remaining_total: '5000',
            wallet_not_live: 0 },
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

/**
 * ── You enter a gift first; inside it the question never arises (owner, 2026-09-28) ──
 *
 * ⚠ THE DEFECT, AS IT HAPPENED: an `admin` at BrightPath (two live gifts) opened Payments, pressed
 * New payment run, and got "Your organisation runs more than one gift, so please say which this
 * run pays from" — with nowhere in the dialog to say it. The page drew every gift's runs and a
 * button the server could only refuse.
 *
 * Now: reached with no gift known, a role that HAS a door to the gifts (super, org_admin) is SENT
 * to the Programmes page — *"the user should be redirected to the Programmes page, which lists the
 * gifts"* — and a role that has none there (admin, finance: the gift cards are not theirs) is asked
 * with the house `ChooseProgramme` box. Either way no list and no New-run button, ever.
 */
describe('several gifts and none chosen', () => {
  const inScope = (choices = TWO_GIFTS, settled = true) => render(
    <GiftScope choices={choices} settled={settled}><PaymentsLandingPage /></GiftScope>)

  const noMoneyOnScreen = () => {
    expect(screen.queryByText(/admin.payments.newRun/)).toBeNull()
    expect(screen.queryByTestId('run-cards')).toBeNull()
    expect(screen.queryByText('admin.payments.funding.title')).toBeNull()
    // …and the server is not even ASKED for every gift's runs behind the screen.
    expect(mockApi.getPaymentRuns).not.toHaveBeenCalled()
    expect(mockApi.getFundingSummary).not.toHaveBeenCalled()
  }

  it('⚠ an org_admin is REDIRECTED to the Programmes page — once, with replace', async () => {
    asRole('org_admin')
    inScope()
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith('/admin/organisation'))
    expect(mockReplace).toHaveBeenCalledTimes(1)
    expect(mockPush).not.toHaveBeenCalled()
    // The instant before it lands: the loading line and nothing else — no box either.
    expect(screen.getByTestId('gift-wait')).toBeTruthy()
    expect(screen.queryByTestId('choose-programme')).toBeNull()
    noMoneyOnScreen()
  })

  it('a super is redirected the same way', async () => {
    asRole('super')
    inScope()
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith('/admin/organisation'))
    noMoneyOnScreen()
  })

  it('⚠ an ADMIN (no gift cards on the Programmes page) is ASKED here, never sent there', async () => {
    // The defect's own role. `maySeeGifts` on the Programmes page is super + org_admin, so a
    // redirect would land Kulaly on a page with no gift to click.
    asRole('admin')
    inScope()
    expect(await screen.findByTestId('choose-programme')).toBeTruthy()
    expect(mockReplace).not.toHaveBeenCalled()
    noMoneyOnScreen()
  })

  it('finance is asked here too, for the same reason', async () => {
    asRole('finance')
    inScope()
    expect(await screen.findByTestId('choose-programme')).toBeTruthy()
    expect(mockReplace).not.toHaveBeenCalled()
  })

  it('answering the box loads THAT gift’s runs, and the crumb says so', async () => {
    asRole('admin')
    inScope()
    fireEvent.click(await screen.findByRole('button', { name: 'Sabah Bursary 2026' }))
    await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(
      'bpb-sabah-2026', { token: 'tok' }))
    expect(mockApi.getFundingSummary).toHaveBeenCalledWith('bpb-sabah-2026', { token: 'tok' })
    expect(screen.queryByTestId('choose-programme')).toBeNull()
    expect(await screen.findByText(/admin.payments.newRun/)).toBeTruthy()
    expect(crumbText()).toContain('Sabah Bursary 2026')
  })

  it('⚠ the list NOT YET LOADED is not "no gift": no redirect, and nothing drawn', async () => {
    // An empty list reads as "one gift" before it arrives. Acting on it would bounce every page
    // load — or flash every gift's money for the length of the fetch.
    asRole('org_admin')
    inScope(TWO_GIFTS, false)
    expect(screen.getByTestId('gift-wait')).toBeTruthy()
    await new Promise((r) => setTimeout(r, 20))
    expect(mockReplace).not.toHaveBeenCalled()
    noMoneyOnScreen()
  })

  it('with ONE gift there is nothing to ask — no redirect, the page exactly as before', async () => {
    asRole('org_admin')
    inScope([TWO_GIFTS[0]])
    await screen.findByText('26/07/2026')
    expect(mockReplace).not.toHaveBeenCalled()
    expect(screen.queryByTestId('choose-programme')).toBeNull()
    expect(mockApi.getPaymentRuns).toHaveBeenCalledWith('brightpath-flagship', { token: 'tok' })
  })

  it('⚠ CANNOT LOOP: opening a gift from the Programmes page and landing here does NOT redirect',
    async () => {
      // The real door: `GiftProgrammes`' card calls `select(code)` and navigates. Then the person
      // clicks Payments in the rail. If that bounced back, the console would loop.
      asRole('org_admin')
      mockApi.getAdminProgrammes.mockResolvedValue({ programmes: [
        { id: 1, code: 'brightpath-flagship', name_en: 'BrightPath Bursary', is_active: true },
        { id: 2, code: 'bpb-sabah-2026', name_en: 'Sabah Bursary 2026', is_active: true },
      ] } as unknown as Awaited<ReturnType<typeof api.getAdminProgrammes>>)
      const { rerender } = render(<GiftScope><GiftProgrammes token="tok" /></GiftScope>)
      fireEvent.click(await screen.findByTestId('open-bpb-sabah-2026'))
      // TD-296: the card's push carries the gift in the URL too; the loop assertion is unchanged.
      expect(mockPush).toHaveBeenCalledWith('/admin/programme/overview?programme=bpb-sabah-2026')
      rerender(<GiftScope><PaymentsLandingPage /></GiftScope>)
      await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(
        'bpb-sabah-2026', { token: 'tok' }))
      expect(mockReplace).not.toHaveBeenCalled()
    })
})

/**
 * ── F1 (adversarial review, 2026-09-28): a DRAFT is not a second gift ── The reviewer's exact
 * case: one live gift and one draft. The server auto-picks the one live gift; the first cut
 * counted the draft, hid Payments and bounced org_admins to the Programmes page.
 */
describe('one live gift and one draft', () => {
  const LIVE_AND_DRAFT = [TWO_GIFTS[0], { ...TWO_GIFTS[1], isActive: false }]

  it('is ONE gift: no redirect, no box, the live gift’s runs, and the dialog names it', async () => {
    asRole('org_admin')
    render(<GiftScope choices={LIVE_AND_DRAFT}><PaymentsLandingPage /></GiftScope>)
    await screen.findByText('26/07/2026')
    expect(mockReplace).not.toHaveBeenCalled()
    expect(screen.queryByTestId('choose-programme')).toBeNull()
    expect(mockApi.getPaymentRuns).toHaveBeenCalledWith('brightpath-flagship', { token: 'tok' })
    fireEvent.click(screen.getByText(/admin.payments.newRun/))
    expect(screen.getByTestId('pays-from').textContent)
      .toBe('admin.payments.paysFrom:Flagship Bursary')
  })

  it('two LIVE gifts and a draft: the question offers only the LIVE two', async () => {
    asRole('admin')
    render(<GiftScope choices={[...TWO_GIFTS, { code: 'draft-gift', name: 'Draft Gift', isActive: false }]}>
      <PaymentsLandingPage /></GiftScope>)
    const box = await screen.findByTestId('choose-programme')
    expect(Array.from(box.querySelectorAll('button')).map((b) => b.textContent))
      .toEqual(['Flagship Bursary', 'Sabah Bursary 2026'])
  })
})

/** THE PAIR, the page's half: redirected IFF `hasGiftDoor` — the predicate the rail hides on. */
describe('who is redirected and who is asked', () => {
  it('each role allowed here is redirected exactly when it has a door to the gifts', async () => {
    for (const role of ['super', 'org_admin', 'admin', 'finance'] as const) {
      mockReplace.mockClear()
      asRole(role)
      const view = render(<GiftScope><PaymentsLandingPage /></GiftScope>)
      if (hasGiftDoor(role)) {
        await waitFor(() => expect(mockReplace).toHaveBeenCalledWith('/admin/organisation'))
      } else {
        expect(await screen.findByTestId('choose-programme')).toBeTruthy()
        expect(mockReplace).not.toHaveBeenCalled()
      }
      view.unmount()
    }
  })

  it('finance can USE the box: choosing a gift loads its runs', async () => {
    asRole('finance')
    render(<GiftScope><PaymentsLandingPage /></GiftScope>)
    fireEvent.click(await screen.findByRole('button', { name: 'Flagship Bursary' }))
    await waitFor(() => expect(mockApi.getPaymentRuns).toHaveBeenCalledWith(
      'brightpath-flagship', { token: 'tok' }))
    expect(screen.queryByTestId('choose-programme')).toBeNull()
  })
})

describe('the New-run dialog names the fund', () => {
  it('says which gift the run pays from — read-only, one line', async () => {
    render(<GiftScope choices={[TWO_GIFTS[1]]}><PaymentsLandingPage /></GiftScope>)
    await screen.findByText('26/07/2026')
    fireEvent.click(screen.getByText(/admin.payments.newRun/))
    const line = screen.getByTestId('pays-from')
    expect(line.textContent).toBe('admin.payments.paysFrom:Sabah Bursary 2026')
    // It is a sentence, not a control: nothing in the dialog lets you pick a gift.
    expect(line.tagName).toBe('P')
    expect(screen.queryByRole('combobox')).toBeNull()
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

/**
 * TD-244 (2026-10-03): a REPORT, never an email. Funded students holding a wallet id that Vircle
 * has not reported switched on are NAMED above the funding table; nothing is drawn when there are
 * none (0 in production at the time of writing).
 */
describe('the wallet-not-live line', () => {
  it('names each student whose wallet is held but not switched on, with the count', async () => {
    const rows = [
      { ...FUNDING.rows[0], wallet_not_live: true },
      FUNDING.rows[1],
      { ...FUNDING.rows[0], application_id: 3, name: 'SECOND STUDENT', wallet_not_live: true },
    ]
    mockApi.getFundingSummary.mockResolvedValue(
      { rows, totals: { ...FUNDING.totals, students: 3, wallet_not_live: 2 } } as api.FundingSummary)
    render(<PaymentsLandingPage />)
    const line = await screen.findByRole('status')
    expect(line.textContent).toBe(
      'admin.payments.funding.walletNotLive:2:RASEKA A/P MURUGESE, SECOND STUDENT')
  })

  it('draws nothing when every held wallet is live', async () => {
    render(<PaymentsLandingPage />)
    await screen.findByText('26/07/2026')
    expect(screen.queryByText(/admin.payments.funding.walletNotLive/)).toBeNull()
  })
})
