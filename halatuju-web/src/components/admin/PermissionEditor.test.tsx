/**
 * @jest-environment jsdom
 *
 * "What <name> can do" — the staff-permission editor (request #39 Sprint 4), against the design of
 * record the owner approved on 2026-10-21: two groups of site Toggles, Quality check bringing See
 * all students (TD-499: it IMPLIES it, as the server says), "changed" markers, a consequence line worded from the SERVER's
 * dry run (never re-derived here), the server's refusal shown as it is, Save and Reset.
 * Sprint M2d: the Admins keys sit in the by-page boxes (`lib/permissionLayout.ts`), a page's switch named
 * by the sidebar's label; no "Custom" chip (D6).
 */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import PermissionEditor from './PermissionEditor'
import * as api from '@/lib/admin-api/admins'
import { formatDateTime } from '@/lib/formatDate'
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
const ROHINI: api.StaffPermissionsView = {
  id: 7, name: 'Rohini', role: 'reviewer', is_active: true, editable: true,
  preset: ['review'], permissions: ['review'], custom: false, keys: KEYS,
  // T3: the tables she sits in decide the sections; Rohini (keys in both) sits in both.
  tables: ['admins', 'reviewers'],
}
const plan = (over: Partial<api.StaffPermissionsPlan>): api.StaffPermissionsPlan => ({
  id: 7, role: 'reviewer', dry_run: true, changed: true, permissions: ['review'], custom: false,
  added: [], removed: [], consequences: [], ...over,
})

/** M2d: a page's own switch carries the sidebar's label; a sub-item and a Reviewers key their own words. */
const LABEL: Record<string, string> = {
  see_all: 'admin.scholarship.nav', scholars: 'admin.scholars.nav', spending: 'admin.spending.nav',
}
const label = (key: string) => LABEL[key] ?? `admin.perm.${key}.name`
const toggle = (key: string) => screen.getByRole('switch', { name: label(key) })
const isOn = (key: string) => toggle(key).getAttribute('aria-checked') === 'true'

async function open(view: api.StaffPermissionsView = ROHINI, onSaved = jest.fn()) {
  mockApi.getStaffPermissions.mockResolvedValue(view)
  render(<PermissionEditor adminId={7} name="Rohini" token="tok" onSaved={onSaved} />)
  await waitFor(() => expect(screen.getByTestId('permission-editor')).toBeTruthy())
  return onSaved
}

beforeEach(() => jest.clearAllMocks())

it('shows the two groups of toggles the server serves, from the person\'s current set', async () => {
  await open()
  expect(screen.getByText('admin.permEditor.title(name=Rohini)')).toBeTruthy()
  expect(screen.getByText('admin.permEditor.intro(name=Rohini)')).toBeTruthy()       // M2d D6
  expect(screen.queryByText(/admin\.permEditor\.subtitle/)).toBeNull()
  // T3: one section per table she sits in (both, here); the old Students / Money groups are gone.
  const admins = screen.getByTestId('perm-section-admins')
  const reviewers = screen.getByTestId('perm-section-reviewers')
  expect(within(admins).getByText('admin.permLayout.box.organisation')).toBeTruthy()
  expect(within(admins).getByText('admin.permLayout.box.programme')).toBeTruthy()
  // M2d: in sidebar order — Applications, Scholars (and its withdrawals), Payments' three, Spending.
  expect(within(admins).getAllByRole('switch').map((b) => b.getAttribute('aria-label'))).toEqual(
    ['see_all', 'scholars', 'award_withdraw_request', 'award_withdraw_approve', 'payments_prepare',
      'payments_check', 'payments_approve', 'spending'].map(label))
  expect(within(reviewers).getAllByRole('switch').map((b) => b.getAttribute('aria-label'))).toEqual(
    ['admin.perm.review.name', 'admin.perm.qc.name'])
  expect(screen.queryByText('admin.permEditor.students')).toBeNull()
  expect(screen.queryByText('admin.permEditor.money')).toBeNull()
  expect(screen.getAllByRole('switch')).toHaveLength(KEYS.length)       // toggles, never checkboxes
  expect(screen.queryByRole('checkbox')).toBeNull()
  expect(isOn('review')).toBe(true)
  expect(isOn('spending')).toBe(false)
  expect(screen.queryByText('admin.permEditor.custom')).toBeNull()
  expect(screen.getByText('admin.permEditor.noChange(name=Rohini)')).toBeTruthy()
  expect(screen.getByText('admin.permEditor.footnote')).toBeTruthy()
  expect(mockApi.saveStaffPermissions).not.toHaveBeenCalled()          // nothing changed, nothing asked
})

