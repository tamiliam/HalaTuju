/**
 * @jest-environment jsdom
 *
 * Team → an Admin or Finance person → Permissions (2026-10-22, the owner's option A): their own
 * page, with a header drawn from the permissions GET and ONE tab, "Permissions". The card itself is
 * `PermissionEditor.test.tsx`'s subject; here what matters is the header, the gate, the single
 * request (the page hands its GET to the card), and the way back to the Admins tab.
 */
import { render, screen, waitFor } from '@testing-library/react'
import AdminPersonPage from './page'
import * as api from '@/lib/admin-api/admins'
import { formatDate } from '@/lib/formatDate'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
jest.mock('next/navigation', () => ({ useParams: () => ({ id: '14' }) }))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({
    t: (k: string, p?: Record<string, string>) =>
      p ? `${k}(${Object.entries(p).map(([a, b]) => `${a}=${b}`).join(';')})` : k,
  }),
}))
let viewerRole: { role: string; is_super_admin?: boolean } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: viewerRole }),
}))
jest.mock('@/lib/admin-api/admins')
let handed: api.StaffPermissionsView | undefined
jest.mock('@/components/admin/LazyPermissionEditor', () => ({
  __esModule: true,
  default: ({ adminId, initial }: { adminId: number; initial?: api.StaffPermissionsView }) => {
    handed = initial
    return <div data-testid="perm-editor">{adminId}</div>
  },
}))

const mockApi = api as jest.Mocked<typeof api>
const ARUN: api.StaffPermissionsView = {
  id: 14, name: 'Arun Pillai', role: 'admin', is_active: true, editable: true,
  preset: ['see_all', 'spending', 'payments_prepare'], permissions: ['see_all'], custom: true,
  keys: [], email: 'arun@example.org', created_at: '2026-03-01T00:00:00Z', signed_in: true,
  paused: false, history: [],
}

beforeEach(() => {
  jest.clearAllMocks()
  viewerRole = { role: 'org_admin' }
  handed = undefined
  mockApi.getStaffPermissions.mockResolvedValue(ARUN)
})

const loaded = async (over: Partial<api.StaffPermissionsView> = {}) => {
  mockApi.getStaffPermissions.mockResolvedValue({ ...ARUN, ...over })
  render(<AdminPersonPage />)
  await waitFor(() => expect(screen.getByText('Arun Pillai')).toBeTruthy())
}

it('draws the header: name, role, status, joined date and email', async () => {
  await loaded()
  expect(screen.getByText('admin.role.admin')).toBeTruthy()
  expect(screen.getByText('admin.reviewers.status.active')).toBeTruthy()
  expect(screen.getByText(`admin.reviewers.detail.joined(date=${formatDate(ARUN.created_at)})`))
    .toBeTruthy()
  expect(screen.getByText('arun@example.org')).toBeTruthy()
  expect(screen.queryByTestId('person-invited')).toBeNull()
})

it('says Invited when no sign-in is recorded, and Revoked over everything', async () => {
  await loaded({ signed_in: false, is_active: false })
  expect(screen.getByTestId('person-invited').textContent).toBe('admin.person.invited')
  expect(screen.getByText('admin.reviewers.status.revoked')).toBeTruthy()
})

it('has ONE tab, Permissions, and hands the card the GET it already made', async () => {
  await loaded()
  expect(screen.getAllByRole('tab').map((b) => b.textContent)).toEqual(['admin.person.tabPermissions'])
  expect(screen.getByTestId('perm-editor').textContent).toBe('14')
  expect(handed?.id).toBe(14)
  expect(mockApi.getStaffPermissions).toHaveBeenCalledTimes(1)
  expect(mockApi.getStaffPermissions).toHaveBeenCalledWith(14, { token: 'tok' })
})

it('goes back to the Admins tab of Team', async () => {
  await loaded()
  expect(screen.getByText('← admin.person.back').closest('a')!.getAttribute('href'))
    .toBe('/admin/organisation/reviewers?tab=admins')
})

it('tells an admin or finance viewer they may not, and asks the server nothing', async () => {
  for (const r of ['admin', 'finance']) {
    viewerRole = { role: r }
    const { unmount } = render(<AdminPersonPage />)
    expect(screen.getByText('admin.person.notAllowed')).toBeTruthy()
    unmount()
  }
  expect(mockApi.getStaffPermissions).not.toHaveBeenCalled()
})

it('refuses a reviewer the way the Team page does', () => {
  viewerRole = { role: 'reviewer' }
  render(<AdminPersonPage />)
  expect(screen.getByText('apiErrors.superAdminRequired')).toBeTruthy()
})

it('shows the shared not-found state on a 404 (another organisation, or nobody)', async () => {
  mockApi.getStaffPermissions.mockRejectedValue(new Error('Admin not found'))
  render(<AdminPersonPage />)
  await waitFor(() => expect(screen.getByTestId('record-not-found')).toBeTruthy())
  expect(screen.queryByTestId('perm-editor')).toBeNull()
})

it('lets a super open it too', async () => {
  viewerRole = { role: 'reviewer', is_super_admin: true }
  await loaded()
  expect(screen.getByTestId('perm-editor')).toBeTruthy()
})
