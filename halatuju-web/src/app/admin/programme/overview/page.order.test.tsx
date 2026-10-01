/**
 * @jest-environment jsdom
 *
 * Programme Overview — a reply for the gift you LEFT never lands (TD-301, 2026-10-01).
 *
 * `load` used to set `data` from whichever reply arrived last. Switching gift starts a new read
 * without cancelling the old, so a slow reply for the previous gift could (a) put its figures under
 * a crumb naming the new gift, and (b) through the 404 branch ("that round is not this gift's —
 * drop it"), clear the round the person had just chosen on the NEW gift. Each read now takes a
 * ticket (the TD-298 shape Payments and Spending use) and a stale reply is dropped whole.
 *
 * `t` echoes its key, plus the `name` it was given, so the heading says WHICH gift it describes.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

import ProgrammeOverviewPage from './page'
import * as api from '@/lib/admin-api'
import { GiftScope, TWO_GIFTS, crumbText } from '@/test/giftScope'
import { openAt, switchCrumbTo } from '@/test/giftUrl'

jest.mock('@/lib/i18n', () => ({ useT: () => ({
  t: (k: string, p?: Record<string, string>) => (p?.name ? `${k}:${p.name}` : k),
  locale: 'en',
}) }))
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin' } }),
}))
jest.mock('next/navigation', () => jest.requireActual('@/test/giftUrl').navigationMock)
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>
const SABAH = 'bpb-sabah-2026'
const FLAGSHIP = 'brightpath-flagship'
const TITLE = 'admin.programmeOverview.titleFor'

type Overview = api.ProgrammeOverview
const intake = (id: number, name: string) =>
  ({ id, code: `r-${id}`, name, year: 2026, state: 'open' }) as api.OverviewIntake
const SABAH_ROUNDS = [intake(7, 'Sabah 2026'), intake(8, 'Sabah 2027')]
const FLAGSHIP_ROUNDS = [intake(9, 'Flagship 2026'), intake(10, 'Flagship 2027')]
const overview = (name: string, intakes: api.OverviewIntake[] = []) =>
  ({ programme: { name }, sections: [], intakes }) as unknown as Overview

function later<T>() {
  let resolve!: (v: T) => void
  let reject!: (e: unknown) => void
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

const page = () => <GiftScope choices={TWO_GIFTS}><ProgrammeOverviewPage /></GiftScope>
const title = () => screen.getByRole('heading', { level: 1 }).textContent
const picker = () => screen.getByTestId('intake-picker') as HTMLSelectElement

beforeEach(() => { jest.clearAllMocks() })

it('the figures: the slow reply for the gift you left does not overwrite the new gift', async () => {
  const sabah = later<Overview>()
  mockApi.getProgrammeOverview.mockImplementation(({ programme } = {}) =>
    (programme === SABAH ? sabah.promise : Promise.resolve(overview('Flagship Bursary'))))
  openAt(`/admin/programme/overview?programme=${SABAH}`)
  render(page())
  await waitFor(() => expect(mockApi.getProgrammeOverview).toHaveBeenCalledTimes(1))
  switchCrumbTo('Flagship Bursary')
  await waitFor(() => expect(title()).toBe(`${TITLE}:Flagship Bursary`))
  // The reply for the gift we left lands LAST. Inside `act`, so any update it makes is flushed.
  await act(async () => { sabah.resolve(overview('Sabah Bursary 2026')) })
  expect(title()).toBe(`${TITLE}:Flagship Bursary`)
  expect(crumbText()).toContain('Flagship Bursary')
})

it('the round: a stale 404 for the left gift\'s round does not clear the new gift\'s round', async () => {
  const sabahRound = later<Overview>()
  mockApi.getProgrammeOverview.mockImplementation(({ programme, intake: round } = {}) => {
    if (programme === SABAH && round === 7) return sabahRound.promise
    return Promise.resolve(programme === SABAH
      ? overview('Sabah Bursary 2026', SABAH_ROUNDS) : overview('Flagship Bursary', FLAGSHIP_ROUNDS))
  })
  openAt(`/admin/programme/overview?programme=${SABAH}`)
  render(page())
  await waitFor(() => expect(picker().options.length).toBeGreaterThan(1))
  fireEvent.change(picker(), { target: { value: '7' } })          // Sabah's round — slow
  await waitFor(() => expect(mockApi.getProgrammeOverview)
    .toHaveBeenLastCalledWith({ programme: SABAH, intake: 7 }, { token: 'tok' }))
  switchCrumbTo('Flagship Bursary')
  await waitFor(() => expect(title()).toBe(`${TITLE}:Flagship Bursary`))
  fireEvent.change(picker(), { target: { value: '9' } })          // the NEW gift's round
  await waitFor(() => expect(mockApi.getProgrammeOverview)
    .toHaveBeenLastCalledWith({ programme: FLAGSHIP, intake: 9 }, { token: 'tok' }))
  const reads = mockApi.getProgrammeOverview.mock.calls.length
  // Sabah's round answers 404 — about SABAH's round, long after we left.
  await act(async () => { sabahRound.reject(Object.assign(new Error('nf'), { status: 404 })) })
  expect(picker().value).toBe('9')
  expect(mockApi.getProgrammeOverview.mock.calls.length).toBe(reads)   // nothing re-read
  expect(screen.queryByRole('alert')).toBeNull()
})

it('the control: a 404 for the CURRENT gift\'s round still drops it and reads again', async () => {
  mockApi.getProgrammeOverview.mockImplementation(({ intake: round } = {}) => (round === 7
    ? Promise.reject(Object.assign(new Error('nf'), { status: 404 }))
    : Promise.resolve(overview('Sabah Bursary 2026', SABAH_ROUNDS))))
  openAt(`/admin/programme/overview?programme=${SABAH}`)
  render(page())
  await waitFor(() => expect(picker().options.length).toBeGreaterThan(1))
  fireEvent.change(picker(), { target: { value: '7' } })
  await waitFor(() => expect(mockApi.getProgrammeOverview)
    .toHaveBeenLastCalledWith({ programme: SABAH, intake: undefined }, { token: 'tok' }))
  expect(picker().value).toBe('')
})