describe('TD-499: Quality check IMPLIES See all students (the server rule since T5b)', () => {
  it('allows Quality check without See all students, and brings it along', async () => {
    mockApi.saveStaffPermissions.mockResolvedValue(plan({}))
    await open()
    expect((toggle('qc') as HTMLButtonElement).disabled).toBe(false)
    expect(isOn('see_all')).toBe(false)
    fireEvent.click(toggle('qc'))
    expect(isOn('qc')).toBe(true)
    expect(isOn('see_all')).toBe(true)
    await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenLastCalledWith(
      7, ['review', 'qc', 'see_all'], true, { token: 'tok' }))
  })

  it('refuses to switch See all students off while Quality check is on (locked), and never strips Quality check', async () => {
    await open({ ...ROHINI, permissions: ['review', 'see_all', 'qc'] })
    expect((toggle('see_all') as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(toggle('see_all'))
    expect(isOn('see_all')).toBe(true)
    expect(isOn('qc')).toBe(true)
    expect(mockApi.saveStaffPermissions).not.toHaveBeenCalled()
  })

  it('unlocks See all students once Quality check is off, and leaves it as it was in Admins', async () => {
    mockApi.saveStaffPermissions.mockResolvedValue(plan({}))
    await open({ ...ROHINI, permissions: ['review', 'see_all', 'qc'] })
    fireEvent.click(toggle('qc'))
    expect(isOn('qc')).toBe(false)
    expect(isOn('see_all')).toBe(true)
    expect((toggle('see_all') as HTMLButtonElement).disabled).toBe(false)
    await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenLastCalledWith(
      7, ['review', 'see_all'], true, { token: 'tok' }))
  })
})

it('asks the server for a dry run and words the line from its answer (Rohini\'s Spending)', async () => {
  mockApi.saveStaffPermissions.mockResolvedValue(
    plan({ permissions: ['review', 'spending'], custom: true, added: ['spending'] }))
  await open()
  fireEvent.click(toggle('spending'))
  expect(mockApi.saveStaffPermissions).toHaveBeenCalledWith(7, ['review', 'spending'], true,
    { token: 'tok' })
  await waitFor(() => expect(screen.getByRole('status').textContent).toBe(
    'admin.permEditor.gives(name=Rohini;list=“admin.perm.spending.name”) admin.permEditor.nothingElse'))
  expect(screen.queryByText('admin.permEditor.custom')).toBeNull()                 // M2d D6: no chip
  expect(screen.getAllByText('admin.permEditor.changed')).toHaveLength(1)          // one row moved
})

it('names every consequence the server returns, and what is taken away', async () => {
  const fin = { ...ROHINI, name: 'Suresh', role: 'finance', preset: ['payments_approve'],
                permissions: ['payments_approve'] }
  mockApi.saveStaffPermissions.mockResolvedValue(plan({
    added: ['review'], removed: ['payments_approve'],
    consequences: ['approver_fallback_on', 'files_widened_assigned'],
  }))
  await open(fin)
  fireEvent.click(toggle('payments_approve'))
  const line = await screen.findByRole('status')
  await waitFor(() => expect(line.textContent).toContain('admin.permEditor.effect.approver_fallback_on'))
  expect(line.textContent).toContain('admin.permEditor.takes(name=Suresh;list=“admin.perm.payments_approve.name”)')
  expect(line.textContent).toContain('admin.permEditor.effect.files_widened_assigned(name=Suresh)')
  expect(line.textContent).not.toContain('admin.permEditor.nothingElse')
})

