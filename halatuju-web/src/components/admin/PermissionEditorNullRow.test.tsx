/**
 * @jest-environment jsdom
 *
 * Sprint M2b review (d): a NULL row (permissions stored as NULL = the role's preset) stores no page key,
 * yet holds its preset — a NULL finance row reads the organisation through its Admins seat. The server
 * says it is not custom (`custom: false`), so the Permissions tab shows no "Custom" chip and Reset has
 * nothing to do, from the whole tab and from the Admins table alike, until somebody changes a switch.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import PermissionEditor from './PermissionEditor'
import { permName } from './permName'
import * as api from '@/lib/admin-api/admins'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({
    t: (k: string, p?: Record<string, string>) =>
      p ? `${k}(${Object.entries(p).map(([a, b]) => `${a}=${b}`).join(';')})` : k,
  }),
}))
jest.mock('@/lib/admin-api/admins')
const mockApi = api as jest.Mocked<typeof api>

const KEYS = ['review', 'see_all', 'scholars', 'qc', 'spending', 'payments_prepare', 'payments_check',
  'payments_approve', 'award_withdraw_request', 'award_withdraw_approve']
const ORG_READ = ['invitations.view', 'team.view', 'sponsors.view']
const ADMIN_V2 = [...ORG_READ, 'sponsors.edit']
const k = (key: string, held: boolean): api.StaffV2Key => ({
  key, page: key.split('.')[0], level: key.split('.')[1], grantable: true, reason: null, held,
})
const groups = (held: readonly string[]): api.StaffV2Group[] => [{ group: 'organisation',
  keys: ['invitations.view', 'team.view', 'sponsors.view', 'sponsors.edit'].map((x) => k(x, held.includes(x))) }]

// NULL rows as the server serves them: `permissions` resolved to the preset, no stored page key, not custom.
const NULL_FINANCE: api.StaffPermissionsView = {
  id: 7, name: 'Staff Two', role: 'finance', is_active: true, editable: true,
  preset: ['payments_approve'], permissions: ['payments_approve'], custom: false, keys: KEYS,
  tables: ['admins'], v2_keys: groups(ORG_READ), v2_held: [], v2_preset: ORG_READ,
  table_presets: { admins: ['payments_approve', ...ORG_READ], reviewers: [] },
}
const NULL_ADMIN: api.StaffPermissionsView = {
  id: 8, name: 'Staff Three', role: 'admin', is_active: true, editable: true,
  preset: ['see_all', 'scholars', 'spending', 'payments_prepare'],
  permissions: ['see_all', 'scholars', 'spending', 'payments_prepare'], custom: false, keys: KEYS,
  tables: ['admins'], v2_keys: groups(ADMIN_V2), v2_held: [], v2_preset: ADMIN_V2,
  table_presets: { admins: ['see_all', 'scholars', 'spending', 'payments_prepare', ...ADMIN_V2], reviewers: ['review'] },
}
const tr = (x: string, p?: Record<string, string>) => (p ? `${x}(${Object.entries(p).map(([a, b]) => `${a}=${b}`).join(';')})` : x)

async function open(view: api.StaffPermissionsView, table?: 'admins') {
  mockApi.getStaffPermissions.mockResolvedValue(view)
  render(<PermissionEditor adminId={view.id} name={view.name} token="tok" table={table} />)
  await waitFor(() => expect(screen.getByTestId('permission-editor')).toBeTruthy())
}

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.saveStaffPermissions.mockResolvedValue({
    id: 7, role: 'finance', dry_run: true, changed: true, permissions: ['payments_approve', 'see_all'],
    custom: true, added: ['see_all'], removed: [], consequences: [], v2_held: [],
  })
})
afterEach(cleanup)

for (const [label, view] of [['a NULL finance row', NULL_FINANCE], ['a NULL admin row', NULL_ADMIN]] as const) {
  for (const table of [undefined, 'admins'] as const) {
    it(`${label} is not Custom and has nothing to reset (${table ?? 'whole tab'})`, async () => {
      await open(view, table)
      expect(screen.queryByText('admin.permEditor.custom')).toBeNull()
      expect((screen.getByTestId('perm-reset') as HTMLButtonElement).disabled).toBe(true)
    })
  }
}

it('a NULL finance row turns Custom once a switch is changed, as the server will then say', async () => {
  await open(NULL_FINANCE)
  fireEvent.click(screen.getByRole('switch', { name: permName(tr, 'see_all') }))
  await waitFor(() => expect(screen.getByText('admin.permEditor.custom')).toBeTruthy())
  expect((screen.getByTestId('perm-reset') as HTMLButtonElement).disabled).toBe(false)
})
