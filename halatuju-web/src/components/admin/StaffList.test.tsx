/**
 * @jest-environment jsdom
 *
 * Sprint M1b: Team -> Staff (owner O3, O7, O16, O17, O18). One row per accepted member with their group
 * chips ("No group" when none); Suspend / Restore and Delete live HERE only. These pin what the screen
 * promises — including what must never be on it (a phone, an email) and what must be refused before the
 * click (Suspend while they mentor scholars, Delete while work is unfinished).
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import StaffList, { unfinishedReason } from './StaffList'
import * as api from '@/lib/admin-api'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k) }),
}))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const NO_WORK = { admins: {}, reviewers: { open_cases: 0 }, mentors: { scholars_now: 0 } }
const row = (over: Partial<api.StaffRow> = {}): api.StaffRow => ({
  id: 1, kind: 'staff', mentor_id: null, name: 'Aruna Example', photo_url: null, last_seen_at: null,
  groups: ['admins'], lead: false, suspended: false, manageable: true, work: NO_WORK, deletable: true,
  delete_never: null, delete_outcome: 'erase', revocable: true, ...over,
})

/** A mixed team: an Admin, a reviewer with open cases, a mentor login with scholars, somebody in No group,
 *  a suspended reviewer, the sole organisation admin, and the viewer themselves. */
const TEAM: api.StaffRow[] = [
  row({ id: 1, name: 'Aruna Example', groups: ['admins'], delete_outcome: 'erase' }),
  row({ id: 2, name: 'Bala Example', groups: ['reviewers'], deletable: false, delete_never: 'has_unfinished_work',
    delete_outcome: 'archive', work: { ...NO_WORK, reviewers: { open_cases: 4 } } }),
  row({ id: 3, kind: 'mentor', mentor_id: 30, name: 'Chitra Example', groups: ['mentors'], deletable: false,
    delete_never: 'has_unfinished_work', work: { ...NO_WORK, mentors: { scholars_now: 2 } } }),
  row({ id: 4, name: 'Devi Example', groups: [], delete_outcome: 'archive' }),
  row({ id: 5, name: 'Elan Example', groups: ['reviewers'], suspended: true }),
  row({ id: 6, name: 'Farah Example', groups: ['admins', 'reviewers'], lead: true, manageable: false,
    revocable: false, deletable: false, delete_never: 'sole_org_admin' }),
  row({ id: 7, name: 'Gita Example', groups: ['admins'], manageable: false, revocable: false, deletable: false,
    delete_never: 'self' }),
]

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getStaffList.mockResolvedValue({ staff: TEAM })
  window.confirm = jest.fn(() => true)
})

const draw = async (props: Partial<React.ComponentProps<typeof StaffList>> = {}) => {
  render(<StaffList token="tok" canManage viewerSuper={false} {...props} />)
  await waitFor(() => expect(screen.getByTestId('staff-list')).toBeTruthy())
}
const line = (id: number) => within(screen.getByTestId(`staff-row-${id}`))

