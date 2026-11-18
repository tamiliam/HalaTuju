/**
 * @jest-environment jsdom
 *
 * Request #73 review: the bell's new-note count is asked once on sign-in, then on a route change at most once a
 * minute, and again at once whenever the window regains focus, the tab becomes visible, or the notes card says a
 * case was just read (re-check M2). An older answer never overwrites a newer one (re-check L9). Focus and the
 * tab becoming visible together are one ask (re-check 2 L-E). No token, nothing asked.
 */
import { act, renderHook, waitFor } from '@testing-library/react'

import { NEW_NOTE_THROTTLE_MS, RETURN_COALESCE_MS, announceNotesRead, useNewNoteCount } from '../useNewNoteCount'
import * as adminApi from '@/lib/admin-api'

jest.mock('@/lib/admin-api', () => ({
  getNewNoteCount: jest.fn(() => Promise.resolve({ from_reviewer: 2, from_org_admin: 0 })),
}))

const counts = jest.mocked(adminApi.getNewNoteCount)
const START = new Date('2026-11-16T09:00:00Z').getTime()
let now = START

beforeEach(() => {
  counts.mockClear()
  now = START
  jest.spyOn(Date, 'now').mockImplementation(() => now)
})
afterEach(() => jest.restoreAllMocks())

function mount(token: string | null = 'tok') {
  return renderHook(({ path, tok }) => useNewNoteCount(tok, path),
    { initialProps: { path: '/admin/scholarship', tok: token as string | null } })
}

it('asks once, and serves the answer', async () => {
  const { result } = mount()
  await waitFor(() => expect(result.current.from_reviewer).toBe(2))
  expect(counts).toHaveBeenCalledTimes(1)
  expect(counts).toHaveBeenCalledWith({ token: 'tok' })
})

it('a route change inside the minute asks nothing; after the minute it asks again', async () => {
  const { rerender } = mount()
  await waitFor(() => expect(counts).toHaveBeenCalledTimes(1))
  now = START + 30_000
  rerender({ path: '/admin/scholarship/7', tok: 'tok' })
  rerender({ path: '/admin/scholarship', tok: 'tok' })
  expect(counts).toHaveBeenCalledTimes(1)
  now = START + NEW_NOTE_THROTTLE_MS + 1
  rerender({ path: '/admin/scholarship/8', tok: 'tok' })
  await waitFor(() => expect(counts).toHaveBeenCalledTimes(2))
})

it('focus asks again at once, inside the minute too', async () => {
  mount()
  await waitFor(() => expect(counts).toHaveBeenCalledTimes(1))
  now = START + 5_000
  act(() => { window.dispatchEvent(new Event('focus')) })
  await waitFor(() => expect(counts).toHaveBeenCalledTimes(2))
})

it('no token: nothing is asked, on a route change or on focus, and the count is zero', async () => {
  const { result, rerender } = mount(null)
  rerender({ path: '/admin/scholarship/7', tok: null })
  act(() => { window.dispatchEvent(new Event('focus')) })
  await Promise.resolve()
  expect(counts).not.toHaveBeenCalled()
  expect(result.current).toEqual({ from_reviewer: 0, from_org_admin: 0 })
})

it('reading a case drops the bell at once, without waiting out the minute (re-check M2)', async () => {
  const { result } = mount()
  await waitFor(() => expect(result.current.from_reviewer).toBe(2))
  counts.mockResolvedValueOnce({ from_reviewer: 0, from_org_admin: 0 })
  now = START + 5_000
  act(() => { announceNotesRead() })
  await waitFor(() => expect(result.current.from_reviewer).toBe(0))
  expect(counts).toHaveBeenCalledTimes(2)
})

it('the tab becoming visible asks again; becoming hidden does not (re-check L9)', async () => {
  mount()
  await waitFor(() => expect(counts).toHaveBeenCalledTimes(1))
  const state = jest.spyOn(document, 'visibilityState', 'get')
  state.mockReturnValue('hidden')
  act(() => { document.dispatchEvent(new Event('visibilitychange')) })
  await Promise.resolve()
  expect(counts).toHaveBeenCalledTimes(1)
  state.mockReturnValue('visible')
  act(() => { document.dispatchEvent(new Event('visibilitychange')) })
  await waitFor(() => expect(counts).toHaveBeenCalledTimes(2))
})

it('an older answer arriving last never overwrites a newer one (re-check L9)', async () => {
  const answers: Array<(v: { from_reviewer: number; from_org_admin: number }) => void> = []
  counts.mockImplementation(() => new Promise((r) => { answers.push(r) }))
  const { result } = mount()
  await waitFor(() => expect(answers).toHaveLength(1))
  act(() => { window.dispatchEvent(new Event('focus')) })
  await waitFor(() => expect(answers).toHaveLength(2))
  await act(async () => { answers[1]({ from_reviewer: 0, from_org_admin: 1 }) })
  await act(async () => { answers[0]({ from_reviewer: 5, from_org_admin: 0 }) })
  expect(result.current).toEqual({ from_reviewer: 0, from_org_admin: 1 })
})

it('focus and the tab becoming visible together are one ask; a later return asks again (re-check 2 L-E)', async () => {
  mount()
  await waitFor(() => expect(counts).toHaveBeenCalledTimes(1))
  jest.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
  now = START + 5_000
  act(() => {
    document.dispatchEvent(new Event('visibilitychange'))
    window.dispatchEvent(new Event('focus'))
  })
  await waitFor(() => expect(counts).toHaveBeenCalledTimes(2))
  now = START + 5_000 + RETURN_COALESCE_MS - 1
  act(() => { window.dispatchEvent(new Event('focus')) })
  await Promise.resolve()
  expect(counts).toHaveBeenCalledTimes(2)
  now = START + 5_000 + RETURN_COALESCE_MS + 1
  act(() => { window.dispatchEvent(new Event('focus')) })
  await waitFor(() => expect(counts).toHaveBeenCalledTimes(3))
})
