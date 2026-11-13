/**
 * @jest-environment jsdom
 *
 * Sprint M2b (D9), laid out BY PAGE in sprint M2d: the v2 PAGE keys sit in the Organisation and Programme
 * boxes (`lib/permissionLayout.ts`) — a three-way choice for a page with a view and a change, a switch for a
 * one-key page — the ones the server lets nobody here store drawn disabled with a padlock under ONE legend
 * line, the `never_grantable` and `alias` keys not drawn at all but kept in the saved set. The set is one list
 * (today's keys + the stored page keys); Reset weighs the page part against the role's own (`v2_preset`, or
 * the Admins table's `table_presets`). Nothing here re-derives who may hold what: `grantable`, `reason`,
 * `held` and `v2_gaps` are served.
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
const teamSwitch = () => screen.getByRole('switch', { name: 'admin.nav.reviewers' }) as HTMLButtonElement
/** A page's three-way (named by the sidebar's label) and one of its options. */
const radio = (page: string, level: 'none' | 'view' | 'edit') => within(screen.getByRole('radiogroup', { name: page }))
  .getByRole('radio', { name: `admin.permEditor.level.${level}` }) as HTMLButtonElement
const level = (page: string) => (['none', 'view', 'edit'] as const)
  .find((l) => radio(page, l).getAttribute('aria-checked') === 'true')
const SPONSORS = 'admin.sponsors.nav'
const INVITATIONS = 'admin.nav.invitations'

async function open(view: api.StaffPermissionsView = ADMIN, table?: 'admins' | 'reviewers') {
  mockApi.getStaffPermissions.mockResolvedValue(view)
  render(<PermissionEditor adminId={9} name="Staff One" token="tok" table={table} />)
  await waitFor(() => expect(screen.getByTestId('permission-editor')).toBeTruthy())
}

beforeEach(() => { jest.clearAllMocks(); mockApi.saveStaffPermissions.mockResolvedValue(plan({})) })
afterEach(cleanup)

it('draws each page once, in its box; a locked option with a padlock under one legend; hidden keys not drawn', async () => {
  await open()
  const org = screen.getByTestId('perm-box-organisation')
  expect(within(org).getByText('admin.permLayout.box.organisation')).toBeTruthy()
  expect(within(org).getByRole('radiogroup', { name: INVITATIONS })).toBeTruthy()
  expect(teamSwitch().getAttribute('aria-checked')).toBe('true')
  expect(teamSwitch().disabled).toBe(false)
  expect(level(SPONSORS)).toBe('edit')
  // D4: Invitations' "View and change" is lead_only — that option alone disabled, with a padlock; off (not held).
  expect(level(INVITATIONS)).toBe('view')
  expect(radio(INVITATIONS, 'edit').disabled).toBe(true)
  expect(radio(INVITATIONS, 'view').disabled).toBe(false)
  expect(radio(INVITATIONS, 'none').disabled).toBe(false)
  expect(within(radio(INVITATIONS, 'edit')).getByTestId('perm-padlock')).toBeTruthy()
  expect(screen.getAllByTestId('perm-legend')).toHaveLength(1)
  expect(screen.getByTestId('perm-legend').textContent).toBe('admin.permEditor.notAssignable')
  // D3: never_grantable and alias keys are not drawn; the old key's row stands in (Applications is see_all).
  for (const key of ['billing.edit', 'students.view']) expect(screen.queryByRole('switch', { name: name(key) })).toBeNull()
  expect(screen.queryByText('admin.billing.title')).toBeNull()                 // the row has nothing served
  expect(screen.getByRole('switch', { name: 'admin.scholarship.nav' }).getAttribute('aria-checked')).toBe('true')
  // D6: no Pages heading, no group headings, no reasons, no "Custom".
  for (const gone of [/admin\.permV2\.(title|intro|group|reason)/, /admin\.permEditor\.custom/]) {
    expect(screen.queryAllByText(gone)).toHaveLength(0)
  }
  expect(screen.queryByTestId('perm-other')).toBeNull()                        // every served key is placed
  expect(mockApi.saveStaffPermissions).not.toHaveBeenCalled()
})