describe('the rows', () => {
  it('lists every accepted member once, with their group chips — "No group" when they sit in none', async () => {
    await draw()
    expect(mockApi.getStaffList).toHaveBeenCalledWith({ token: 'tok' })
    for (const r of TEAM) expect(screen.getByTestId(`staff-row-${r.id}`)).toBeTruthy()
    expect(line(1).getByTestId('staff-groups-1')).toBeTruthy()
    expect(line(4).getByTestId('staff-no-group-4').textContent).toBe('admin.staff.noGroup')
    expect(line(1).queryByTestId('staff-no-group-1')).toBeNull()
    expect(line(5).getByText('admin.staff.statusSuspended')).toBeTruthy()
    expect(line(1).getByText('admin.staff.statusActive')).toBeTruthy()
  })

  it('⚠ O16: shows no phone and no email, even when an older payload carries them', async () => {
    mockApi.getStaffList.mockResolvedValue({ staff: [
      { ...row(), phone: '012-345 6789', email: 'aruna@example.test' } as unknown as api.StaffRow] })
    await draw()
    expect(document.body.textContent).not.toContain('012-345 6789')
    expect(document.body.textContent).not.toContain('aruna@example.test')
    expect(document.querySelector('[data-testid^="team-phone-"]')).toBeNull()
  })

  it('links a manager to the person page (a mentor login by its Mentors record), never a suspended row', async () => {
    await draw()
    expect(line(1).getByText('Aruna Example').closest('a')!.getAttribute('href'))
      .toBe('/admin/organisation/reviewers/admins/1')
    expect(line(3).getByText('Chitra Example').closest('a')!.getAttribute('href'))
      .toBe('/admin/organisation/reviewers/mentors/30')
    expect(line(5).getByText('Elan Example').closest('a')).toBeNull()
    expect(line(4).getByText('Devi Example').closest('a')).toBeNull()      // No group: no group page
  })

  it('a reader who may not manage gets the list with no links and no actions', async () => {
    await draw({ canManage: false })
    expect(screen.getByText('Aruna Example').closest('a')).toBeNull()
    expect(screen.queryByText('admin.staff.suspend')).toBeNull()
    expect(screen.queryByText('admin.delete')).toBeNull()
  })

  it('says so when the list cannot load, and when it is empty', async () => {
    mockApi.getStaffList.mockRejectedValueOnce(new Error('boom'))
    const { unmount } = render(<StaffList token="tok" canManage viewerSuper={false} />)
    expect((await screen.findByRole('alert')).textContent).toBe('admin.staff.loadFailed')
    unmount()
    mockApi.getStaffList.mockResolvedValueOnce({ staff: [] })
    render(<StaffList token="tok" canManage viewerSuper={false} />)
    expect(await screen.findByText('admin.staff.empty')).toBeTruthy()
  })
})

describe('Suspend / Restore (O3, O18)', () => {
  it('suspends a staff row through admin/admins after asking, then reads the list again', async () => {
    mockApi.revokeAdmin.mockResolvedValue({})
    const onChanged = jest.fn()
    await draw({ onChanged })
    fireEvent.click(screen.getByTestId('staff-toggle-1'))
    expect((window.confirm as jest.Mock).mock.calls[0][0]).toBe('admin.staff.suspendConfirm {"name":"Aruna Example"}')
    await waitFor(() => expect(mockApi.revokeAdmin).toHaveBeenCalledWith(1, 'revoke', { token: 'tok' }))
    await waitFor(() => expect(mockApi.getStaffList).toHaveBeenCalledTimes(2))
    expect(onChanged).toHaveBeenCalled()
    expect(await screen.findByText('admin.staff.suspended {"name":"Aruna Example"}')).toBeTruthy()
  })

  it('restores a suspended row', async () => {
    mockApi.revokeAdmin.mockResolvedValue({})
    await draw()
    expect(line(5).getByText('admin.restore')).toBeTruthy()
    fireEvent.click(screen.getByTestId('staff-toggle-5'))
    await waitFor(() => expect(mockApi.revokeAdmin).toHaveBeenCalledWith(5, 'restore', { token: 'tok' }))
  })

  it('asks nothing of the server when the confirm is declined', async () => {
    window.confirm = jest.fn(() => false)
    await draw()
    fireEvent.click(screen.getByTestId('staff-toggle-1'))
    expect(mockApi.revokeAdmin).not.toHaveBeenCalled()
  })

  it('O18: greys Suspend on somebody who still mentors scholars, the reason and count in its tip', async () => {
    await draw()
    expect(screen.queryByTestId('staff-toggle-3')).toBeNull()
    const b = within(line(3).getByTestId('staff-toggle-3-greyed')).getByText('admin.staff.suspend')
    expect(b.getAttribute('aria-disabled')).toBe('true')
    expect(document.getElementById(b.getAttribute('aria-describedby')!)!.textContent)
      .toBe('admin.refusal.has_scholars.many {"n":"2"}')
    fireEvent.click(b)
    expect(mockApi.mentorAction).not.toHaveBeenCalled()
  })

  it('a mentor login with no scholars is suspended through its Mentors record (`deactivate`)', async () => {
    mockApi.getStaffList.mockResolvedValue({ staff: [row({ id: 3, kind: 'mentor', mentor_id: 30, groups: ['mentors'] })] })
    mockApi.mentorAction.mockResolvedValue({} as never)
    await draw()
    fireEvent.click(screen.getByTestId('staff-toggle-3'))
    await waitFor(() => expect(mockApi.mentorAction).toHaveBeenCalledWith(30, 'deactivate', { token: 'tok' }))
    expect(mockApi.revokeAdmin).not.toHaveBeenCalled()
  })

  it('a refusal reads in the reader\'s words, not the server\'s sentence', async () => {
    mockApi.revokeAdmin.mockRejectedValue(Object.assign(new Error('Server sentence in English.'),
      { status: 409, code: 'has_scholars', body: { code: 'has_scholars', scholars_now: 1 } }))
    await draw()
    fireEvent.click(screen.getByTestId('staff-toggle-1'))
    expect(await screen.findByText('admin.refusal.has_scholars.one {"n":"1"}')).toBeTruthy()
    expect(screen.queryByText('Server sentence in English.')).toBeNull()
  })

  it('the sole organisation admin and yourself: no Suspend and no Delete at all', async () => {
    await draw({ viewerSuper: true })
    for (const id of [6, 7]) {
      expect(line(id).queryByText('admin.staff.suspend')).toBeNull()
      expect(line(id).queryByText('admin.delete')).toBeNull()
      expect(line(id).queryByTestId('staff-delete-greyed')).toBeNull()
    }
  })
})

