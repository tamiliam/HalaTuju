/**
 * @jest-environment jsdom
 *
 * #86 (review round 1): a signed-out visit to an admin page (the "returned by QC" email's case link)
 * is sent to sign-in WITH the page as a safe `next`, so the reviewer comes back to the case.
 */
import { render } from '@testing-library/react'
import AdminLayout from './layout'

const replace = jest.fn()
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace }),
  usePathname: () => window.location.pathname,
}))
jest.mock('@/lib/messagesAdmin', () => ({}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-auth-context', () => ({
  AdminAuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAdminAuth: () => ({ isAdminAuthenticated: false, isLoading: false, role: null, token: null }),
}))
jest.mock('@/components/admin/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

beforeEach(() => replace.mockReset())
afterEach(() => window.history.pushState({}, '', '/'))

it('carries the case page through sign-in', () => {
  window.history.pushState({}, '', '/admin/scholarship/513')
  render(<AdminLayout><p>case</p></AdminLayout>)
  expect(replace).toHaveBeenCalledWith('/admin/login?next=%2Fadmin%2Fscholarship%2F513')
})

it('keeps the list filters too', () => {
  window.history.pushState({}, '', '/admin/scholarship?assigned=me&band=open')
  render(<AdminLayout><p>list</p></AdminLayout>)
  expect(replace).toHaveBeenCalledWith(
    `/admin/login?next=${encodeURIComponent('/admin/scholarship?assigned=me&band=open')}`)
})
