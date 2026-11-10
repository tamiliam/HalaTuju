/**
 * @jest-environment jsdom
 *
 * Sprint T2 (owner, 2026-11-08): the ONE action cell every Team table and person page draws —
 * Revoke / Restore, then Delete. "The delete however will be greyed out if there is work on record.
 * When hovered above delete link/text, it may say there is work on record, etc. For org admins, the
 * delete button should be visible only to super admin."
 *
 * The tables and pages have their own rendered tests; this pins the cell's own promises: the reason
 * is reachable by HOVER, by TAP and by keyboard FOCUS (a `disabled` button allows none of the three),
 * it carries the counts, and a greyed Delete never deletes.
 */
import { act, fireEvent, render, screen } from '@testing-library/react'
import StaffActions from './StaffActions'
import TableFrame from './TableFrame'

jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k) }),
}))

const WORK = { assigned_applications: 2, payment_runs: 1 }
const REASON = 'admin.deleteHasWork {"work":"assigned applications: 2, payment runs: 1"}'

/** jsdom has no PointerEvent with `pointerType` (InfoTip.test's helper), so it is put on by hand. */
function pointer(el: Element, type: 'pointerover' | 'pointerout', pointerType: string) {
  const e = new MouseEvent(type, { bubbles: true, cancelable: true })
  Object.defineProperty(e, 'pointerType', { value: pointerType })
  act(() => { el.dispatchEvent(e) })
}

const greyed = () => screen.getByTestId('staff-delete-greyed').querySelector('button') as HTMLButtonElement

describe('Revoke / Restore, then Delete', () => {
  it('draws Revoke before Delete, and each does its own thing', () => {
    const onToggle = jest.fn()
    const onDelete = jest.fn()
    render(<StaffActions active onToggle={onToggle} onDelete={onDelete} deletable />)
    const buttons = screen.getAllByRole('button').map((b) => b.textContent)
    expect(buttons).toEqual(['admin.revoke', 'admin.delete'])
    fireEvent.click(screen.getByText('admin.revoke'))
    expect(onToggle).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByTestId('staff-delete'))
    expect(onDelete).toHaveBeenCalledTimes(1)
  })

  it('says Restore for somebody revoked, in the caller\'s own words when it has some', () => {
    const { unmount } = render(<StaffActions active={false} onToggle={() => {}} />)
    expect(screen.getByText('admin.restore')).toBeTruthy()
    unmount()
    render(<StaffActions active onToggle={() => {}} revokeKey="admin.mentors.action.deactivate" />)
    expect(screen.getByText('admin.mentors.action.deactivate')).toBeTruthy()
  })

  it('draws no Delete where the server offers none (no work, and not deletable)', () => {
    render(<StaffActions active onToggle={() => {}} onDelete={() => {}} />)
    expect(screen.queryByText('admin.delete')).toBeNull()
  })

  it('draws no Delete where the caller hands in no onDelete', () => {
    render(<StaffActions active onToggle={() => {}} deletable />)
    expect(screen.queryByText('admin.delete')).toBeNull()
  })
})