it('says the withdrawal approve seat needs every case, in all three languages', async () => {
  // A1.13b review fix: the server names `withdraw_approve_needs_view`; the line is worded per locale.
  const fin = { ...ROHINI, name: 'Suresh', role: 'finance', preset: ['payments_approve'],
                permissions: ['payments_approve'] }
  mockApi.saveStaffPermissions.mockResolvedValue(plan({
    added: ['award_withdraw_approve'], consequences: ['withdraw_approve_needs_view'],
  }))
  await open(fin)
  fireEvent.click(toggle('award_withdraw_approve'))
  const line = await screen.findByRole('status')
  await waitFor(() => expect(line.textContent).toContain(
    'admin.permEditor.effect.withdraw_approve_needs_view(name=Suresh)'))
  for (const messages of [en, ms, ta]) {
    const said = (messages as { admin: { permEditor: { effect: Record<string, string> } } })
      .admin.permEditor.effect.withdraw_approve_needs_view
    expect(said).toContain('{name}')
  }
  expect(en.admin.permEditor.effect.withdraw_approve_needs_view).toBe(
    '{name} can approve award withdrawals only if they can also see all cases. Give them that too, or they cannot decide.')
})

it('shows the server\'s refusal as it is and will not save', async () => {
  const err = Object.assign(new Error('Rohini has 2 open case(s) assigned.'), { code: 'has_open_cases' })
  mockApi.saveStaffPermissions.mockRejectedValue(err)
  await open()
  fireEvent.click(toggle('review'))
  await waitFor(() => expect(screen.getByRole('alert').textContent)
    .toBe('Rohini has 2 open case(s) assigned.'))
  expect((screen.getByText('admin.permEditor.save') as HTMLButtonElement).disabled).toBe(true)
})

it('saves for real, tells the page, and says it is done', async () => {
  mockApi.saveStaffPermissions
    .mockResolvedValueOnce(plan({ added: ['spending'], permissions: ['review', 'spending'] }))
    .mockResolvedValueOnce(plan({ dry_run: false, added: ['spending'],
                                  permissions: ['review', 'spending'], custom: true }))
  const onSaved = await open()
  fireEvent.click(toggle('spending'))
  const save = screen.getByText('admin.permEditor.save') as HTMLButtonElement
  await waitFor(() => expect(save.disabled).toBe(false))
  await act(async () => { fireEvent.click(save) })
  expect(mockApi.saveStaffPermissions).toHaveBeenLastCalledWith(7, ['review', 'spending'], false,
    { token: 'tok' })
  expect(onSaved).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('status').textContent).toBe('admin.permEditor.saved(name=Rohini)')
  expect(screen.queryByText('admin.permEditor.changed')).toBeNull()      // the new set is the baseline
})

it('resets to the preset in one press', async () => {
  const custom = { ...ROHINI, permissions: ['review', 'spending'], custom: true }
  mockApi.saveStaffPermissions.mockResolvedValue(plan({ removed: ['spending'] }))
  await open(custom)
  fireEvent.click(screen.getByText('admin.permEditor.reset(preset=admin.role.reviewer)'))
  expect(isOn('spending')).toBe(false)
  await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenCalledWith(
    7, ['review'], true, { token: 'tok' }))
})

