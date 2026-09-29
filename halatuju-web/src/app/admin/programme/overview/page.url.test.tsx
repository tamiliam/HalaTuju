/**
 * @jest-environment jsdom
 *
 * Programme Overview — the URL carries the gift (TD-296, 2026-09-28).
 *
 * The Overview is where a gift card lands, so it is the first page a shared gift link will name.
 * It READS, and with no gift known it describes everything the fence allows under a neutral
 * heading; these pin that a recognised `?programme=` narrows it (and nothing is read before the
 * link's gift applies), an unknown one narrows nothing, and a switch rewrites the address bar in
 * place.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import ProgrammeOverviewPage from './page'
import * as api from '@/lib/admin-api'
import { GiftScope, TWO_GIFTS } from '@/test/giftScope'
import {
  address, crumbOffersAll, openAt, switchCrumbTo, switchCrumbToAll, urlRouter,
} from '@/test/giftUrl'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k, locale: 'en' }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin' } }),
}))
jest.mock('next/navigation', () => jest.requireActual('@/test/giftUrl').navigationMock)
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>
const SABAH = 'bpb-sabah-2026'
const giftsAskedFor = () => mockApi.getProgrammeOverview.mock.calls.map((c) => c[0]?.programme)

beforeEach(() => {
  jest.clearAllMocks()
  openAt('/admin/programme/overview')
  mockApi.getProgrammeOverview.mockResolvedValue(
    { sections: [], intakes: [] } as unknown as api.ProgrammeOverview)
})

const page = (choices = TWO_GIFTS, settled = true) =>
  <GiftScope choices={choices} settled={settled}><ProgrammeOverviewPage /></GiftScope>

it('a recognised gift narrows it — and nothing is read before the link’s gift applies', async () => {
  openAt(`/admin/programme/overview?programme=${SABAH}`)
  const view = render(page([], false))   // a real fresh load: the list is empty until it answers
  await new Promise((r) => setTimeout(r, 20))
  expect(mockApi.getProgrammeOverview).not.toHaveBeenCalled()
  view.rerender(page(TWO_GIFTS, true))
  await waitFor(() => expect(giftsAskedFor()).toEqual([SABAH]))
  expect(urlRouter.replace).not.toHaveBeenCalled()
})

it('an unknown gift narrows nothing', async () => {
  openAt('/admin/programme/overview?programme=not-a-gift')
  render(page())
  await waitFor(() => expect(mockApi.getProgrammeOverview).toHaveBeenCalled())
  expect(giftsAskedFor()).toEqual([undefined])
})

describe('TD-302 — "All gifts" on the Overview', () => {
  // TWO rounds, on purpose: since 2026-09-29 the Overview draws the round picker only when a gift
  // has two or more rounds ("All intakes" and a lone round describe the same cases), so a fixture
  // with one round has no picker to drive. That fix landed from the other machine while this
  // sprint was in review, and the rebase is where the two met.
  const INTAKES: api.OverviewIntake[] = [
    { id: 7, code: 'sabah-2026', name: 'Sabah 2026', year: 2026, state: 'open' },
    { id: 8, code: 'sabah-2027', name: 'Sabah 2027', year: 2027, state: 'draft' },
  ]

  it('clears the gift and its round, drops the query in place, and reads every gift', async () => {
    mockApi.getProgrammeOverview.mockResolvedValue(
      { sections: [], intakes: INTAKES } as unknown as api.ProgrammeOverview)
    openAt(`/admin/programme/overview?programme=${SABAH}`)
    render(page())
    await waitFor(() => expect(giftsAskedFor()).toEqual([SABAH]))
    fireEvent.change(await screen.findByTestId('intake-picker'), { target: { value: '7' } })
    await waitFor(() => expect(mockApi.getProgrammeOverview)
      .toHaveBeenLastCalledWith({ programme: SABAH, intake: 7 }, { token: 'tok' }))
    const before = window.history.length
    switchCrumbToAll()
    // The round belonged to Sabah, so it goes with it: the read is every gift, every round.
    await waitFor(() => expect(mockApi.getProgrammeOverview)
      .toHaveBeenLastCalledWith({ programme: undefined, intake: undefined }, { token: 'tok' }))
    expect(address()).toBe('/admin/programme/overview')
    expect((screen.getByTestId('intake-picker') as HTMLSelectElement).value).toBe('')
    expect(urlRouter.push).not.toHaveBeenCalled()
    expect(window.history.length).toBe(before)
  })

  it('with nothing chosen it is absent', async () => {
    render(page())
    await waitFor(() => expect(mockApi.getProgrammeOverview).toHaveBeenCalled())
    expect(crumbOffersAll()).toBe(false)
  })
})

it('a switch rewrites the address bar in place', async () => {
  openAt(`/admin/programme/overview?programme=${SABAH}`)
  render(page())
  await waitFor(() => expect(giftsAskedFor()).toEqual([SABAH]))
  const before = window.history.length
  switchCrumbTo('Flagship Bursary')
  await waitFor(() => expect(address()).toBe('/admin/programme/overview?programme=brightpath-flagship'))
  expect(urlRouter.push).not.toHaveBeenCalled()
  expect(window.history.length).toBe(before)
})