describe('the greyed Delete — work on record', () => {
  it('is greyed, aria-disabled (not disabled), and never deletes', () => {
    const onDelete = jest.fn()
    render(<StaffActions active onDelete={onDelete} work={WORK} />)
    expect(screen.queryByTestId('staff-delete')).toBeNull()
    const b = greyed()
    expect(b.getAttribute('aria-disabled')).toBe('true')
    expect(b.disabled).toBe(false)   // a disabled button could take no focus, so no reason
    expect(b.className).toContain('text-ground-400')
    fireEvent.click(b)
    expect(onDelete).not.toHaveBeenCalled()
  })

  it('carries its reason, with the counts, for a screen reader before any bubble opens', () => {
    render(<StaffActions active onDelete={() => {}} work={WORK} />)
    const id = greyed().getAttribute('aria-describedby')!
    expect(document.getElementById(id)!.textContent).toBe(REASON)
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('shows the reason on HOVER with a mouse, and hides it when the mouse leaves', async () => {
    render(<StaffActions active onDelete={() => {}} work={WORK} />)
    pointer(greyed(), 'pointerover', 'touch')   // a finger is never a hover
    expect(greyed().getAttribute('aria-expanded')).toBe('false')
    pointer(greyed(), 'pointerover', 'mouse')
    expect((await screen.findByRole('tooltip')).textContent).toBe(REASON)
    pointer(greyed(), 'pointerout', 'mouse')
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('shows the reason on a TAP, and keeps it until tapped again', async () => {
    render(<StaffActions active onDelete={() => {}} work={WORK} />)
    fireEvent.click(greyed())
    expect((await screen.findByRole('tooltip')).textContent).toBe(REASON)
    expect(greyed().getAttribute('aria-expanded')).toBe('true')
    fireEvent.click(greyed())
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('draws the reason ABOVE the table frame, so the frame cannot clip it (Team -> Reviewers, 2026-11-10)', async () => {
    render(
      <TableFrame label="Reviewers">
        <table><tbody><tr><td><StaffActions active onDelete={() => {}} work={WORK} /></td></tr></tbody></table>
      </TableFrame>,
    )
    fireEvent.click(greyed())
    const bubble = await screen.findByRole('tooltip')
    expect(bubble.closest('table')).toBeNull()
    expect(bubble.parentElement).toBe(document.body)
    // a tap on the reason itself keeps it open: the bubble is no longer inside the cell
    act(() => { bubble.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true })) })
    expect(screen.queryByRole('tooltip')).toBe(bubble)
  })

  it('shows the reason on keyboard FOCUS, and hides it on blur', async () => {
    render(<StaffActions active onDelete={() => {}} work={WORK} />)
    act(() => { greyed().focus() })
    expect((await screen.findByRole('tooltip')).textContent).toBe(REASON)
    act(() => { greyed().blur() })
    expect(screen.queryByRole('tooltip')).toBeNull()
  })
})

describe('an organisation admin\'s row (owner: "visible only to super admin")', () => {
  it('shows a non-super viewer no Delete at all — live or greyed', () => {
    const { unmount } = render(<StaffActions active onDelete={() => {}} deletable orgAdmin />)
    expect(screen.queryByText('admin.delete')).toBeNull()
    unmount()
    render(<StaffActions active onDelete={() => {}} work={WORK} orgAdmin />)
    expect(screen.queryByText('admin.delete')).toBeNull()
  })

  it('shows a super the Delete, live or greyed', () => {
    const { unmount } = render(<StaffActions active onDelete={() => {}} deletable orgAdmin viewerSuper />)
    expect(screen.getByTestId('staff-delete')).toBeTruthy()
    unmount()
    render(<StaffActions active onDelete={() => {}} work={WORK} orgAdmin viewerSuper />)
    expect(screen.getByTestId('staff-delete-greyed')).toBeTruthy()
  })
})

describe('a row nobody may ever delete (T2 review N2: `delete_never`)', () => {
  it('draws no Delete at all, even with work on record — a greyed "work" reason would mislead', () => {
    const { unmount } = render(<StaffActions active onToggle={() => {}} onDelete={() => {}} work={WORK} deleteNever viewerSuper />)
    expect(screen.queryByText('admin.delete')).toBeNull()
    expect(screen.getByText('admin.revoke')).toBeTruthy()
    unmount()
    render(<StaffActions active onDelete={() => {}} deletable deleteNever viewerSuper />)
    expect(screen.queryByText('admin.delete')).toBeNull()
  })
})

describe('M1b: refused Suspend and Delete, greyed with their reason (O7, O17, O18)', () => {
  it('toggleBlocked greys Suspend: the reason is in the tip and a click never toggles', () => {
    const onToggle = jest.fn()
    render(<StaffActions active onToggle={onToggle} toggleTestId="staff-toggle-3" toggleBlocked="They still mentor 2 scholars." />)
    expect(screen.queryByTestId('staff-toggle-3')).toBeNull()
    const b = screen.getByTestId('staff-toggle-3-greyed').querySelector('button') as HTMLButtonElement
    expect(b.textContent).toBe('admin.revoke')
    expect(b.getAttribute('aria-disabled')).toBe('true')
    expect(document.getElementById(b.getAttribute('aria-describedby')!)!.textContent).toBe('They still mentor 2 scholars.')
    fireEvent.click(b)
    expect(onToggle).not.toHaveBeenCalled()
  })

  it('deleteBlocked greys Delete with the caller\'s reason, even with no work on the row', () => {
    const onDelete = jest.fn()
    render(<StaffActions active onDelete={onDelete} deleteBlocked="Reassign their 4 open cases first." />)
    expect(screen.queryByTestId('staff-delete')).toBeNull()
    const b = greyed()
    expect(document.getElementById(b.getAttribute('aria-describedby')!)!.textContent).toBe('Reassign their 4 open cases first.')
    fireEvent.click(b)
    expect(onDelete).not.toHaveBeenCalled()
  })
})
