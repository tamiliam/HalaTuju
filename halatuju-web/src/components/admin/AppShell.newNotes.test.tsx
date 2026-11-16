/**
 * @jest-environment jsdom
 *
 * Request #73 (2026-11-16): the bell's "new note" line. The shell reads the served count of STUDENTS with a note
 * from the other side the person has not opened (`getNewNoteCount`), and the bell shows it as an `info` line
 * that is a REAL LINK (a 44 px target): an org admin's goes to the applications table, a reviewer's to their own
 * cases. One and many are worded apart. A failed read never blocks the shell, and the bell keeps its note.
 * (Its own file: AppShell.test.tsx sits at the 600-line limit.)
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'

import { AppShell } from './AppShell'
import type { AdminRoleName } from '@/lib/navigation'
import * as adminApi from '@/lib/admin-api'

let mockRole: Record<string, unknown> = {}
jest.mock('next/navigation', () => ({
  usePathname: () => '/admin/scholarship',
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, vars?: Record<string, string>) => (vars ? `${k}:${Object.values(vars).join('|')}` : k) }),
}))
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ role: jest.requireActual('@/test/staffPresets').withServedPageKeys(mockRole), token: 'test-token' }) }))
jest.mock('@/lib/admin-supabase', () => ({ adminSignOut: jest.fn() }))
jest.mock('@/lib/admin-api', () => ({
  getPendingSponsorCount: jest.fn(() => Promise.resolve({ count: 0 })),
  getOrgRequestCount: jest.fn(() => Promise.reject(new Error('404'))),
  getBillingUsage: jest.fn(() => Promise.reject(new Error('404'))),
  getAdminScopes: jest.fn(() => Promise.resolve({ organisations: [], programmes: [] })),
  getPaymentRuns: jest.fn(() => Promise.resolve({ runs: [] })),
  getSystemHealth: jest.fn(() => Promise.resolve({ overall: 'green', checked_at: new Date().toISOString(), rows: [] })),
  getNewNoteCount: jest.fn(() => Promise.resolve({ from_reviewer: 0, from_org_admin: 0 })),
}))

const counts = jest.mocked(adminApi.getNewNoteCount)
const asRole = (role: AdminRoleName) => { mockRole = { role, admin_name: 'Test Person', is_super_admin: false } }
const A = 'admin.shell.attn'

async function openBell() {
  fireEvent.click(screen.getByRole('button', { name: 'admin.shell.notifications' }))
  return screen.findByRole('menu', { name: 'admin.shell.notifications' })
}

beforeEach(() => { counts.mockClear(); counts.mockResolvedValue({ from_reviewer: 0, from_org_admin: 0 }) })

it("an org admin's line counts the students with a reviewer's note, and links to the applications table", async () => {
  counts.mockResolvedValue({ from_reviewer: 3, from_org_admin: 0 })
  asRole('org_admin')
  render(<AppShell>content</AppShell>)
  await waitFor(() => expect(counts).toHaveBeenCalledWith({ token: 'test-token' }))
  const bell = await openBell()
  const line = await within(bell).findByText(`${A}.notesFromReviewer:3`)
  const link = line.closest('a') as HTMLAnchorElement
  expect(link.getAttribute('href')).toBe('/admin/scholarship')
  expect(link.className).toContain('min-h-11')
  expect(within(bell).getByText('admin.shell.attentionNote')).toBeTruthy()   // the bell keeps its note
})

it("a reviewer's line is worded for one student and links to their own cases", async () => {
  counts.mockResolvedValue({ from_reviewer: 0, from_org_admin: 1 })
  asRole('reviewer')
  render(<AppShell>content</AppShell>)
  await waitFor(() => expect(counts).toHaveBeenCalled())
  const bell = await openBell()
  const line = await within(bell).findByText(`${A}.notesFromOrgAdminOne:1`)
  expect((line.closest('a') as HTMLAnchorElement).getAttribute('href')).toBe('/admin/scholarship?assigned=me')
  expect(within(bell).queryByText(/notesFromReviewer/)).toBeNull()
})

it('says nothing at zero', async () => {
  asRole('org_admin')
  render(<AppShell>content</AppShell>)
  await waitFor(() => expect(counts).toHaveBeenCalled())
  const bell = await openBell()
  expect(within(bell).getByText('admin.shell.nothingWaiting')).toBeTruthy()
})

it('a failed read never blocks the shell', async () => {
  counts.mockRejectedValue(new Error('500'))
  asRole('org_admin')
  render(<AppShell>content</AppShell>)
  await waitFor(() => expect(counts).toHaveBeenCalled())
  expect(screen.getByText('content')).toBeTruthy()
  const bell = await openBell()
  expect(within(bell).queryByText(/notesFrom/)).toBeNull()
})

it('a source partner is never on a case, so the count is not asked for', async () => {
  asRole('source_partner')
  render(<AppShell>content</AppShell>)
  await waitFor(() => expect(adminApi.getAdminScopes).toHaveBeenCalled())
  expect(counts).not.toHaveBeenCalled()
})
