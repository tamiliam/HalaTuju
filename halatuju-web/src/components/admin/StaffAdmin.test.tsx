/**
 * @jest-environment jsdom
 *
 * The Staff table's Status cell.
 *
 * Until 2026-08-03 this column read `is_active` and nothing else, so the SAME reviewer showed
 * "Paused" on Organisation → Reviewers and "Active" here. `paused_at` existed on the model and on
 * one of its two readers; this screen had simply never asked the server for it.
 *
 * The precedence assertion is the one worth keeping: revoked beats paused, because a revoked
 * account cannot be brought back by un-pausing, and naming the smaller of two facts sends an
 * org_admin to the wrong control.
 */
import { render, screen } from '@testing-library/react'
import { StaffTable } from './StaffAdmin'
import type { AdminItem } from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

const row = (over: Partial<AdminItem>): AdminItem => ({
  id: 1, name: 'Someone', email: 's@example.org', is_super_admin: false,
  role: 'reviewer', is_active: true, org_name: null, created_at: '2026-06-01T00:00:00Z',
  ...over,
} as AdminItem)

const draw = (rows: AdminItem[]) => render(<StaffTable rows={rows} canAct={false} />)

it('says a paused reviewer is paused, instead of calling them active', () => {
  draw([row({ id: 1, name: 'Vanitha', paused: true, paused_at: '2026-08-02T17:11:18Z' })])
  expect(screen.getByText('admin.reviewers.status.paused')).toBeTruthy()
  expect(screen.queryByText('admin.active')).toBeNull()
})

it('still says active for somebody who has not stepped back', () => {
  // A flag that is always true says nothing — assert the ordinary case stays ordinary.
  draw([row({ id: 2, name: 'Working', paused: false })])
  expect(screen.getByText('admin.active')).toBeTruthy()
  expect(screen.queryByText('admin.reviewers.status.paused')).toBeNull()
})

it('reports REVOKED over paused when somebody is both', () => {
  draw([row({ id: 3, name: 'Gone', is_active: false, paused: true })])
  expect(screen.getByText('admin.revoked')).toBeTruthy()
  expect(screen.queryByText('admin.reviewers.status.paused')).toBeNull()
})

it('treats a payload with no pause field as not paused, never as broken', () => {
  // An older cached payload, or any role the server does not compute pause for.
  draw([row({ id: 4, name: 'Legacy' })])
  expect(screen.getByText('admin.active')).toBeTruthy()
})
