/**
 * @jest-environment jsdom
 *
 * The My activity card (common profile S5): its chips, its rows, Show older, the empty and error
 * states, and that an answer for a chip the reader has left never lands.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import en from '@/messages/en.json'
import * as api from '@/lib/admin-api'
import { interpolateMessage } from '@/lib/branding'
import type { ActivityItem, ActivityPage } from '@/lib/admin-api'
import ActivityCard from './ActivityCard'
import type { ProfileState } from './shared'

jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const t = (key: string, vars?: Record<string, string>) => {
  const v = key.split('.').reduce<unknown>((c, k) => (c && typeof c === 'object' ? (c as Record<string, unknown>)[k] : undefined), en)
  return typeof v === 'string' ? interpolateMessage(v, vars) : key
}
const state = (role: string, permissions: string[]) =>
  ({ t, token: 'tok', role, isSuper: false, permissions }) as unknown as ProfileState

const NOW = new Date().toISOString()
const LONG_AGO = new Date(Date.now() - 40 * 86400000).toISOString()
const item = (over: Partial<ActivityItem>): ActivityItem => ({
  id: 1, verb: 'verdict_recorded', kind: 'students', created_at: NOW, backfilled: false,
  subject: null, meta: {}, ...over,
})
const page = (results: ActivityItem[], next: string | null = null): ActivityPage => ({ results, next })

beforeEach(() => { jest.clearAllMocks() })

it('a reviewer: All / Students / Profile and sign-in, rows by day, links, our neutral words, rebuilt', async () => {
  mockApi.getMyActivity.mockResolvedValue(page([
    item({ id: 3, subject: { type: 'application', state: 'visible', label: 'Aisyah binti Ali', id: 104 } }),
    item({ id: 2, verb: 'query_raised', subject: { type: 'application', state: 'hidden', label: 'SERVER WORD', id: null } }),
    item({ id: 1, verb: 'case_closed', created_at: LONG_AGO, backfilled: true,
           subject: { type: 'application', state: 'removed', label: 'SERVER WORD', id: null } }),
  ]))
  render(<ActivityCard state={state('reviewer', ['review'])} />)
  const rows = await screen.findAllByTestId('activity-row')
  expect(screen.getAllByRole('button').filter((b) => b.hasAttribute('aria-pressed')).map((b) => b.textContent))
    .toEqual(['All', 'Students', 'Profile and sign-in'])
  expect(rows[0].textContent).toContain('Recorded a verdict for Aisyah binti Ali')
  expect(within(rows[0]).getByRole('link', { name: 'Aisyah binti Ali' }).getAttribute('href')).toBe('/admin/scholarship/104')
  expect(rows[1].textContent).toContain('Raised a query with a student')
  expect(within(rows[1]).queryByRole('link')).toBeNull()
  expect(rows[2].textContent).toContain('Closed the case of a student (removed)')
  expect(screen.queryByText(/SERVER WORD/)).toBeNull()
  expect(within(rows[2]).getByTestId('activity-rebuilt')).toBeTruthy()
  expect(within(rows[0]).queryByTestId('activity-rebuilt')).toBeNull()
  expect(screen.getByRole('region', { name: 'Today' })).toBeTruthy()
  expect(screen.getByRole('region', { name: 'Earlier' })).toBeTruthy()
  expect(screen.getByText(/Only you can see this list/)).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Show older' })).toBeNull()
  expect(mockApi.getMyActivity).toHaveBeenCalledWith('all', null, { token: 'tok' })
})

it('Show older asks for the next page with the cursor, appends it, and goes when there is no more', async () => {
  mockApi.getMyActivity
    .mockResolvedValueOnce(page([item({ id: 2, verb: 'first_sign_in' })], 'CUR1'))
    .mockResolvedValueOnce(page([item({ id: 1, verb: 'profile_updated', created_at: LONG_AGO })]))
  render(<ActivityCard state={state('admin', ['see_all', 'spending', 'payments_prepare'])} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Show older' }))
  await waitFor(() => expect(screen.getAllByTestId('activity-row')).toHaveLength(2))
  expect(mockApi.getMyActivity).toHaveBeenLastCalledWith('all', 'CUR1', { token: 'tok' })
  expect(screen.getByText('Updated your profile')).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Show older' })).toBeNull()
})

it('a chip asks the server for its kind; an empty list says so in plain words', async () => {
  mockApi.getMyActivity.mockResolvedValue(page([]))
  render(<ActivityCard state={state('finance', ['payments_approve'])} />)
  expect((await screen.findByTestId('activity-empty')).textContent).toContain('Nothing here yet.')
  expect(screen.queryByRole('button', { name: 'Students' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Money' }))
  await waitFor(() => expect(mockApi.getMyActivity).toHaveBeenLastCalledWith('money', null, { token: 'tok' }))
  expect((await screen.findByTestId('activity-empty')).textContent).toContain('Nothing of this kind yet.')
  expect((screen.getByRole('button', { name: 'Money' })).getAttribute('aria-pressed')).toBe('true')
})

it('a failed load says so, and Try again asks again', async () => {
  mockApi.getMyActivity.mockRejectedValueOnce(new Error('boom')).mockResolvedValue(page([item({ verb: 'first_sign_in' })]))
  render(<ActivityCard state={state('qc', ['see_all', 'qc'])} />)
  expect((await screen.findByRole('alert')).textContent).toContain('We could not load your activity.')
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByText('Signed in for the first time')).toBeTruthy()
})

it('an answer for a chip the reader has left never lands', async () => {
  let release: (p: ActivityPage) => void = () => {}
  mockApi.getMyActivity
    .mockImplementationOnce(() => new Promise<ActivityPage>((r) => { release = r }))
    .mockResolvedValueOnce(page([item({ id: 9, verb: 'profile_updated' })]))
  render(<ActivityCard state={state('reviewer', ['review'])} />)
  fireEvent.click(screen.getByRole('button', { name: 'Profile and sign-in' }))
  expect(await screen.findByText('Updated your profile')).toBeTruthy()
  release(page([item({ id: 1, verb: 'verdict_recorded' })]))
  await new Promise((r) => setTimeout(r, 20))
  expect(screen.getAllByTestId('activity-row')).toHaveLength(1)
  expect(screen.queryByText(/Recorded a verdict/)).toBeNull()
})