// Sprint T3 (M2, owner 2026-11-09) REVERSES "no switches for a row nobody edits": an organisation admin's
// (or your own) set reads as LOCKED switches under one line — what they hold is visible, nothing moves.
it('M2: shows a row nobody edits as locked switches under one line — no Save, no Reset, no dry run', async () => {
  mockApi.getStaffPermissions.mockResolvedValue({ ...ROHINI, editable: false, permissions: ['review', 'see_all'] })
  render(<PermissionEditor adminId={7} name="Rohini" token="tok" />)
  await waitFor(() => expect(screen.getByTestId('perm-fixed').textContent).toBe('admin.permEditor.fixed(name=Rohini)'))
  expect(screen.getAllByRole('switch')).toHaveLength(KEYS.length)
  for (const b of screen.getAllByRole('switch')) expect((b as HTMLButtonElement).disabled).toBe(true)
  expect(isOn('review')).toBe(true)
  expect(isOn('see_all')).toBe(true)
  expect(isOn('spending')).toBe(false)
  fireEvent.click(toggle('spending'))
  expect(isOn('spending')).toBe(false)
  expect(mockApi.saveStaffPermissions).not.toHaveBeenCalled()
  expect(screen.queryByTestId('perm-reset')).toBeNull()
  expect(screen.queryByText('admin.permEditor.save')).toBeNull()
  expect(screen.queryByText('admin.permEditor.footnote')).toBeNull()
  expect(screen.queryByText('admin.permEditor.noChange(name=Rohini)')).toBeNull()
})

it('drops the old preview the moment a new dry run starts, so Save cannot act on it (fix 9)', async () => {
  let answer: (p: api.StaffPermissionsPlan) => void = () => {}
  mockApi.saveStaffPermissions
    .mockResolvedValueOnce(plan({ added: ['spending'], permissions: ['review', 'spending'] }))
    .mockImplementationOnce(() => new Promise((res) => { answer = res }))
  await open()
  fireEvent.click(toggle('spending'))
  const save = screen.getByText('admin.permEditor.save') as HTMLButtonElement
  await waitFor(() => expect(save.disabled).toBe(false))
  fireEvent.click(toggle('see_all'))                        // a second change, its answer pending
  expect(save.disabled).toBe(true)
  await act(async () => { answer(plan({ added: ['see_all', 'spending'] })) })
  expect(save.disabled).toBe(false)
})

it('warns that a Reviewer holding neither Review nor Quality check would leave People (fix 1)', async () => {
  mockApi.saveStaffPermissions.mockResolvedValue(plan({}))
  await open()
  expect(screen.queryByTestId('unlisted-hint')).toBeNull()
  fireEvent.click(toggle('review'))
  expect(screen.getByTestId('unlisted-hint').textContent).toBe('admin.permEditor.unlistedHint')
})

it('tells a revoked person\'s admin to restore them first, with no switches (fix 8)', async () => {
  mockApi.getStaffPermissions.mockResolvedValue({ ...ROHINI, editable: false, is_active: false })
  render(<PermissionEditor adminId={7} name="Rohini" token="tok" />)
  await waitFor(() => expect(screen.getByText('admin.permEditor.restoreFirst(name=Rohini)')).toBeTruthy())
  expect(screen.queryByRole('switch')).toBeNull()
})

it('says so when the permissions cannot be loaded', async () => {
  mockApi.getStaffPermissions.mockRejectedValue(new Error('404'))
  render(<PermissionEditor adminId={7} name="Rohini" token="tok" />)
  await waitFor(() => expect(screen.getByText('admin.permEditor.loadFailed(name=Rohini)')).toBeTruthy())
})

// ── Changes (2026-10-22): the history under the card, from the SAME GET ─────────────────────────
const AT = '2026-10-20T09:15:00Z'
const change = (over: Partial<api.StaffPermissionChangeRow>): api.StaffPermissionChangeRow => ({
  kind: 'edit', role: 'reviewer', before: ['review'], after: ['review'], added: [], removed: [],
  at: AT, by: 'Priya Lead', by_super: false, ...over,
})