it('the three-way sends the right set: View and change, View, then No access', async () => {
  await open({ ...ADMIN, v2_held: ['invitations.view', 'team.view'] })
  const base = [...ADMIN.permissions, 'invitations.view', 'team.view']
  expect(level(SPONSORS)).toBe('none')
  fireEvent.click(radio(SPONSORS, 'edit'))
  expect(level(SPONSORS)).toBe('edit')
  await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenLastCalledWith(9,
    [...base, 'sponsors.view', 'sponsors.edit'], true, { token: 'tok' }))
  fireEvent.click(radio(SPONSORS, 'view'))
  expect(level(SPONSORS)).toBe('view')
  await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenLastCalledWith(9,
    [...base, 'sponsors.view'], true, { token: 'tok' }))
  fireEvent.click(radio(SPONSORS, 'none'))                    // back to the set it holds: nothing to ask
  expect(level(SPONSORS)).toBe('none')
  expect(screen.getByText('admin.permEditor.noChange(name=Staff One)')).toBeTruthy()
  expect(mockApi.saveStaffPermissions).toHaveBeenCalledTimes(2)
})

it('"No access" clears the whole page, and the locked option never moves', async () => {
  await open()
  fireEvent.click(radio(SPONSORS, 'none'))
  await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenLastCalledWith(9,
    [...ADMIN.permissions, 'invitations.view', 'team.view'], true, { token: 'tok' }))
  fireEvent.click(radio(INVITATIONS, 'edit'))                 // disabled: nothing happens
  expect(level(INVITATIONS)).toBe('view')
})

it('hidden keys are never drawn yet still saved as held', async () => {
  await open({ ...ADMIN, v2_held: [...PRESET_V2, 'billing.edit'] })
  expect(screen.queryByRole('switch', { name: name('billing.edit') })).toBeNull()
  fireEvent.click(teamSwitch())
  await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenLastCalledWith(9,
    [...ADMIN.permissions, 'invitations.view', 'sponsors.view', 'sponsors.edit', 'billing.edit'], true, { token: 'tok' }))
})

it('Reset weighs the page part against the role\'s own', async () => {
  await open()
  const reset = () => screen.getByTestId('perm-reset') as HTMLButtonElement
  fireEvent.click(teamSwitch())
  await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenCalled())
  expect(reset().disabled).toBe(false)
  fireEvent.click(reset())
  expect(teamSwitch().getAttribute('aria-checked')).toBe('true')
  expect(screen.getByText('admin.permEditor.reset(preset=admin.role.admin)')).toBeTruthy()
})

