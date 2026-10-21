/**
 * @jest-environment jsdom
 *
 * "What <name> can do" — the staff-permission editor (request #39 Sprint 4), against the design of
 * record the owner approved on 2026-10-21: two groups of site Toggles, Quality check held behind See
 * all students, a "Custom" chip and "changed" markers, a consequence line worded from the SERVER's
 * dry run (never re-derived here), the server's refusal shown as it is, Save and Reset.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import PermissionEditor from './PermissionEditor'
import * as api from '@/lib/admin-api/admins'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({
    t: (k: string, p?: Record<string, string>) =>
      p ? `${k}(${Object.entries(p).map(([a, b]) => `${a}=${b}`).join(';')})` : k,
  }),
}))
jest.mock('@/lib/admin-api/admins')
const mockApi = api as jest.Mocked<typeof api>

const KEYS = ['review', 'see_all', 'qc', 'spending', 'payments_prepare', 'payments_check',
  'payments_approve']
const ROHINI: api.StaffPermissionsView = {
  id: 7, name: 'Rohini', role: 'reviewer', is_active: true, editable: true,
  preset: ['review'], permissions: ['review'], custom: false, keys: KEYS,
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
  expect(screen.getByText('admin.permEditor.students')).toBeTruthy()
  expect(screen.getByText('admin.permEditor.money')).toBeTruthy()
  expect(screen.getAllByRole('switch')).toHaveLength(KEYS.length)       // toggles, never checkboxes
  expect(screen.queryByRole('checkbox')).toBeNull()
  expect(isOn('review')).toBe(true)
  expect(isOn('spending')).toBe(false)
  expect(screen.queryByText('admin.permEditor.custom')).toBeNull()
  expect(screen.getByText('admin.permEditor.noChange(name=Rohini)')).toBeTruthy()
  expect(screen.getByText('admin.permEditor.footnote')).toBeTruthy()
  expect(mockApi.saveStaffPermissions).not.toHaveBeenCalled()          // nothing changed, nothing asked
})

it('holds Quality check until See all students is on, and drops it when See all goes', async () => {
  mockApi.saveStaffPermissions.mockResolvedValue(plan({}))
  await open()
  expect((toggle('qc') as HTMLButtonElement).disabled).toBe(true)
  expect(screen.getByText('admin.permEditor.qcHint')).toBeTruthy()
  fireEvent.click(toggle('see_all'))
  expect((toggle('qc') as HTMLButtonElement).disabled).toBe(false)
  fireEvent.click(toggle('qc'))
  expect(isOn('qc')).toBe(true)
  await waitFor(() => expect(mockApi.saveStaffPermissions).toHaveBeenLastCalledWith(
    7, ['review', 'see_all', 'qc'], true, { token: 'tok' }))
  const asked = mockApi.saveStaffPermissions.mock.calls.length
  fireEvent.click(toggle('see_all'))
  expect(isOn('qc')).toBe(false)
  // Back to the set she holds: nothing to ask the server, and the line says so.
  expect(screen.getByText('admin.permEditor.noChange(name=Rohini)')).toBeTruthy()
  expect(mockApi.saveStaffPermissions).toHaveBeenCalledTimes(asked)
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