describe('Changes', () => {
  it('words each change in plain terms, newest first as served, with who and when', async () => {
    await open({ ...ROHINI, history: [
      change({ added: ['spending'], removed: ['payments_approve'] }),
      change({ kind: 'role_change', role: 'qc', by: '', by_super: true }),
      change({ added: ['scholars'], by: '', by_migration: true }),
    ] })
    const items = within(screen.getByTestId('permission-history')).getAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(items[0].textContent).toContain(
      'admin.permHistory.on(perm=admin.perm.spending.name) · admin.permHistory.off(perm=admin.perm.payments_approve.name)')
    expect(items[0].textContent).toContain(`admin.permHistory.byAt(by=Priya Lead;at=${formatDateTime(AT)})`)
    expect(items[1].textContent).toContain('admin.permHistory.roleReset(role=admin.role.qc)')
    // A super's change names the team, never an address.
    expect(items[1].textContent).toContain('by=admin.permHistory.team')
    // A data migration's change (sprint S1) says so, never a blank "by".
    expect(items[2].textContent).toContain('by=admin.permHistory.migration')
  })

  it('M2d D9: more than three keys read as a summary, with Show / Hide for the full list', async () => {
    const on = ['spending', 'scholars', 'team.view', 'sponsors.view']
    await open({ ...ROHINI, history: [
      change({ added: on, removed: ['payments_approve'] }),
      change({ added: ['spending', 'scholars'], removed: ['qc'] }),            // three: inline as before
      change({ kind: 'role_change', role: 'qc' }),
    ] })
    const items = within(screen.getByTestId('permission-history')).getAllByRole('listitem')
    expect(items[0].textContent).toContain('admin.permHistory.countOn(n=4) · admin.permHistory.countOff(n=1)')
    expect(within(items[0]).queryByTestId('perm-history-full')).toBeNull()
    const show = within(items[0]).getByRole('button', { name: 'admin.permHistory.show' })
    expect(show.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(show)
    expect(show.getAttribute('aria-expanded')).toBe('true')
    expect(show.textContent).toBe('admin.permHistory.hide')
    const full = within(items[0]).getByTestId('perm-history-full').textContent ?? ''
    expect(full).toContain('admin.permHistory.on(perm=admin.perm.spending.name)')
    expect(full).toContain('admin.permHistory.off(perm=admin.perm.payments_approve.name)')
    expect(full.split(' · ')).toHaveLength(5)
    fireEvent.click(show)
    expect(within(items[0]).queryByTestId('perm-history-full')).toBeNull()
    expect(within(items[1]).queryByRole('button')).toBeNull()
    expect(items[1].textContent).toContain('admin.permHistory.off(perm=admin.perm.qc.name)')
    expect(within(items[2]).queryByRole('button')).toBeNull()                 // a role reset reads as one
    expect(items[2].textContent).toContain('admin.permHistory.roleReset(role=admin.role.qc)')
  })

  it('says there is nothing yet, naming the set the person holds', async () => {
    await open()                                      // an older api: no `history` at all
    expect(screen.getByText('admin.permHistory.empty(name=Rohini;role=admin.role.reviewer)')).toBeTruthy()
  })

  it('re-reads the list after a save, so the new line appears', async () => {
    mockApi.saveStaffPermissions
      .mockResolvedValueOnce(plan({ added: ['spending'], permissions: ['review', 'spending'] }))
      .mockResolvedValueOnce(plan({ dry_run: false, added: ['spending'],
                                    permissions: ['review', 'spending'], custom: true }))
    await open()
    mockApi.getStaffPermissions.mockResolvedValue({ ...ROHINI, history: [change({ added: ['spending'] })] })
    fireEvent.click(toggle('spending'))
    const save = screen.getByText('admin.permEditor.save') as HTMLButtonElement
    await waitFor(() => expect(save.disabled).toBe(false))
    await act(async () => { fireEvent.click(save) })
    await waitFor(() => expect(screen.getByText('admin.permHistory.on(perm=admin.perm.spending.name)'))
      .toBeTruthy())
    expect(mockApi.getStaffPermissions).toHaveBeenCalledTimes(2)
  })

  it('uses the page\'s own GET when it is handed one, and asks nothing more', async () => {
    render(<PermissionEditor adminId={7} name="Rohini" token="tok"
      initial={{ ...ROHINI, history: [change({ added: ['spending'] })] }} />)
    expect(screen.getByTestId('permission-editor')).toBeTruthy()
    expect(screen.getByText('admin.permHistory.on(perm=admin.perm.spending.name)')).toBeTruthy()
    expect(mockApi.getStaffPermissions).not.toHaveBeenCalled()
  })

  it('still shows a revoked person\'s history under the "restore first" line', async () => {
    mockApi.getStaffPermissions.mockResolvedValue({ ...ROHINI, editable: false, is_active: false,
      history: [change({ added: ['spending'] })] })
    render(<PermissionEditor adminId={7} name="Rohini" token="tok" />)
    await waitFor(() => expect(screen.getByTestId('permission-history')).toBeTruthy())
    expect(screen.getByText('admin.permHistory.on(perm=admin.perm.spending.name)')).toBeTruthy()
  })
})

describe('Team tables T3: one section per table (owner, 2026-11-03)', () => {
  const REVIEWER_ONLY = { ...ROHINI, tables: ['reviewers'] }

  it('a Reviewer only: the Reviewer section alone — no See all students, no money switches', async () => {
    await open(REVIEWER_ONLY)
    expect(screen.queryByTestId('perm-section-admins')).toBeNull()
    expect(screen.getAllByRole('switch').map((b) => b.getAttribute('aria-label')))
      .toEqual(['admin.perm.review.name', 'admin.perm.qc.name'])
  })

  it('an Admin only: the Admin section alone', async () => {
    await open({ ...ROHINI, role: 'admin', preset: ['see_all', 'spending', 'payments_prepare'],
      permissions: ['see_all', 'spending', 'payments_prepare'], tables: ['admins'] })
    expect(screen.queryByTestId('perm-section-reviewers')).toBeNull()
    expect(screen.queryByRole('switch', { name: 'admin.perm.review.name' })).toBeNull()
    expect(screen.getByTestId('perm-section-admins')).toBeTruthy()
  })

  it('Quality check for a Reviewer only says it needs the Admin permission, and brings See all students', async () => {
    mockApi.saveStaffPermissions.mockResolvedValue(plan({}))
    await open(REVIEWER_ONLY)
    expect((toggle('qc') as HTMLButtonElement).disabled).toBe(false)
    expect(screen.getByTestId('qc-brings-see-all').textContent).toBe('admin.permEditor.qcBrings')
    fireEvent.click(toggle('qc'))
    await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenLastCalledWith(
      7, ['review', 'qc', 'see_all'], true, { token: 'tok' }))
  })

  it('NEVER drops a key held outside the sections on screen', async () => {
    mockApi.saveStaffPermissions.mockResolvedValue(plan({}))
    // A QC reviewer: See all students is Quality check's need, held but not shown (not in Admins).
    await open({ ...REVIEWER_ONLY, role: 'qc', preset: ['see_all', 'qc'], permissions: ['review', 'see_all', 'qc'] })
    fireEvent.click(toggle('review'))
    await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenLastCalledWith(
      7, ['see_all', 'qc'], true, { token: 'tok' }))
    jest.clearAllMocks()
    // Any other key the screen does not show rides along too, through the dry run AND the save.
    mockApi.saveStaffPermissions.mockResolvedValue(plan({ permissions: ['review', 'spending', 'qc', 'see_all'] }))
    document.body.innerHTML = ''
    await open({ ...REVIEWER_ONLY, permissions: ['review', 'spending'] })
    fireEvent.click(toggle('qc'))
    await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenLastCalledWith(
      7, ['review', 'spending', 'qc', 'see_all'], true, { token: 'tok' }))
    fireEvent.click(await screen.findByText('admin.permEditor.save'))
    await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenLastCalledWith(
      7, ['review', 'spending', 'qc', 'see_all'], false, { token: 'tok' }))
  })

  it('in both tables, Quality check is never held back, and says it brings See all students (TD-499)', async () => {
    await open()
    expect((toggle('qc') as HTMLButtonElement).disabled).toBe(false)
    expect(screen.getByTestId('qc-brings-see-all').textContent).toBe('admin.permEditor.qcBrings')
  })
})

