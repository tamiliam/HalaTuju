/**
 * @jest-environment jsdom
 *
 * Applications — the URL carries the gift (TD-296) and the newest reply wins (TD-298), 2026-09-28.
 *
 * ⚠ THIS IS THE ALL-GIFTS LIST BY DESIGN — a reviewer's only door. With NO query (and no earlier
 * choice) it must still list every gift; a recognised query narrows it, as the crumb does. A code
 * the list does not know narrows NOTHING and names nothing: the neutral heading and every gift the
 * fence allows, which is the honest answer for a read — never the only gift, never a guess.
 */
import { act, render, screen, waitFor } from '@testing-library/react'

import AdminScholarshipList from './page'
import * as api from '@/lib/admin-api'
import { GiftScope, TWO_GIFTS, scopeChosen } from '@/test/giftScope'
import { address, deferred, openAt, switchCrumbTo, urlRouter } from '@/test/giftUrl'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, vars?: Record<string, string>) =>
    (vars ? `${k}|${Object.values(vars).join(',')}` : k) }),
}))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'reviewer' } }),
}))
jest.mock('next/navigation', () => jest.requireActual('@/test/giftUrl').navigationMock)
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>
const FLAGSHIP = 'brightpath-flagship'
const SABAH = 'bpb-sabah-2026'

const list = (...names: string[]) => ({
  count: names.length, total_count: names.length, total_pages: 1, page: 1, page_size: 25,
  next: null, previous: null,
  applications: names.map((name, i) => ({
    id: i + 1, name, status: 'submitted', bucket: 'A', qualification: 'spm', merit_score: 1,
    referral_source: '', submitted_at: null, assigned_to_id: null, call_language: '',
  })),
}) as unknown as api.AdminScholarshipListData

beforeEach(() => {
  jest.clearAllMocks()
  openAt('/admin/scholarship')
  mockApi.getScholarshipApplications.mockResolvedValue(list())
  mockApi.getAssignableAdmins.mockResolvedValue({ admins: [], past_assignees: [] })
})

const page = (choices = TWO_GIFTS, settled = true) =>
  <GiftScope choices={choices} settled={settled}><AdminScholarshipList /></GiftScope>
const giftsAskedFor = () => mockApi.getScholarshipApplications.mock.calls.map((c) => c[0]?.programme)
const heading = () => screen.getByRole('heading', { level: 1 }).textContent

describe('(i) no query, no earlier choice: every gift', () => {
  it('lists every gift under the neutral heading, and leaves the address bar alone', async () => {
    render(page())
    await waitFor(() => expect(mockApi.getScholarshipApplications).toHaveBeenCalled())
    expect(giftsAskedFor()).toEqual([undefined])
    expect(heading()).toBe('admin.scholarship.titleAll')
    expect(urlRouter.replace).not.toHaveBeenCalled()
    expect(address()).toBe('/admin/scholarship')
  })
})

describe('(a) a recognised query narrows the list to that gift', () => {
  it('asks for that gift only — never for every gift first, even on a cold load', async () => {
    openAt(`/admin/scholarship?programme=${SABAH}`)
    const view = render(page([], false))   // a real fresh load: the list is empty until it answers
    await new Promise((r) => setTimeout(r, 20))
    // A shared link must not flash every gift's applicants before its own gift applies.
    expect(mockApi.getScholarshipApplications).not.toHaveBeenCalled()
    view.rerender(page(TWO_GIFTS, true))
    await waitFor(() => expect(heading()).toBe('admin.scholarship.title|Sabah Bursary 2026'))
    expect(giftsAskedFor()).toEqual([SABAH])
    expect(urlRouter.replace).not.toHaveBeenCalled()
  })
})

describe('(b) an unrecognised query selects nothing', () => {
  it('the neutral all-gifts list, and no gift is chosen', async () => {
    openAt('/admin/scholarship?programme=not-a-gift')
    render(page())
    await waitFor(() => expect(mockApi.getScholarshipApplications).toHaveBeenCalled())
    expect(giftsAskedFor()).toEqual([undefined])
    expect(heading()).toBe('admin.scholarship.titleAll')
    expect(scopeChosen()).toBe('(none)')
  })

  it('⚠ on a single-gift tenant it still names nothing — not "the only one"', async () => {
    openAt('/admin/scholarship?programme=not-a-gift')
    render(page([TWO_GIFTS[0]]))
    await waitFor(() => expect(mockApi.getScholarshipApplications).toHaveBeenCalled())
    expect(scopeChosen()).toBe('(none)')
    expect(heading()).toBe('admin.scholarship.titleAll')
  })
})

describe('(e)(g) switching gift keeps the address bar in step, in place', () => {
  it('replace, never push; no history entry; the list re-reads', async () => {
    openAt(`/admin/scholarship?programme=${SABAH}`)
    render(page())
    await waitFor(() => expect(giftsAskedFor()).toEqual([SABAH]))
    const before = window.history.length
    switchCrumbTo('Flagship Bursary')
    await waitFor(() => expect(urlRouter.replace).toHaveBeenCalledWith(
      `/admin/scholarship?programme=${FLAGSHIP}`, { scroll: false }))
    expect(urlRouter.push).not.toHaveBeenCalled()
    expect(window.history.length).toBe(before)
    await waitFor(() => expect(giftsAskedFor()).toContain(FLAGSHIP))
  })

  it('choosing a gift on the all-gifts list writes it in, so the narrowed list is shareable', async () => {
    render(page())
    await waitFor(() => expect(mockApi.getScholarshipApplications).toHaveBeenCalled())
    switchCrumbTo('Sabah Bursary 2026')
    await waitFor(() => expect(address()).toBe(`/admin/scholarship?programme=${SABAH}`))
  })
})

describe('(j) TD-298 — a reply for the gift you LEFT never overwrites the new one', () => {
  it('replies resolved out of order: the list shows the gift the crumb names', async () => {
    const forSabah = deferred<api.AdminScholarshipListData>()
    const forFlagship = deferred<api.AdminScholarshipListData>()
    mockApi.getScholarshipApplications.mockImplementation(
      (f) => (f?.programme === SABAH ? forSabah.promise : forFlagship.promise))
    openAt(`/admin/scholarship?programme=${SABAH}`)
    render(page())
    await waitFor(() => expect(giftsAskedFor()).toEqual([SABAH]))
    switchCrumbTo('Flagship Bursary')
    await waitFor(() => expect(giftsAskedFor()).toContain(FLAGSHIP))
    forFlagship.resolve(list('FLAGSHIP STUDENT'))
    expect((await screen.findAllByText('FLAGSHIP STUDENT')).length).toBeGreaterThan(0)
    // Inside `act`, so any render the stale reply causes is flushed before we look.
    await act(async () => { forSabah.resolve(list('SABAH STUDENT')) })
    expect(screen.queryAllByText('SABAH STUDENT')).toHaveLength(0)
    expect(screen.getAllByText('FLAGSHIP STUDENT').length).toBeGreaterThan(0)
  })
})
