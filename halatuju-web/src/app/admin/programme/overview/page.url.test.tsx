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
import { render, waitFor } from '@testing-library/react'

import ProgrammeOverviewPage from './page'
import * as api from '@/lib/admin-api'
import { GiftScope, TWO_GIFTS } from '@/test/giftScope'
import { address, openAt, switchCrumbTo, urlRouter } from '@/test/giftUrl'

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