describe('T3 review: no Reset for somebody sitting in no table', () => {
  it('hides Reset when tables is empty, and shows it otherwise', async () => {
    await open({ ...ROHINI, tables: [] })
    expect(screen.queryByTestId('perm-reset')).toBeNull()
    document.body.innerHTML = ''
    await open(ROHINI)
    expect(screen.getByTestId('perm-reset')).toBeTruthy()
  })
})

describe('M1b (owner O12): opened from one table, the card draws that table only', () => {
  // Rohini sits in both tables; Admin preset is empty, Reviewer preset is Review.
  const BOTH: api.StaffPermissionsView = {
    ...ROHINI, permissions: ['review', 'spending'], preset: ['review'], custom: true,
    table_presets: { admins: [], reviewers: ['review'] },
  }
  async function openFrom(table: 'admins' | 'reviewers', view: api.StaffPermissionsView = BOTH) {
    mockApi.getStaffPermissions.mockResolvedValue(view)
    render(<PermissionEditor adminId={7} name="Rohini" token="tok" table={table} />)
    await waitFor(() => expect(screen.getByTestId('permission-editor')).toBeTruthy())
  }

  it('from Admins: only the Admin section, no role chip', async () => {
    await openFrom('admins')
    expect(screen.getByTestId('perm-section-admins')).toBeTruthy()
    expect(screen.queryByTestId('perm-section-reviewers')).toBeNull()
    expect(screen.queryByRole('switch', { name: 'admin.perm.review.name' })).toBeNull()
    // The grey role chip is gone; the role is named only in the subtitle.
    expect(screen.queryByText('admin.role.reviewer')).toBeNull()
  })

  it('from Reviewers: only the Reviewer section', async () => {
    await openFrom('reviewers')
    expect(screen.getByTestId('perm-section-reviewers')).toBeTruthy()
    expect(screen.queryByTestId('perm-section-admins')).toBeNull()
  })

  it('Reset weighs that table\'s keys against table_presets[table] (M2d: no chip, Reset alone)', async () => {
    const reset = () => screen.getByTestId('perm-reset') as HTMLButtonElement
    await openFrom('reviewers')        // reviewer keys ['review'] = preset ['review'] -> nothing to undo
    expect(reset().disabled).toBe(true)
    cleanup()
    await openFrom('admins')           // admin keys ['spending'] vs preset [] -> Reset has work
    expect(reset().disabled).toBe(false)
    expect(screen.queryByText('admin.permEditor.custom')).toBeNull()
  })

  it('saving never drops the keys of the hidden section', async () => {
    mockApi.saveStaffPermissions.mockResolvedValue(plan({ permissions: ['review', 'spending', 'payments_check'] }))
    await openFrom('admins')
    fireEvent.click(toggle('payments_check'))
    await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenCalledTimes(1))
    expect(mockApi.saveStaffPermissions.mock.calls[0][1]).toEqual(['review', 'spending', 'payments_check'])
    const save = screen.getByText('admin.permEditor.save') as HTMLButtonElement
    await waitFor(() => expect(save.disabled).toBe(false))
    await act(async () => { fireEvent.click(save) })
    const [, sent, dry] = mockApi.saveStaffPermissions.mock.calls[1]
    expect(dry).toBe(false)
    expect(sent).toEqual(expect.arrayContaining(['review']))       // the hidden Reviewer key rides along
    expect(sent).toHaveLength(3)
  })

  it('Reset restores this table\'s preset and keeps the other table\'s keys', async () => {
    mockApi.saveStaffPermissions.mockResolvedValue(plan({}))
    await openFrom('admins')
    fireEvent.click(screen.getByTestId('perm-reset'))
    await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenCalled())
    expect(mockApi.saveStaffPermissions.mock.calls[0][1]).toEqual(['review'])   // spending off, review kept
  })

  it('from Reviewers, turning Quality check off keeps Applications for someone seated at Admins', async () => {
    mockApi.saveStaffPermissions.mockResolvedValue(plan({}))
    await openFrom('reviewers', { ...BOTH, permissions: ['review', 'qc', 'see_all'] })
    fireEvent.click(toggle('qc'))
    await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenCalled())
    expect(mockApi.saveStaffPermissions.mock.calls[0][1]).toEqual(['review', 'see_all'])
  })
})
