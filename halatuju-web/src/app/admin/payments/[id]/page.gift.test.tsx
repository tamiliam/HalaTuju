/**
 * @jest-environment jsdom
 *
 * A payment run tells the breadcrumb which gift it belongs to (2026-09-28).
 *
 * ⚠ THE DEFECT: the run page read the gift zero times. Switch the crumb on a run page and the
 * crumb changed while the run did not — the crumb lied. And a fresh tab, a bookmark or a refresh
 * started with no choice at all, so the crumb asked "which gift?" above a run that could only
 * ever belong to one.
 *
 * What is pinned: a FRESH mount with no prior choice names the run's own gift, with no switch;
 * the name comes from the SERVER payload and nothing stored; the pin outranks a different earlier
 * choice; a gift the scope does not know shows the RECORD's own name (from the payload), selecting
 * nothing; and leaving the page releases the pin and gives back the person's previous choice
 * EXACTLY — "none" included. (The first cut selected the gift; the adversarial review showed that
 * narrowed the all-gifts Applications list with no way back, so (ii) was reversed the same day.)
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import PaymentRunPage from './page'
import * as api from '@/lib/admin-api'
import {
  GiftScope, crumbSwitch, crumbText, scopeChosen, scopePinned,
} from '@/test/giftScope'
import { useProgrammeScope } from '@/lib/programmeScope'
import { readWeb } from '@/test/sourceGuard'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'admin', owning_org_id: 11 } }),
}))
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn() }),
  useParams: () => ({ id: '3' }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const RUN = {
  id: 3, reference: 'PR-2026-10-01-01', payment_date: '2026-10-01', period_month: '2026-10-01',
  status: 'draft', note: '', drive_file_url: '', created_by: '', created_at: '',
  admin_signed: null, finance_signed: null, finance_check_required: false, org_admin_signed: null,
  items: [], skipped: [], students: 0, total: '0',
  programme: { id: 2, code: 'bpb-sabah-2026', name: 'Sabah Bursary 2026' },
} as unknown as api.PaymentRunDetail

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getPaymentRun.mockResolvedValue(RUN)
})

const loaded = () => screen.findByText('PR-2026-10-01-01', { selector: 'h1' })

describe('a fresh mount — a new tab, a bookmark, a refresh — with no prior choice', () => {
  it('names the RUN’s gift in the crumb, with no switch', async () => {
    render(<GiftScope><PaymentRunPage /></GiftScope>)
    // Before the run arrives nothing is pinned, and with two gifts the crumb honestly asks.
    expect(crumbText()).toContain('admin.shell.chooseProgramme')
    await loaded()
    await waitFor(() => expect(crumbText()).toContain('Sabah Bursary 2026'))
    expect(crumbText()).not.toContain('admin.shell.chooseProgramme')
    expect(crumbSwitch()).toBeNull()
    expect(scopePinned()).toBe('true')
    expect(scopeChosen()).toBe('bpb-sabah-2026')
  })

  it('takes the gift from the SERVER payload — a run with no gift pins nothing', async () => {
    mockApi.getPaymentRun.mockResolvedValue({ ...RUN, programme: null })
    render(<GiftScope><PaymentRunPage /></GiftScope>)
    await loaded()
    expect(scopePinned()).toBe('false')
    // Unpinned, two gifts, nothing chosen: the question — and the switch to answer it.
    expect(crumbText()).toContain('admin.shell.chooseProgramme')
    expect(crumbSwitch()).not.toBeNull()
  })
})

describe('the pin and an earlier choice', () => {
  function PickFlagship() {
    const { select } = useProgrammeScope()
    return <button type="button" onClick={() => select('brightpath-flagship')}>pick-flagship</button>
  }

  it('outranks a DIFFERENT gift chosen before — the crumb names the run’s', async () => {
    const { rerender } = render(<GiftScope><PickFlagship /></GiftScope>)
    fireEvent.click(screen.getByText('pick-flagship'))
    expect(scopeChosen()).toBe('brightpath-flagship')
    rerender(<GiftScope><PaymentRunPage /></GiftScope>)
    await loaded()
    await waitFor(() => expect(crumbText()).toContain('Sabah Bursary 2026'))
    expect(crumbText()).not.toContain('Flagship Bursary')
  })
})

describe('leaving the run', () => {
  it('releases the pin on unmount and gives back "no choice" — the pin never selects', async () => {
    const { rerender } = render(<GiftScope><PaymentRunPage /></GiftScope>)
    await loaded()
    await waitFor(() => expect(scopePinned()).toBe('true'))
    // Navigate away: the page unmounts, the shell (and its scope) stays.
    rerender(<GiftScope>{null}</GiftScope>)
    expect(scopePinned()).toBe('false')
    // Nobody chose a gift, so nobody has one: the list page meets its own gate, honestly.
    expect(scopeChosen()).toBe('(none)')
    expect(crumbText()).toContain('admin.shell.chooseProgramme')
    expect(crumbSwitch()).not.toBeNull()
  })

  it('gives back an EARLIER choice exactly, even a different gift from the run’s', async () => {
    function PickFlagship() {
      const { select } = useProgrammeScope()
      return <button type="button" onClick={() => select('brightpath-flagship')}>pick-flagship</button>
    }
    const { rerender } = render(<GiftScope><PickFlagship /></GiftScope>)
    fireEvent.click(screen.getByText('pick-flagship'))
    rerender(<GiftScope><PaymentRunPage /></GiftScope>)
    await loaded()
    await waitFor(() => expect(scopeChosen()).toBe('bpb-sabah-2026'))   // pinned while mounted
    rerender(<GiftScope>{null}</GiftScope>)
    expect(scopeChosen()).toBe('brightpath-flagship')
  })
})

describe('a gift the scope does not know', () => {
  // F4 (adversarial review): the crumb used to ASK here, with no switch — a question with no
  // answer. The payload carries the gift's NAME from the server; that is a fact, not a guess.
  it('names the RECORD’s own gift, from the payload — no switch, and selects nothing', async () => {
    mockApi.getPaymentRun.mockResolvedValue({
      ...RUN, programme: { id: 9, code: 'some-other-gift', name: 'Some Other Gift' },
    })
    render(<GiftScope><PaymentRunPage /></GiftScope>)
    await loaded()
    await waitFor(() => expect(scopePinned()).toBe('true'))
    expect(crumbText()).toContain('Some Other Gift')
    expect(crumbText()).not.toContain('admin.shell.chooseProgramme')
    expect(crumbText()).not.toContain('Flagship Bursary')
    expect(crumbText()).not.toContain('Sabah Bursary 2026')
    expect(crumbSwitch()).toBeNull()
    expect(scopeChosen()).toBe('(none)')
  })

  it('names it even when the list is EMPTY (the scopes fetch failed)', async () => {
    render(<GiftScope choices={[]}><PaymentRunPage /></GiftScope>)
    await loaded()
    await waitFor(() => expect(crumbText()).toContain('Sabah Bursary 2026'))
    expect(crumbSwitch()).toBeNull()
  })

  // Found by a SILENT bite (2026-09-28): letting an unknown pin fall through to the person's
  // earlier pick passed the test above, because that test had no earlier pick. With one, the fault
  // would name the WRONG gift over this run — the exact lie this sprint exists to remove.
  it('⚠ does not fall back to an EARLIER pick', async () => {
    mockApi.getPaymentRun.mockResolvedValue({
      ...RUN, programme: { id: 9, code: 'some-other-gift', name: 'Some Other Gift' },
    })
    function PickFlagship() {
      const { select } = useProgrammeScope()
      return <button type="button" onClick={() => select('brightpath-flagship')}>pick-flagship</button>
    }
    const { rerender } = render(<GiftScope><PickFlagship /></GiftScope>)
    fireEvent.click(screen.getByText('pick-flagship'))
    rerender(<GiftScope><PaymentRunPage /></GiftScope>)
    await loaded()
    await waitFor(() => expect(scopePinned()).toBe('true'))
    expect(crumbText()).toContain('Some Other Gift')
    expect(crumbText()).not.toContain('Flagship Bursary')
    expect(scopeChosen()).toBe('(none)')
  })
})

describe('the way back to the list', () => {
  it('is a client-side link, so the gift you were in survives the trip', async () => {
    render(<GiftScope><PaymentRunPage /></GiftScope>)
    await loaded()
    const back = screen.getByRole('link', { name: 'admin.payments.title' })
    // TD-296: the way back names THIS RUN's gift, so the list opens in it — from a bookmark or a
    // new tab too, where no earlier choice exists. (Was the bare path before the URL carried it.)
    expect(back.getAttribute('href')).toBe('/admin/payments?programme=bpb-sabah-2026')
    // `next/link` renders an <a> too; what distinguishes it is that it is not a bare anchor in
    // the SOURCE — asserted structurally below, because jsdom does not navigate either way.
    const src = readWeb('src/app/admin/payments/[id]/page.tsx',
      'the run page\'s way back to the list must be next/link: a bare <a> reloads the app and '
      + 'throws away the gift the person was in (2026-09-28)')
    expect(src).not.toMatch(/<a href="\/admin\/payments"/)
    expect(src).not.toMatch(/<a href=\{run\.programme/)
    expect(src).toMatch(/<Link href=\{run\.programme \? `\/admin\/payments\?programme=/)
  })

  it('a run with no gift goes back to the bare list — a link never claims a gift', async () => {
    mockApi.getPaymentRun.mockResolvedValue({ ...RUN, programme: null })
    render(<GiftScope><PaymentRunPage /></GiftScope>)
    await loaded()
    expect(screen.getByRole('link', { name: 'admin.payments.title' }).getAttribute('href'))
      .toBe('/admin/payments')
  })
})