describe('Delete (O3, O7, O17)', () => {
  it('names the outcome — Erase — and sends no archive flag', async () => {
    mockApi.deleteAdmin.mockResolvedValue({ message: 'ok' })
    await draw()
    fireEvent.click(line(1).getByTestId('staff-delete'))
    expect(screen.getByTestId('staff-delete-outcome').textContent).toBe('admin.staff.outcome.erase')
    const go = screen.getByTestId('typed-confirm-go') as HTMLButtonElement
    expect(go.disabled).toBe(true)
    fireEvent.change(document.getElementById('typed-confirm')!, { target: { value: 'Aruna Example' } })
    fireEvent.click(go)
    await waitFor(() => expect(mockApi.deleteAdmin).toHaveBeenCalledWith(1, { token: 'tok' }, false))
    expect(await screen.findByText('admin.staff.erased {"name":"Aruna Example"}')).toBeTruthy()
  })

  it('names the outcome — Archive, "their name stays on past records" — and sends archive', async () => {
    mockApi.deleteAdmin.mockResolvedValue({ message: 'ok', archived: true })
    await draw()
    fireEvent.click(line(4).getByTestId('staff-delete'))
    expect(screen.getByTestId('staff-delete-outcome').textContent).toBe('admin.staff.outcome.archive')
    fireEvent.change(document.getElementById('typed-confirm')!, { target: { value: 'Devi Example' } })
    fireEvent.click(screen.getByTestId('typed-confirm-go'))
    await waitFor(() => expect(mockApi.deleteAdmin).toHaveBeenCalledWith(4, { token: 'tok' }, true))
    expect(await screen.findByText('admin.staff.archived {"name":"Devi Example"}')).toBeTruthy()
  })

  it('a mentor login is deleted through its Mentors record', async () => {
    mockApi.getStaffList.mockResolvedValue({ staff: [row({ id: 3, kind: 'mentor', mentor_id: 30, name: 'Chitra Example',
      groups: ['mentors'], delete_outcome: 'archive' })] })
    mockApi.deleteMentor.mockResolvedValue({ message: 'ok' })
    await draw()
    fireEvent.click(screen.getByTestId('staff-delete'))
    fireEvent.change(document.getElementById('typed-confirm')!, { target: { value: 'Chitra Example' } })
    fireEvent.click(screen.getByTestId('typed-confirm-go'))
    await waitFor(() => expect(mockApi.deleteMentor).toHaveBeenCalledWith(30, { token: 'tok' }, true))
    expect(mockApi.deleteAdmin).not.toHaveBeenCalled()
  })

  it('O7 / O17: greys Delete while work is unfinished, what is unfinished (with its count) in the tip', async () => {
    await draw()
    expect(line(2).queryByTestId('staff-delete')).toBeNull()
    const b = within(line(2).getByTestId('staff-delete-greyed')).getByText('admin.delete')
    expect(b.getAttribute('aria-disabled')).toBe('true')
    expect(document.getElementById(b.getAttribute('aria-describedby')!)!.textContent)
      .toBe('admin.refusal.has_open_cases.many {"n":"4"}')
    fireEvent.click(b)
    expect(screen.queryByTestId('typed-confirm-go')).toBeNull()
  })

  it('a refused delete reads in the reader\'s words, and the list is read again', async () => {
    mockApi.deleteAdmin.mockRejectedValue(Object.assign(new Error('Server sentence.'),
      { status: 409, code: 'run_in_progress', body: { code: 'run_in_progress', runs_in_progress: 1 } }))
    await draw()
    fireEvent.click(line(1).getByTestId('staff-delete'))
    fireEvent.change(document.getElementById('typed-confirm')!, { target: { value: 'Aruna Example' } })
    fireEvent.click(screen.getByTestId('typed-confirm-go'))
    expect(await screen.findByText('admin.refusal.run_in_progress.one {"n":"1"}')).toBeTruthy()
    await waitFor(() => expect(mockApi.getStaffList).toHaveBeenCalledTimes(2))
  })
})