it('opened from the Admins table, the served table preset (with its page keys) is the preset', async () => {
  await open(ADMIN, 'admins')
  expect((screen.getByTestId('perm-reset') as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(radio(SPONSORS, 'view'))
  expect((screen.getByTestId('perm-reset') as HTMLButtonElement).disabled).toBe(false)
  await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenCalled())
})

it('opened from the Reviewers table, no page keys are drawn', async () => {
  await open({ ...ADMIN, role: 'reviewer', tables: ['admins', 'reviewers'], permissions: ['review'] }, 'reviewers')
  expect(screen.queryByTestId('perm-section-admins')).toBeNull()
  expect(screen.queryByRole('radiogroup')).toBeNull()
})

it('a save keeps the page keys the server answers with', async () => {
  mockApi.saveStaffPermissions.mockResolvedValue(plan({ dry_run: false, v2_held: ['invitations.view', 'sponsors.view'] }))
  await open()
  fireEvent.click(teamSwitch())
  await waitFor(() => expect((screen.getByText('admin.permEditor.save') as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByText('admin.permEditor.save'))
  await waitFor(() => expect(level(SPONSORS)).toBe('view'))
  expect(teamSwitch().getAttribute('aria-checked')).toBe('false')
})

it('an older api with no page keys draws no page control and sends today\'s keys as before', async () => {
  await open({ ...ADMIN, v2_keys: undefined, v2_held: undefined, v2_preset: undefined })
  expect(screen.queryByRole('radiogroup')).toBeNull()
  expect(screen.queryByTestId('perm-legend')).toBeNull()
  fireEvent.click(screen.getByRole('switch', { name: 'admin.spending.nav' }))
  await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenLastCalledWith(9,
    ['see_all', 'scholars', 'payments_prepare'], true, { token: 'tok' }))
})

describe('D5: the boxes count and collapse', () => {
  it('"N of M on" moves with the working set; a locked control is not counted', async () => {
    await open()
    // Invitations (a three-way, once), Team, Sponsors: three enabled controls, all on.
    expect(screen.getByTestId('perm-box-organisation-count').textContent).toBe('admin.permEditor.boxCount(n=3;m=3)')
    // Applications, Scholars + 2, Payments' 3, Spending: eight; Applications, Scholars, Prepare, Spending on.
    expect(screen.getByTestId('perm-box-programme-count').textContent).toBe('admin.permEditor.boxCount(n=4;m=8)')
    fireEvent.click(teamSwitch())
    fireEvent.click(radio(SPONSORS, 'view'))                  // still on: a three-way is on unless "No access"
    expect(screen.getByTestId('perm-box-organisation-count').textContent).toBe('admin.permEditor.boxCount(n=2;m=3)')
    fireEvent.click(radio(INVITATIONS, 'none'))
    expect(screen.getByTestId('perm-box-organisation-count').textContent).toBe('admin.permEditor.boxCount(n=1;m=3)')
  })

  it('both open on load; collapsing hides the rows and keeps the working set', async () => {
    await open()
    const box = screen.getByTestId('perm-box-organisation')
    const head = within(box).getByRole('button', { expanded: true })
    fireEvent.click(teamSwitch())
    fireEvent.click(head)
    expect(head.getAttribute('aria-expanded')).toBe('false')
    expect(screen.queryByRole('switch', { name: 'admin.nav.reviewers' })).toBeNull()   // hidden rows leave the tree
    expect(screen.getByTestId('perm-box-programme').querySelector('[aria-expanded="true"]')).toBeTruthy()
    fireEvent.click(head)
    expect(teamSwitch().getAttribute('aria-checked')).toBe('false')
    expect(screen.getAllByText('admin.permEditor.changed').length).toBeGreaterThan(0)
  })
})

describe('D7: the Scholars note, as the server tells it', () => {
  const note = () => screen.queryByTestId('perm-scholars-note')

  it('at rest from v2_gaps; while changed from the dry run', async () => {
    mockApi.saveStaffPermissions.mockResolvedValue(plan({ v2_gaps: ['announcements', 'surveys'],
      consequences: ['scholars_needed'] }))
    await open({ ...ADMIN, v2_gaps: ['surveys'] })
    expect(note()?.textContent).toBe('admin.permEditor.scholarsNote(pages=admin.permV2.page.surveys)')
    fireEvent.click(teamSwitch())
    await waitFor(() => expect(note()?.textContent).toBe(
      'admin.permEditor.scholarsNote(pages=admin.permV2.page.announcements, admin.permV2.page.surveys)'))
    // Said once, by the note: the save bar's line does not repeat it (M2d review fix).
    expect(screen.getByRole('status').textContent).not.toContain('scholars_needed')
    expect(screen.getByRole('status').textContent).toContain('admin.permEditor.nothingElse')
    expect((screen.getByText('admin.permEditor.save') as HTMLButtonElement).disabled).toBe(false)   // not a refusal
  })

  it('a change that closes the gap clears it; none served, none shown', async () => {
    mockApi.saveStaffPermissions.mockResolvedValue(plan({ v2_gaps: [] }))
    await open({ ...ADMIN, v2_gaps: ['surveys'] })
    fireEvent.click(teamSwitch())
    await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenCalled())
    await waitFor(() => expect(note()).toBeNull())
    cleanup()
    await open()
    expect(note()).toBeNull()
  })

  it('a fixed card shows no note, no legend and no save bar', async () => {
    // As the server serves a fixed card: each key's `held` says what opens today.
    const asHeld = GROUPS.map((g) => ({ ...g, keys: g.keys.map((x) => ({ ...x, held: x.held || PRESET_V2.includes(x.key) })) }))
    await open({ ...ADMIN, editable: false, v2_gaps: ['surveys'], v2_keys: asHeld })
    expect(note()).toBeNull()
    expect(screen.queryByTestId('perm-legend')).toBeNull()
    expect(screen.queryByTestId('perm-save-bar')).toBeNull()
    expect(radio(SPONSORS, 'view').disabled).toBe(true)
    expect(level(SPONSORS)).toBe('edit')                    // D4: shows what it holds
  })
})

describe('permName: a v2 page key reads "<page>: <level>"', () => {
  it('words both kinds of key', () => {
    expect(name('see_all')).toBe('admin.perm.see_all.name')
    expect(name('sponsors.edit')).toBe(
      'admin.permV2.name(page=admin.permV2.page.sponsors;level=admin.permV2.level.edit)')
  })

  it('has every page and level in all three languages', () => {
    const pages = ['invitations', 'team', 'sources', 'sponsors', 'billing', 'requests', 'settings', 'students',
      'scholars', 'contracts', 'programmes', 'announcements', 'surveys', 'development', 'mentoring', 'payments',
      'spending']
    for (const m of [en, ms, ta]) {
      const v2 = (m as { admin: { permV2: Record<string, Record<string, string> | string> } }).admin.permV2
      expect(Object.keys(v2.page as object).sort()).toEqual([...pages].sort())
      expect(Object.keys(v2.level as object).sort()).toEqual(['approve', 'check', 'edit', 'prepare', 'view'])
      expect(v2.group).toBeUndefined()            // M2d D6: no group headings, no reasons
      expect(v2.reason).toBeUndefined()
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
