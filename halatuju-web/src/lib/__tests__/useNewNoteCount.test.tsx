/**
 * @jest-environment jsdom
 *
 * Request #73 review: the bell's new-note count is asked once on sign-in, then on a route change at most once a
 * minute, and again whenever the window regains focus. No token, nothing asked.
 */
import { act, renderHook, waitFor } from '@testing-library/react'

import { NEW_NOTE_THROTTLE_MS, useNewNoteCount } from '../useNewNoteCount'
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
