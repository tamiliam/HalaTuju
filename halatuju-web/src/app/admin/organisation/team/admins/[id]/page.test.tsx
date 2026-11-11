/**
 * @jest-environment jsdom
 *
 * Team → an Admin or Finance person (2026-10-22, the owner's option A; one person page since Sprint T3,
 * 2026-11-09). The header is the `person` block on the permissions GET; the page has the same two tabs
 * as everybody's, Profile and Permissions. The card itself is `PermissionEditor.test.tsx`'s subject;
 * here what matters is the header (no role word, D9), the gate, the single request (the page hands its
 * GET to the card), and the way back to the Admins tab. The per-kind checks are in
 * `components/admin/person/GroupPages*.test.tsx`.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import AdminPersonPage from './page'
import * as api from '@/lib/admin-api/admins'
import { formatDate } from '@/lib/formatDate'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
const mockPush = jest.fn()
jest.mock('next/navigation', () => ({
  useParams: () => ({ id: '14' }), useSearchParams: () => null, useRouter: () => ({ push: mockPush }),
}))
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
jest.mock('@/components/admin/PermissionEditor', () => ({
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
  person: {
    admin_id: 14, mentor_id: null, name: 'Arun Pillai', email: 'arun@example.org', tables: ['admins'],
    lead: false, mentor_only: false, is_active: true, paused: false, joined_at: '2026-03-01T00:00:00Z',
    signed_in: true, last_seen_at: '2026-11-01T00:00:00Z',
    profile: { job_title: 'Programme officer', about: '', qualification: '', university: '', graduation_year: null,
      field_of_study: '', phone: '', languages: ['en', 'ms'], other_language: '' },
  },
}

beforeEach(() => {
  jest.clearAllMocks()
  viewerRole = { role: 'org_admin' }
  handed = undefined
  mockApi.getStaffPermissions.mockResolvedValue(ARUN)
})

const loaded = async (over: Partial<api.StaffPermissionsView> = {}, person: Partial<api.TeamPersonBlock> = {}) => {
  mockApi.getStaffPermissions.mockResolvedValue({ ...ARUN, ...over, person: { ...ARUN.person!, ...person } })
  render(<AdminPersonPage />)
  await waitFor(() => expect(screen.getByText('Arun Pillai')).toBeTruthy())
}

it('draws the header: name, the table chip, status, joined date — no email (O11) and no role word (D9)', async () => {
  await loaded()
  expect(screen.queryByText('admin.role.admin')).toBeNull()
  expect(screen.getByTestId('person-tables').textContent).toBe('admin.team.chip.admins')
  expect(screen.getByText('admin.reviewers.status.active')).toBeTruthy()
  expect(screen.getByText(`admin.reviewers.detail.joined(date=${formatDate(ARUN.created_at)})`))
    .toBeTruthy()
  // O11 (owner, 2026-11-10): the header drops the email under the name; it stays in About.
  expect(screen.queryByTestId('person-email')).toBeNull()
  expect(screen.getByTestId('person-header').textContent).not.toContain('arun@example.org')
  expect(screen.getByTestId('person-field-email').textContent).toContain('arun@example.org')
  expect(screen.queryByTestId('person-invited')).toBeNull()
})

it('O11: a person with no name is headed by their email, the one place it still shows up top', async () => {
  mockApi.getStaffPermissions.mockResolvedValue({ ...ARUN, name: '', person: { ...ARUN.person!, name: '' } })
  render(<AdminPersonPage />)
  expect((await screen.findByRole('heading', { level: 1 })).textContent).toBe('arun@example.org')
})

it('O10: a super opens the organisation admin\'s page — no Revoke, no Remove, no dead Delete', async () => {
  viewerRole = { role: 'reviewer', is_super_admin: true }
  // The sole organisation admin, as the server serves them to a super (`delete_fields`).
  await loaded({ role: 'org_admin', editable: false, revocable: false, delete_never: true, deletable: false,
    work: { payment_runs: 1 } }, { lead: true })
  expect(screen.queryByTestId('person-action-row')).toBeNull()      // M1b (O3): Suspend and Delete are on Staff
  expect(screen.queryByText('admin.revoke')).toBeNull()
  expect(screen.queryByText('admin.delete')).toBeNull()
  expect(screen.queryByTestId('remove-from-admins')).toBeNull()
  expect(screen.getByTestId('person-tables').textContent).toContain('admin.team.chip.lead')
  fireEvent.click(screen.getByText('admin.person.tabPermissions'))
  expect(screen.getByTestId('perm-editor').textContent).toBe('14')
  window.history.replaceState(null, '', window.location.pathname)   // the tab writes #permissions
})

it('says Invited when no sign-in is recorded, and Revoked over everything', async () => {
  await loaded({}, { signed_in: false, is_active: false })
  expect(screen.getByTestId('person-invited').textContent).toBe('admin.person.invited')
  expect(screen.getByText('admin.reviewers.status.revoked')).toBeTruthy()
})

it('has the two tabs, opens on Profile, and hands the card the GET it already made', async () => {
  await loaded()
  expect(screen.getAllByRole('tab').map((b) => b.textContent))
    .toEqual(['admin.person.tabProfile', 'admin.person.tabPermissions'])
  expect(screen.getByTestId('person-field-jobTitle').textContent).toBe('Programme officer')
  expect(screen.queryByTestId('perm-editor')).toBeNull()
  fireEvent.click(screen.getByText('admin.person.tabPermissions'))
  expect(screen.getByTestId('perm-editor').textContent).toBe('14')
  expect(handed?.id).toBe(14)
  expect(mockApi.getStaffPermissions).toHaveBeenCalledTimes(1)
  expect(mockApi.getStaffPermissions).toHaveBeenCalledWith(14, { token: 'tok' })
})

it('goes back to the Admins tab of Team', async () => {
  await loaded()
  expect(screen.getByText('← admin.person.backTo.admins').closest('a')!.getAttribute('href'))
    .toBe('/admin/organisation/team?tab=admins')
})

it('tells an admin or finance viewer they may not, and asks the server nothing', async () => {
  for (const r of ['admin', 'finance']) {
    viewerRole = { role: r }
    const { unmount } = render(<AdminPersonPage />)
    expect(await screen.findByText('admin.person.notAllowed')).toBeTruthy()
    unmount()
  }
  expect(mockApi.getStaffPermissions).not.toHaveBeenCalled()
})

it('refuses a reviewer the way the Team page does', async () => {
  viewerRole = { role: 'reviewer' }
  render(<AdminPersonPage />)
  expect(await screen.findByText('apiErrors.superAdminRequired')).toBeTruthy()
})

it('shows the shared not-found state on a 404 (another organisation, or nobody)', async () => {
  mockApi.getStaffPermissions.mockRejectedValue(Object.assign(new Error('Admin not found'), { status: 404 }))
  render(<AdminPersonPage />)
  await waitFor(() => expect(screen.getByTestId('record-not-found')).toBeTruthy())
  expect(screen.queryByTestId('perm-editor')).toBeNull()
})

it('lets a super open it too', async () => {
  viewerRole = { role: 'reviewer', is_super_admin: true }
  await loaded()
  fireEvent.click(screen.getByText('admin.person.tabPermissions'))
  expect(screen.getByTestId('perm-editor')).toBeTruthy()
})

describe('M1b (owner O3, O10): Suspend and Delete live on Team -> Staff, not on an admin\'s page', () => {
  it.each([
    ['a deletable admin', { deletable: true, work: {} }],
    ['an admin with work', { deletable: false, work: { payment_runs: 2 } }],
    ['a revocable admin', { revocable: true, delete_never: false, deletable: false, work: {} }],
  ])('%s: no Revoke, no Restore, no Delete, no action row', async (_n, over) => {
    viewerRole = { role: 'reviewer', is_super_admin: true }
    await loaded(over as Partial<api.StaffPermissionsView>)
    expect(screen.queryByTestId('person-action-row')).toBeNull()
    for (const k of ['admin.revoke', 'admin.restore', 'admin.delete']) expect(screen.queryByText(k)).toBeNull()
    expect(mockApi.deleteAdmin).not.toHaveBeenCalled()
  })

  it('O10: a fellow organisation admin\'s page is read-only for an organisation admin (`manageable: false`)', async () => {
    await loaded({ role: 'org_admin', editable: false, manageable: false } as Partial<api.StaffPermissionsView>, { lead: true })
    expect(screen.queryByTestId('person-action-row')).toBeNull()
    expect(screen.queryByText('admin.reviewers.detail.pause')).toBeNull()
    fireEvent.click(screen.getByText('admin.person.tabPermissions'))
    expect(screen.getByTestId('perm-editor').textContent).toBe('14')   // shown (locked, `editable: false`)
    window.history.replaceState(null, '', window.location.pathname)
  })
})
