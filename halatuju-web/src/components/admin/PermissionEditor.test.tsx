/**
 * @jest-environment jsdom
 *
 * "What <name> can do" — the staff-permission editor (request #39 Sprint 4), against the design of
 * record the owner approved on 2026-10-21: two groups of site Toggles, Quality check bringing See
 * all students (TD-499: it IMPLIES it, as the server says), a "Custom" chip and "changed" markers, a consequence line worded from the SERVER's
 * dry run (never re-derived here), the server's refusal shown as it is, Save and Reset.
 */
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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

const KEYS = ['review', 'see_all', 'qc', 'spending', 'payments_prepare', 'payments_check',
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

const toggle = (key: string) => screen.getByRole('switch', { name: `admin.perm.${key}.name` })
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
  expect(screen.getByText('admin.permEditor.subtitle(preset=admin.role.reviewer)')).toBeTruthy()
  // T3: one section per table she sits in (both, here); the old Students / Money groups are gone.
  const admins = screen.getByTestId('perm-section-admins')
  const reviewers = screen.getByTestId('perm-section-reviewers')
  expect(within(admins).getByText('admin.team.colKeys.admins')).toBeTruthy()
  expect(within(admins).getAllByRole('switch').map((b) => b.getAttribute('aria-label'))).toEqual(
    ['see_all', 'spending', 'payments_prepare', 'payments_check', 'payments_approve', 'award_withdraw_request',
      'award_withdraw_approve'].map((k) => `admin.perm.${k}.name`))
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
  expect(screen.getByText('admin.permEditor.custom')).toBeTruthy()                 // beside the preset
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
  expect(screen.getByText('admin.permEditor.custom')).toBeTruthy()
})

it('resets to the preset in one press', async () => {
  const custom = { ...ROHINI, permissions: ['review', 'spending'], custom: true }
  mockApi.saveStaffPermissions.mockResolvedValue(plan({ removed: ['spending'] }))
  await open(custom)
  expect(screen.getByText('admin.permEditor.custom')).toBeTruthy()
  fireEvent.click(screen.getByText('admin.permEditor.reset(preset=admin.role.reviewer)'))
  expect(isOn('spending')).toBe(false)
  expect(screen.queryByText('admin.permEditor.custom')).toBeNull()
  await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenCalledWith(
    7, ['review'], true, { token: 'tok' }))
})

it('draws no switches for a row nobody edits', async () => {
  mockApi.getStaffPermissions.mockResolvedValue({ ...ROHINI, editable: false })
  render(<PermissionEditor adminId={7} name="Rohini" token="tok" />)
  await waitFor(() => expect(screen.getByText('admin.permEditor.fixed(name=Rohini)')).toBeTruthy())
  expect(screen.queryByRole('switch')).toBeNull()
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
    ] })
    const items = within(screen.getByTestId('permission-history')).getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(items[0].textContent).toContain(
      'admin.permHistory.on(perm=admin.perm.spending.name) · admin.permHistory.off(perm=admin.perm.payments_approve.name)')
    expect(items[0].textContent).toContain(`admin.permHistory.byAt(by=Priya Lead;at=${formatDateTime(AT)})`)
    expect(items[1].textContent).toContain('admin.permHistory.roleReset(role=admin.role.qc)')
    // A super's change names the team, never an address.
    expect(items[1].textContent).toContain('by=admin.permHistory.team')
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
