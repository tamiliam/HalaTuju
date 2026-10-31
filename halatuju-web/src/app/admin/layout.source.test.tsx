/**
 * @jest-environment jsdom
 *
 * The admin layout's source guard (source sign-in, review M3). A SOURCE user who reaches a staff page
 * — a typed URL, an old bookmark, a staff link — is sent to its own landing BEFORE that page or the
 * shell mounts, so not one staff fetch goes out (each would be refused: deny by default, S1). Its own
 * pages, and every staff user, pass untouched.
 */
import { useEffect } from 'react'
import { render, screen } from '@testing-library/react'
import AdminLayout from './layout'
import * as api from '@/lib/admin-api'

const replace = jest.fn()
let mockPath = '/admin/students'
let mockRole: Record<string, unknown> = {}
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace }),
  usePathname: () => mockPath,
}))
jest.mock('@/lib/messagesAdmin', () => ({}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  AdminAuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAdminAuth: () => ({ isAdminAuthenticated: true, isLoading: false, role: mockRole, token: 'tok' }),
}))
jest.mock('@/components/admin/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div data-testid="shell">{children}</div>,
}))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

/** Stands in for any staff page: it fetches a staff endpoint the moment it mounts. */
function StaffPage() {
  useEffect(() => { void mockApi.getInvitations('admins', { token: 'tok' }) }, [])
  return <p>staff page</p>
}

const SOURCE = { role: 'source_partner', is_admin: true, is_super_admin: false, source_name: 'MUETMyWay',
                 permissions: [] }

beforeEach(() => { jest.clearAllMocks(); mockRole = SOURCE })

it.each([
  '/admin', '/admin/students', '/admin/organisation', '/admin/organisation/staff', '/admin/organisation/reviewers',
  '/admin/sources', '/admin/sponsors', '/admin/sponsors/4', '/admin/requests', '/admin/billing', '/admin/payments',
  '/admin/programme', '/admin/contracts', '/admin/guide', '/admin/faq',
])('sends a source user away from %s before the page or the shell mounts', (path) => {
  mockPath = path
  render(<AdminLayout><StaffPage /></AdminLayout>)
  expect(replace).toHaveBeenCalledWith('/admin/programme/overview')
  expect(screen.queryByTestId('shell')).toBeNull()
  expect(screen.queryByText('staff page')).toBeNull()
  expect(mockApi.getInvitations).not.toHaveBeenCalled()
})

it.each(['/admin/programme/overview', '/admin/scholarship', '/admin/scholarship/104', '/admin/scholars',
  '/admin/scholars/104', '/admin/profile'])('lets a source user open its own page %s', (path) => {
  mockPath = path
  render(<AdminLayout><p>own page</p></AdminLayout>)
  expect(replace).not.toHaveBeenCalled()
  expect(screen.getByTestId('shell')).toBeTruthy()
})

it('leaves staff alone', () => {
  mockRole = { role: 'org_admin', is_admin: true, is_super_admin: false, permissions: [] }
  mockPath = '/admin/organisation/staff'
  render(<AdminLayout><StaffPage /></AdminLayout>)
  expect(replace).not.toHaveBeenCalled()
  expect(screen.getByText('staff page')).toBeTruthy()
})

// Student maintenance S7a (2026-10-31): a MENTOR is held the same way — its only page is Profile.
const MENTOR = { role: 'mentor', is_admin: true, is_super_admin: false, permissions: [] }

it.each([
  '/admin', '/admin/organisation', '/admin/organisation/mentors', '/admin/organisation/staff',
  '/admin/programme/overview', '/admin/scholarship', '/admin/scholars/104', '/admin/guide',
])('sends a mentor away from %s to its Profile before the page or the shell mounts', (path) => {
  mockRole = MENTOR
  mockPath = path
  render(<AdminLayout><StaffPage /></AdminLayout>)
  expect(replace).toHaveBeenCalledWith('/admin/profile')
  expect(screen.queryByTestId('shell')).toBeNull()
  expect(mockApi.getInvitations).not.toHaveBeenCalled()
})

it('lets a mentor open its Profile', () => {
  mockRole = MENTOR
  mockPath = '/admin/profile'
  render(<AdminLayout><p>own page</p></AdminLayout>)
  expect(replace).not.toHaveBeenCalled()
  expect(screen.getByTestId('shell')).toBeTruthy()
})
