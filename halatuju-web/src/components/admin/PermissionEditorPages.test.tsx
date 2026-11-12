/**
 * @jest-environment jsdom
 *
 * Sprint M2b (D9): the Permissions tab draws the v2 PAGE keys by group, under "Admin permissions" — a
 * switch per key the server lets this viewer store, the rest LOCKED with the server's reason; the set is
 * one list (today's keys + the stored page keys); "Custom" and Reset weigh the page part against the
 * role's own (`v2_preset`, or the Admins table's `table_presets`). Nothing here re-derives who may hold
 * what: `grantable`, `reason` and `held` are served.
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import PermissionEditor from './PermissionEditor'
import PermissionHistory from './PermissionHistory'
import PermissionChips from './PermissionChips'
import { permName } from './permName'
import * as api from '@/lib/admin-api/admins'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

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
const PRESET_V2 = ['invitations.view', 'team.view', 'sponsors.view', 'sponsors.edit']
const k = (key: string, grantable: boolean, reason: api.StaffV2Key['reason'], held = false): api.StaffV2Key => ({
  key, page: key.split('.')[0], level: key.split('.')[1], grantable, reason, held,
})
const GROUPS: api.StaffV2Group[] = [
  { group: 'organisation', keys: [
    k('invitations.view', true, null), k('invitations.edit', false, 'lead_only'), k('team.view', true, null),
    k('sponsors.view', true, null), k('sponsors.edit', true, null), k('billing.edit', false, 'never_grantable')] },
  { group: 'programme', keys: [k('students.view', false, 'alias', true)] },
]
const ADMIN: api.StaffPermissionsView = {
  id: 9, name: 'Staff One', role: 'admin', is_active: true, editable: true,
  preset: ['see_all', 'scholars', 'spending', 'payments_prepare'],
  permissions: ['see_all', 'scholars', 'spending', 'payments_prepare'], custom: false, keys: KEYS,
  tables: ['admins'], v2_keys: GROUPS, v2_held: PRESET_V2, v2_preset: PRESET_V2,
  table_presets: { admins: ['see_all', 'scholars', 'spending', 'payments_prepare', ...PRESET_V2], reviewers: ['review'] },
}
const plan = (over: Partial<api.StaffPermissionsPlan>): api.StaffPermissionsPlan => ({
  id: 9, role: 'admin', dry_run: true, changed: true, permissions: ADMIN.permissions, custom: true,
  added: [], removed: [], consequences: [], v2_held: PRESET_V2, ...over,
})
const name = (key: string) => permName((x, p) => (p ? `${x}(${Object.entries(p).map(([a, b]) => `${a}=${b}`).join(';')})` : x), key)
const toggle = (key: string) => screen.getByRole('switch', { name: name(key) })
const isOn = (key: string) => toggle(key).getAttribute('aria-checked') === 'true'

async function open(view: api.StaffPermissionsView = ADMIN, table?: 'admins' | 'reviewers') {
  mockApi.getStaffPermissions.mockResolvedValue(view)
  render(<PermissionEditor adminId={9} name="Staff One" token="tok" table={table} />)
  await waitFor(() => expect(screen.getByTestId('permission-editor')).toBeTruthy())
}

beforeEach(() => { jest.clearAllMocks(); mockApi.saveStaffPermissions.mockResolvedValue(plan({})) })
afterEach(cleanup)

it('draws the page keys by group, the stored ones on, the rest locked with the server reason', async () => {
  await open()
  const pages = screen.getByTestId('perm-section-pages')
  expect(within(pages).getByText('admin.permV2.title')).toBeTruthy()
  expect(within(pages).getByText('admin.permV2.group.organisation')).toBeTruthy()
  expect(within(pages).getByText('admin.permV2.group.programme')).toBeTruthy()
  expect(isOn('team.view')).toBe(true)
  expect((toggle('team.view') as HTMLButtonElement).disabled).toBe(false)
  for (const [key, reason] of [['invitations.edit', 'lead_only'], ['billing.edit', 'never_grantable'],
    ['students.view', 'alias']]) {
    expect((toggle(key) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByTestId(`v2-reason-${key}`).textContent).toBe(`admin.permV2.reason.${reason}`)
  }
  expect(isOn('students.view')).toBe(true)            // held through Applications, and says so
  expect(isOn('billing.edit')).toBe(false)
  expect(screen.queryByText('admin.permEditor.custom')).toBeNull()    // on its preset, both parts
  expect(mockApi.saveStaffPermissions).not.toHaveBeenCalled()
})

it('sends the whole set — today\'s keys and the page keys — and a change brings its page view', async () => {
  mockApi.saveStaffPermissions.mockResolvedValue(plan({}))
  await open({ ...ADMIN, v2_held: ['invitations.view', 'team.view'] })
  fireEvent.click(toggle('sponsors.edit'))
  expect(isOn('sponsors.view')).toBe(true)
  await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenLastCalledWith(9,
    [...ADMIN.permissions, 'invitations.view', 'team.view', 'sponsors.edit', 'sponsors.view'], true, { token: 'tok' }))
  fireEvent.click(toggle('sponsors.view'))           // a page's view off takes its change with it
  expect(isOn('sponsors.edit')).toBe(false)
  // back to the set it holds: nothing to ask, nothing to save
  expect(screen.getByText('admin.permEditor.noChange(name=Staff One)')).toBeTruthy()
  expect(mockApi.saveStaffPermissions).toHaveBeenCalledTimes(1)
})

it('"Custom" and Reset weigh the page part against the role\'s own', async () => {
  mockApi.saveStaffPermissions.mockResolvedValue(plan({}))
  await open()
  fireEvent.click(toggle('team.view'))
  expect(screen.getByText('admin.permEditor.custom')).toBeTruthy()
  await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenCalled())
  fireEvent.click(screen.getByTestId('perm-reset'))
  expect(isOn('team.view')).toBe(true)
  expect(screen.queryByText('admin.permEditor.custom')).toBeNull()
})

it('opened from the Admins table, the served table preset (with its page keys) is the preset', async () => {
  await open(ADMIN, 'admins')
  expect(screen.queryByText('admin.permEditor.custom')).toBeNull()
  fireEvent.click(toggle('sponsors.edit'))
  expect(screen.getByText('admin.permEditor.custom')).toBeTruthy()
  await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenCalled())
})

it('opened from the Reviewers table, no page keys are drawn', async () => {
  await open({ ...ADMIN, role: 'reviewer', tables: ['admins', 'reviewers'], permissions: ['review'] }, 'reviewers')
  expect(screen.queryByTestId('perm-section-pages')).toBeNull()
})

it('a save keeps the page keys the server answers with', async () => {
  mockApi.saveStaffPermissions.mockResolvedValue(plan({ dry_run: false, v2_held: ['invitations.view', 'sponsors.view'] }))
  await open()
  fireEvent.click(toggle('team.view'))
  await waitFor(() => expect(screen.getByText('admin.permEditor.save')).toBeTruthy())
  await waitFor(() => expect((screen.getByText('admin.permEditor.save') as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByText('admin.permEditor.save'))
  await waitFor(() => expect(isOn('sponsors.edit')).toBe(false))
  expect(isOn('sponsors.view')).toBe(true)
})

it('an older api with no page keys draws no Pages section and sends today\'s keys as before', async () => {
  await open({ ...ADMIN, v2_keys: undefined, v2_held: undefined, v2_preset: undefined })
  expect(screen.queryByTestId('perm-section-pages')).toBeNull()
  expect(screen.queryByText('admin.permEditor.custom')).toBeNull()
})

describe('permName: a v2 page key reads "<page>: <level>"', () => {
  it('words both kinds of key', () => {
    expect(name('see_all')).toBe('admin.perm.see_all.name')
    expect(name('sponsors.edit')).toBe(
      'admin.permV2.name(page=admin.permV2.page.sponsors;level=admin.permV2.level.edit)')
  })

  it('has every page, level, group and reason in all three languages', () => {
    const pages = ['invitations', 'team', 'sources', 'sponsors', 'billing', 'requests', 'settings', 'students',
      'scholars', 'contracts', 'programmes', 'announcements', 'surveys', 'development', 'mentoring', 'payments',
      'spending']
    for (const m of [en, ms, ta]) {
      const v2 = (m as { admin: { permV2: Record<string, Record<string, string> | string> } }).admin.permV2
      expect(Object.keys(v2.page as object).sort()).toEqual([...pages].sort())
      expect(Object.keys(v2.level as object).sort()).toEqual(['approve', 'check', 'edit', 'prepare', 'view'])
      expect(Object.keys(v2.group as object).sort()).toEqual(['engagement', 'money', 'organisation', 'programme'])
      expect(Object.keys(v2.reason as object).sort()).toEqual(['alias', 'lead_only', 'never_grantable'])
    }
  })

  it('the history and the chips word a v2 key', () => {
    render(<PermissionHistory name="Staff One" role="admin" rows={[{ kind: 'edit', role: 'admin', before: [],
      after: ['team.view'], added: ['team.view'], removed: [], at: '2026-11-12T00:00:00Z', by: '', by_super: false,
      by_migration: true }]} />)
    expect(screen.getByText(`admin.permHistory.on(perm=${name('team.view')})`)).toBeTruthy()
    render(<PermissionChips row={{ custom: true, permissions_added: [], permissions_removed: ['surveys.edit'] }} />)
    expect(screen.getByText(name('surveys.edit'))).toBeTruthy()
  })
})
