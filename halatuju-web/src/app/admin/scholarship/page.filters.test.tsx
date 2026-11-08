/**
 * @jest-environment jsdom
 *
 * Applications — the Overview cards' links (owner 2026-11-05): ?status=&assigned=&ready=1&band= (and, A1.13b,
 * &withdrawal=pending) are read once on mount into the list request; ready / band / withdrawal show as a removable
 * chip; hand changes drop or update the URL.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import AdminScholarshipList from './page'
import * as api from '@/lib/admin-api'
import { GiftScope, TWO_GIFTS } from '@/test/giftScope'
import { openAt } from '@/test/giftUrl'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'super' } }),
}))
jest.mock('next/navigation', () => jest.requireActual('@/test/giftUrl').navigationMock)
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>
const empty = {
  count: 0, total_count: 0, total_pages: 1, page: 1, page_size: 25, next: null, previous: null, applications: [],
} as unknown as api.AdminScholarshipListData

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getScholarshipApplications.mockResolvedValue(empty)
  mockApi.getAssignableAdmins.mockResolvedValue({ admins: [], past_assignees: [] })
  mockApi.getSourceNames.mockResolvedValue({ sources: [] })
})

const show = (url: string) => {
  openAt(url)
  return render(<GiftScope choices={TWO_GIFTS} settled><AdminScholarshipList /></GiftScope>)
}
const firstRequest = async () => {
  await waitFor(() => expect(mockApi.getScholarshipApplications).toHaveBeenCalled())
  return mockApi.getScholarshipApplications.mock.calls[0][0]
}

describe('the address bar feeds the list request', () => {
  it('unassigned card: status, assigned and ready, in the very first request', async () => {
    show('/admin/scholarship?status=profile_complete&assigned=none&ready=1')
    const f = await firstRequest()
    expect(f).toMatchObject({ status: 'profile_complete', assigned: 'none', ready: true })
    expect(f?.band).toBeUndefined()
    expect(screen.getByTestId('chip-ready').textContent).toContain('admin.scholarship.chip.ready')
  })

  it('my overdue card: assigned=me and band=overdue', async () => {
    show('/admin/scholarship?assigned=me&band=overdue')
    expect(await firstRequest()).toMatchObject({ assigned: 'me', band: 'overdue' })
    expect(screen.getByTestId('chip-band').textContent).toContain('admin.scholarship.chip.overdue')
  })

  it('my open card: assigned=me and band=open', async () => {
    show('/admin/scholarship?assigned=me&band=open')
    expect(await firstRequest()).toMatchObject({ assigned: 'me', band: 'open' })
    expect(screen.getByTestId('chip-band').textContent).toContain('admin.scholarship.chip.open')
  })

  it('due soon chip text; unknown values are ignored', async () => {
    show('/admin/scholarship?band=due_soon&status=bogus&assigned=x;drop')
    const f = await firstRequest()
    expect(f).toMatchObject({ band: 'due_soon' })
    expect(f?.status).toBeUndefined()
    expect(f?.assigned).toBeUndefined()
    expect(screen.getByTestId('chip-band').textContent).toContain('admin.scholarship.chip.dueSoon')
  })

  it('no query: no chip, no extra filters', async () => {
    show('/admin/scholarship')
    const f = await firstRequest()
    expect(f?.ready).toBeUndefined()
    expect(f?.band).toBeUndefined()
    expect(screen.queryByTestId('url-filter-chips')).toBeNull()
  })
})

describe('the withdrawal checker card (A1.13b): ?withdrawal=pending', () => {
  it('goes into the first request and shows a removable chip', async () => {
    show('/admin/scholarship?withdrawal=pending')
    expect(await firstRequest()).toMatchObject({ withdrawal: 'pending' })
    expect(screen.getByTestId('chip-withdrawal').textContent).toContain('admin.scholarship.chip.withdrawalPending')
  })

  it('any other value is ignored', async () => {
    show('/admin/scholarship?withdrawal=approved')
    expect((await firstRequest())?.withdrawal).toBeUndefined()
    expect(screen.queryByTestId('chip-withdrawal')).toBeNull()
  })

  it('removing the chip asks again without it and drops it from the address bar', async () => {
    show('/admin/scholarship?withdrawal=pending')
    await firstRequest()
    fireEvent.click(screen.getByLabelText('admin.scholarship.chip.remove'))
    await waitFor(() => expect(screen.queryByTestId('chip-withdrawal')).toBeNull())
    await waitFor(() => expect(mockApi.getScholarshipApplications.mock.calls.at(-1)?.[0]?.withdrawal).toBeUndefined())
    expect(window.location.search).toBe('')
  })
})

describe('clearing', () => {
  it('removing the chip asks again without it and drops it from the address bar', async () => {
    show('/admin/scholarship?band=overdue&ready=1')
    await firstRequest()
    fireEvent.click(screen.getAllByLabelText('admin.scholarship.chip.remove')[1])
    await waitFor(() => expect(screen.queryByTestId('chip-band')).toBeNull())
    await waitFor(() => expect(mockApi.getScholarshipApplications.mock.calls.at(-1)?.[0]?.band).toBeUndefined())
    expect(mockApi.getScholarshipApplications.mock.calls.at(-1)?.[0]?.ready).toBe(true)
    expect(window.location.search).toBe('?ready=1')
  })

  it('changing the status by hand updates the address bar', async () => {
    show('/admin/scholarship?status=interviewed')
    await firstRequest()
    fireEvent.change(screen.getByLabelText('admin.scholarship.allStatuses'), { target: { value: '' } })
    await waitFor(() => expect(window.location.search).toBe(''))
  })
})
