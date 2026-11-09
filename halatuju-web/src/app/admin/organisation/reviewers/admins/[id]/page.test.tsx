/**
 * @jest-environment jsdom
 *
 * Team → an Admin or Finance person (2026-10-22, the owner's option A; one person page since Sprint T3,
 * 2026-11-09). The header is the `person` block on the permissions GET; the page has the same two tabs
 * as everybody's, Profile and Permissions. The card itself is `PermissionEditor.test.tsx`'s subject;
 * here what matters is the header (no role word, D9), the gate, the single request (the page hands its
 * GET to the card), and the way back to the Admins tab. The per-kind checks are in
 * `components/admin/person/TeamPersonPage.test.tsx`.
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

it('draws the header: name, email, the table chip, status, joined date — and no role word (D9)', async () => {
  await loaded()
  expect(screen.queryByText('admin.role.admin')).toBeNull()
  expect(screen.getByTestId('person-tables').textContent).toBe('admin.team.chip.admins')
  expect(screen.getByText('admin.reviewers.status.active')).toBeTruthy()
  expect(screen.getByText(`admin.reviewers.detail.joined(date=${formatDate(ARUN.created_at)})`))
    .toBeTruthy()
  expect(screen.getByTestId('person-email').textContent).toBe('arun@example.org')
  expect(screen.queryByTestId('person-invited')).toBeNull()
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
    .toBe('/admin/organisation/reviewers?tab=admins')
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
  mockApi.getStaffPermissions.mockRejectedValue(new Error('Admin not found'))
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

describe('Sprint T2: Revoke and Delete on an admin\'s own page (owner, 2026-11-08)', () => {
  const actions = () => within(screen.getByTestId('person-actions'))

  beforeEach(() => { window.confirm = jest.fn(() => true) })

  it('offers Revoke and a live Delete on an admin with no work, and goes back to Admins after it', async () => {
    mockApi.deleteAdmin.mockResolvedValue({ message: 'ok' } as never)
    await loaded({ deletable: true, work: {} })
    expect(actions().getByText('admin.revoke')).toBeTruthy()
    fireEvent.click(actions().getByTestId('staff-delete'))
    fireEvent.change(document.getElementById('typed-confirm')!, { target: { value: 'arun@example.org' } })
    fireEvent.click(screen.getByTestId('typed-confirm-go'))
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/admin/organisation/reviewers?tab=admins'))
    expect(mockApi.deleteAdmin).toHaveBeenCalledWith(14, { token: 'tok' })
  })

  it('greys the Delete of an admin with work, with the reason and its counts', async () => {
    await loaded({ deletable: false, work: { payment_runs: 2 } })
    expect(actions().queryByTestId('staff-delete')).toBeNull()
    const b = within(actions().getByTestId('staff-delete-greyed')).getByText('admin.delete')
    expect(b.getAttribute('aria-disabled')).toBe('true')
    expect(document.getElementById(b.getAttribute('aria-describedby')!)!.textContent)
      .toBe('admin.deleteHasWork(work=payment runs: 2)')
  })

  it('revokes after a confirm, and then reads Revoked with a Restore', async () => {
    mockApi.revokeAdmin.mockResolvedValue({} as never)
    await loaded({ deletable: false, work: { payment_runs: 2 } })
    fireEvent.click(actions().getByText('admin.revoke'))
    await waitFor(() => expect(actions().getByText('admin.restore')).toBeTruthy())
    expect(mockApi.revokeAdmin).toHaveBeenCalledWith(14, 'revoke', { token: 'tok' })
    expect(screen.getByText('admin.reviewers.status.revoked')).toBeTruthy()
  })

  it('shows the server\'s refusal in its own words', async () => {
    mockApi.deleteAdmin.mockRejectedValue(new Error('They have work on record now.'))
    await loaded({ deletable: true, work: {} })
    fireEvent.click(actions().getByTestId('staff-delete'))
    fireEvent.change(document.getElementById('typed-confirm')!, { target: { value: 'arun@example.org' } })
    fireEvent.click(screen.getByTestId('typed-confirm-go'))
    expect((await screen.findByRole('alert')).textContent).toBe('They have work on record now.')
    expect(mockPush).not.toHaveBeenCalled()
  })

  it('shows an organisation admin viewer no Delete and no Revoke on a fellow organisation admin', async () => {
    await loaded({ role: 'org_admin', deletable: true, work: {} })
    expect(actions().queryByText('admin.delete')).toBeNull()
    expect(actions().queryByText('admin.revoke')).toBeNull()
  })

  it('shows a super the Delete on that organisation admin', async () => {
    viewerRole = { role: 'reviewer', is_super_admin: true }
    await loaded({ role: 'org_admin', deletable: true, work: {} })
    expect(actions().getByTestId('staff-delete')).toBeTruthy()
  })

  // T2 review N2 / N3: the server's `revocable` and `delete_never`, drawn as it says.
  it('offers no Revoke where the server says it would refuse (a super, yourself, the sole org admin)', async () => {
    viewerRole = { role: 'reviewer', is_super_admin: true }
    await loaded({ revocable: false, delete_never: true, deletable: false, work: { payment_runs: 2 } })
    expect(actions().queryByText('admin.revoke')).toBeNull()
    expect(actions().queryByText('admin.delete')).toBeNull()
  })

  it('offers Revoke and a greyed Delete when revocable and only work stops the delete', async () => {
    await loaded({ revocable: true, delete_never: false, deletable: false, work: { payment_runs: 2 } })
    expect(actions().getByText('admin.revoke')).toBeTruthy()
    expect(actions().getByTestId('staff-delete-greyed')).toBeTruthy()
  })
})