describe('unfinishedReason', () => {
  const t = (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k)

  it('names each unfinished thing with its count, in order', () => {
    const r = row({ work: { admins: { runs_in_progress: 2 }, reviewers: { open_cases: 1 }, mentors: { scholars_now: 3 } } })
    expect(unfinishedReason(r, t)).toBe([
      'admin.refusal.has_open_cases.one {"n":"1"}',
      'admin.refusal.run_in_progress.many {"n":"2"}',
      'admin.refusal.has_scholars.many {"n":"3"}',
    ].join(' '))
  })

  it('falls back to the plain sentence when no count says what', () => {
    expect(unfinishedReason(row(), t)).toBe('admin.refusal.has_unfinished_work')
  })
})

/** A promise the test settles by hand. */
function later<V>() {
  let resolve!: (v: V) => void
  let reject!: (e: unknown) => void
  const promise = new Promise<V>((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

describe('M1b review', () => {
  it('Suspend on a reviewer with open cases says how many wait on them', async () => {
    mockApi.getStaffList.mockResolvedValue({ staff: [
      row({ id: 2, name: 'Bala Example', groups: ['reviewers'], work: { ...NO_WORK, reviewers: { open_cases: 3 } } })] })
    mockApi.revokeAdmin.mockResolvedValue({})
    await draw()
    fireEvent.click(screen.getByTestId('staff-toggle-2'))
    expect((window.confirm as jest.Mock).mock.calls[0][0])
      .toBe('admin.reviewers.revokeConfirmOpen {"name":"Bala Example","n":"3"}')
    await waitFor(() => expect(mockApi.revokeAdmin).toHaveBeenCalledWith(2, 'revoke', { token: 'tok' }))
  })

  it('Restore keeps its own confirm, open cases or not', async () => {
    mockApi.getStaffList.mockResolvedValue({ staff: [
      row({ id: 5, suspended: true, work: { ...NO_WORK, reviewers: { open_cases: 3 } } })] })
    await draw()
    fireEvent.click(screen.getByTestId('staff-toggle-5'))
    expect((window.confirm as jest.Mock).mock.calls[0][0]).toBe('admin.staff.restoreConfirm {"name":"Aruna Example"}')
  })

  it('an Erase refused `has_work` reads in words, and the list is read again', async () => {
    mockApi.deleteAdmin.mockRejectedValue(Object.assign(new Error('Server sentence.'),
      { status: 409, code: 'has_work', body: { code: 'has_work', work: { reviews: 2 } } }))
    await draw()
    fireEvent.click(line(1).getByTestId('staff-delete'))
    fireEvent.change(document.getElementById('typed-confirm')!, { target: { value: 'Aruna Example' } })
    fireEvent.click(screen.getByTestId('typed-confirm-go'))
    expect(await screen.findByText('admin.refusal.has_work')).toBeTruthy()
    expect(screen.queryByText('Server sentence.')).toBeNull()
    await waitFor(() => expect(mockApi.getStaffList).toHaveBeenCalledTimes(2))
  })

  it('a `has_unfinished_work` 409 names what is unfinished, with the counts from its body', async () => {
    mockApi.deleteAdmin.mockRejectedValue(Object.assign(new Error('Server sentence.'), {
      status: 409, code: 'has_unfinished_work', body: { code: 'has_unfinished_work', work: {
        admins: { runs_in_progress: 2 }, reviewers: { open_cases: 0 }, mentors: { scholars_now: 1 } } } }))
    await draw()
    fireEvent.click(line(4).getByTestId('staff-delete'))
    fireEvent.change(document.getElementById('typed-confirm')!, { target: { value: 'Devi Example' } })
    fireEvent.click(screen.getByTestId('typed-confirm-go'))
    expect(await screen.findByText(
      'admin.refusal.run_in_progress.many {"n":"2"} admin.refusal.has_scholars.one {"n":"1"}')).toBeTruthy()
  })

  it('a blank name still gives Delete a word to type', async () => {
    mockApi.getStaffList.mockResolvedValue({ staff: [row({ name: '  ' })] })
    mockApi.deleteAdmin.mockResolvedValue({ message: 'ok' })
    await draw()
    fireEvent.click(screen.getByTestId('staff-delete'))
    const go = screen.getByTestId('typed-confirm-go') as HTMLButtonElement
    expect(go.disabled).toBe(true)
    fireEvent.change(document.getElementById('typed-confirm')!, { target: { value: 'admin.delete' } })
    expect(go.disabled).toBe(false)
    fireEvent.click(go)
    await waitFor(() => expect(mockApi.deleteAdmin).toHaveBeenCalledWith(1, { token: 'tok' }, false))
  })

  it('a failed re-read keeps the rows, says so inline, and Retry reads again', async () => {
    mockApi.revokeAdmin.mockResolvedValue({})
    await draw()
    mockApi.getStaffList.mockRejectedValueOnce(new Error('boom'))
    fireEvent.click(screen.getByTestId('staff-toggle-1'))
    expect(await screen.findByTestId('staff-reload-failed')).toBeTruthy()
    for (const r of TEAM) expect(screen.getByTestId(`staff-row-${r.id}`)).toBeTruthy()
    fireEvent.click(within(screen.getByTestId('staff-reload-failed')).getByText('common.retry'))
    await waitFor(() => expect(screen.queryByTestId('staff-reload-failed')).toBeNull())
    expect(mockApi.getStaffList).toHaveBeenCalledTimes(3)
    expect(screen.getByTestId('staff-row-1')).toBeTruthy()
  })

  it('only the latest read lands: an older answer arriving late is ignored', async () => {
    const first = later<{ staff: api.StaffRow[] }>()
    const second = later<{ staff: api.StaffRow[] }>()
    mockApi.getStaffList.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const { rerender } = render(<StaffList token="tok" canManage viewerSuper={false} />)
    rerender(<StaffList token="tok2" canManage viewerSuper={false} />)
    second.resolve({ staff: [row({ id: 2, name: 'Bala Example' })] })
    await waitFor(() => expect(screen.getByTestId('staff-row-2')).toBeTruthy())
    first.resolve({ staff: [row({ id: 1, name: 'Aruna Example' })] })
    await first.promise
    await waitFor(() => expect(screen.getByTestId('staff-row-2')).toBeTruthy())
    expect(screen.queryByTestId('staff-row-1')).toBeNull()
  })

  it('busy is per row: a second row acts while the first is still in flight', async () => {
    const one = later<unknown>()
    mockApi.revokeAdmin.mockReturnValueOnce(one.promise as never).mockResolvedValueOnce({})
    await draw()
    fireEvent.click(screen.getByTestId('staff-toggle-1'))
    await waitFor(() => expect((screen.getByTestId('staff-toggle-1') as HTMLButtonElement).disabled).toBe(true))
    expect((screen.getByTestId('staff-toggle-4') as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(screen.getByTestId('staff-toggle-4'))
    await waitFor(() => expect(mockApi.revokeAdmin).toHaveBeenCalledWith(4, 'revoke', { token: 'tok' }))
    await waitFor(() => expect((screen.getByTestId('staff-toggle-4') as HTMLButtonElement).disabled).toBe(false))
    expect((screen.getByTestId('staff-toggle-1') as HTMLButtonElement).disabled).toBe(true)
    one.resolve({})
    await waitFor(() => expect((screen.getByTestId('staff-toggle-1') as HTMLButtonElement).disabled).toBe(false))
  })
})
