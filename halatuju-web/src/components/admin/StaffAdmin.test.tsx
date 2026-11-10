/**
 * @jest-environment jsdom
 *
 * The Staff table's Status cell.
 *
 * Until 2026-08-03 this column read `is_active` and nothing else, so the SAME reviewer showed
 * "Paused" on Organisation → Reviewers and "Active" here. `paused_at` existed on the model and on
 * one of its two readers; this screen had simply never asked the server for it.
 *
 * The precedence assertion is the one worth keeping: revoked beats paused, because a revoked
 * account cannot be brought back by un-pausing, and naming the smaller of two facts sends an
 * org_admin to the wrong control.
 */
import { render, screen, within } from '@testing-library/react'
import { StaffTable } from './StaffAdmin'
import type { AdminItem } from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

const row = (over: Partial<AdminItem>): AdminItem => ({
  id: 1, name: 'Someone', email: 's@example.org', is_super_admin: false,
  role: 'reviewer', is_active: true, org_name: null, created_at: '2026-06-01T00:00:00Z',
  ...over,
} as AdminItem)

/** ⚠ EACH PERSON RENDERS TWICE (2026-09-08): a phone card and a desktop table row. Which one
 *  you SEE is a CSS breakpoint and jsdom applies none, so a status assertion finds two. These
 *  tests are about WHICH status is chosen — the same `statusOf` helper feeds both renderings —
 *  so asserting on the table's copy proves the rule for both. */
const draw = (rows: AdminItem[]) => render(<StaffTable rows={rows} canAct={false} />)
const ui = () => within(document.querySelector('[data-testid="table-scroller"]') as HTMLElement)

it('says a paused reviewer is paused, instead of calling them active', () => {
  draw([row({ id: 1, name: 'Vanitha', paused: true, paused_at: '2026-08-02T17:11:18Z' })])
  expect(ui().getByText('admin.reviewers.status.paused')).toBeTruthy()
  expect(screen.queryByText('admin.active')).toBeNull()
})

it('still says active for somebody who has not stepped back', () => {
  // A flag that is always true says nothing — assert the ordinary case stays ordinary.
  draw([row({ id: 2, name: 'Working', paused: false })])
  expect(ui().getByText('admin.active')).toBeTruthy()
  expect(screen.queryByText('admin.reviewers.status.paused')).toBeNull()
})

it('reports REVOKED over paused when somebody is both', () => {
  draw([row({ id: 3, name: 'Gone', is_active: false, paused: true })])
  expect(ui().getByText('admin.revoked')).toBeTruthy()
  expect(screen.queryByText('admin.reviewers.status.paused')).toBeNull()
})

it('treats a payload with no pause field as not paused, never as broken', () => {
  // An older cached payload, or any role the server does not compute pause for.
  draw([row({ id: 4, name: 'Legacy' })])
  expect(ui().getByText('admin.active')).toBeTruthy()
})

describe('the row actions (2026-09-09)', () => {
  /** ⚠ SCOPED TO THIS RENDER'S OWN CONTAINER, not `document`. The helper at the top of this file
   *  reaches for the first `[data-testid="table-scroller"]` in the document, which is fine while
   *  one test renders once — but these tests each render their own table, and a global lookup
   *  quietly answered every one of them with the FIRST test's markup. Three assertions passed and
   *  failed for reasons that had nothing to do with the row under test. */
  const act = (rows: AdminItem[], on: Partial<Parameters<typeof StaffTable>[0]> = {}) => {
    const r = render(<StaffTable rows={rows} canAct onResend={jest.fn()} onToggle={jest.fn()}
      onDelete={jest.fn()} {...on} />)
    return within(r.container.querySelector('[data-testid="table-scroller"]') as HTMLElement)
  }

  it('⚠ offers RESEND only to somebody who has not arrived', () => {
    // The condition used to be `is_active`, so it sat beside every working colleague — and
    // pressing it OVERWRITES their password with a temporary one and mails it to them. One click
    // locked a signed-in admin out of their own account (owner: "the Resend link is a bug").
    const t = act([row({ id: 1, name: 'Waiting',
                         invitation: { status: 'no_reply' } as AdminItem['invitation'] })])
    expect(t.getByText('admin.resend')).toBeTruthy()
  })

  it('⚠ and NEVER to somebody who has already signed in', () => {
    const t = act([row({ id: 2, name: 'Arrived',
                         invitation: { status: 'accepted' } as AdminItem['invitation'] })])
    expect(t.queryByText('admin.resend')).toBeNull()
  })

  it('offers Delete only where the SERVER said deletable', () => {
    const t = act([row({ id: 3, name: 'Fresh', role: 'admin', deletable: true,
                         invitation: { status: 'accepted' } as AdminItem['invitation'] })])
    expect(t.getByText('admin.delete')).toBeTruthy()
  })

  it('⚠ and Revoke, with Delete GREYED, for somebody with work on record (Sprint T2)', () => {
    // The whole rule, in one row: Kulaly has made 25 payment runs. Revoke stays; Delete is drawn
    // but cannot act, so the owner sees the control and the reason, not a gap.
    const onDelete = jest.fn()
    const t = act([row({ id: 4, name: 'Kulaly', role: 'admin', deletable: false,
                         work: { payment_runs_made: 25 },
                         invitation: { status: 'accepted' } as AdminItem['invitation'] })], { onDelete })
    const del = t.getByText('admin.delete')
    expect(del.getAttribute('aria-disabled')).toBe('true')
    del.click()
    expect(onDelete).not.toHaveBeenCalled()
    expect(t.getByText('admin.revoke')).toBeTruthy()
  })

  it('⚠ draws NO controls at all on a row this viewer may not manage', () => {
    // An org_admin SEES their fellow organisation admins and may not act on them. Drawing a
    // Revoke the server answers with 404 is worse than drawing nothing.
    const t = act([row({ id: 5, name: 'Peer Lead', role: 'org_admin', manageable: false,
                         deletable: false,
                         invitation: { status: 'accepted' } as AdminItem['invitation'] })])
    expect(t.queryByText('admin.revoke')).toBeNull()
    expect(t.queryByText('admin.delete')).toBeNull()
    expect(t.queryByText('admin.resend')).toBeNull()
  })

  it('but still draws them for a manageable colleague', () => {
    // Drive over the bump: a flag read the wrong way round would empty every row of controls.
    const t = act([row({ id: 6, name: 'Own Rev', manageable: true,
                         invitation: { status: 'accepted' } as AdminItem['invitation'] })])
    expect(t.getByText('admin.revoke')).toBeTruthy()
  })

  it('⚠ offers no RESEND to a revoked or cancelled account, invitation open or not', () => {
    // The server refuses it (`not_active`): it would rotate a password and email it to somebody
    // who cannot sign in (2026-10-09).
    const t = act([row({ id: 7, name: 'Cancelled', is_active: false,
                         invitation: { status: 'revoked' } as AdminItem['invitation'] }),
                   row({ id: 8, name: 'Revoked early', is_active: false,
                         invitation: { status: 'no_reply' } as AdminItem['invitation'] })])
    expect(t.queryByText('admin.resend')).toBeNull()
  })

  it('says WHY Delete is greyed — the reason is the button\'s description', () => {
    // The old "Has work on record — revoke instead" grey text is gone; the reason rides on Delete.
    const t = act([row({ id: 9, name: 'Kulaly', role: 'admin', deletable: false,
                         work: { payment_runs_made: 25, assigned_applications: 2 } })])
    const del = t.getByText('admin.delete')
    const why = document.getElementById(del.getAttribute('aria-describedby') ?? '')
    expect(why?.textContent).toBe('admin.deleteHasWork')
  })

  it('says nothing about work on a row that is simply deletable', () => {
    const t = act([row({ id: 10, name: 'Fresh', role: 'admin', deletable: true, work: {} })])
    expect(t.getByText('admin.delete').getAttribute('aria-disabled')).toBeNull()
    expect(t.queryByText('admin.deleteHasWork')).toBeNull()
  })

  it('⚠ draws an organisation admin\'s Delete for a SUPER viewer only (Sprint T2)', () => {
    const lead = [row({ id: 14, name: 'Lead', role: 'org_admin', deletable: true, work: {} })]
    expect(act(lead).queryByText('admin.delete')).toBeNull()
    expect(act(lead, { viewerSuper: true }).getByText('admin.delete')).toBeTruthy()
  })

  it('offers Change role only where a switch exists', () => {
    const onChangeRole = jest.fn()
    const t = act([row({ id: 11, name: 'Admin A', role: 'admin' }),
                   row({ id: 12, name: 'Lead', role: 'org_admin' }),
                   row({ id: 13, name: 'Gone', role: 'finance', is_active: false })],
                  { onChangeRole })
    const buttons = t.getAllByText('admin.changeRole')
    expect(buttons.length).toBe(1)                     // the admin only — never the org_admin
    buttons[0].click()
    expect(onChangeRole).toHaveBeenCalledWith(expect.objectContaining({ id: 11 }))
  })

  it('offers no Change role when the page passes no handler (a viewer who cannot act)', () => {
    const t = act([row({ id: 14, name: 'Admin B', role: 'admin' })])
    expect(t.queryByText('admin.changeRole')).toBeNull()
  })
})

describe('#39 Sprint 4: permission chips, and the name that opens the person page', () => {
  const act = (rows: AdminItem[], on: Partial<Parameters<typeof StaffTable>[0]> = {}) => {
    const r = render(<StaffTable rows={rows} canAct {...on} />)
    return within(r.container.querySelector('[data-testid="table-scroller"]') as HTMLElement)
  }

  it('shows what a custom set adds and takes away, beside the role', () => {
    const t = act([row({ id: 21, name: 'Rohini', custom: true, permissions_added: ['spending'],
                         permissions_removed: [] }),
                   row({ id: 22, name: 'Plain', role: 'admin', custom: false })])
    expect(t.getAllByTestId('permission-chips')).toHaveLength(1)
    expect(t.getByText('admin.permEditor.custom')).toBeTruthy()
    expect(t.getByText('+ admin.perm.spending.name')).toBeTruthy()
  })

  it('links a name only where the page gives an address, on the table AND the phone card', () => {
    // 2026-10-22: a team member's permissions live on their own page; the PAGE decides who links.
    const nameHref = (a: AdminItem) => (a.role === 'admin' ? `/people/${a.id}` : null)
    const r = render(<StaffTable rows={[row({ id: 31, name: 'Admin A', role: 'admin' }),
                                        row({ id: 32, name: 'Lead', role: 'org_admin' })]}
      canAct nameHref={nameHref} />)
    const table = within(r.container.querySelector('[data-testid="table-scroller"]') as HTMLElement)
    expect(table.getByText('Admin A').closest('a')?.getAttribute('href')).toBe('/people/31')
    expect(table.getByText('Lead').closest('a')).toBeNull()
    const cards = within(r.getByTestId('staff-cards'))
    expect(cards.getByText('Admin A').closest('a')?.getAttribute('href')).toBe('/people/31')
    expect(cards.getByText('Lead').closest('a')).toBeNull()
  })

  it('draws every name as plain text when the page passes no addresses (the platform screens)', () => {
    const r = render(<StaffTable rows={[row({ id: 35, name: 'Admin B', role: 'admin' })]} canAct />)
    expect(r.container.querySelector('a')).toBeNull()
  })
})

describe('Team → Admins reads like Reviewers and Mentors (owner 2026-11-08)', () => {
  const team = { onRemove: jest.fn() }
  const heads = () => ui().getAllByRole('columnheader').map((h) => h.textContent)

  it('puts the email under the name, drops the Email column, and adds Last seen after Status', () => {
    render(<StaffTable rows={[row({ id: 40, role: 'admin', last_seen_at: '2026-11-02T00:00:00Z' })]} canAct team={team} />)
    expect(heads()).toEqual(['admin.nameHeader', 'admin.team.colAlsoIn', 'admin.statusHeader',
      'admin.reviewers.colLastSeen', 'admin.actionHeader'])
    expect(ui().getByTestId('team-email-40').textContent).toBe('s@example.org')
    expect(ui().getByTestId('team-email-40').closest('td')?.textContent).toContain('Someone')
    expect(ui().getByTestId('team-last-seen-40').textContent).toBe('02/11/2026')
  })

  it('says "Not recorded" where the server has no last seen', () => {
    render(<StaffTable rows={[row({ id: 41, role: 'admin', last_seen_at: null })]} canAct team={team} />)
    expect(ui().getByTestId('team-last-seen-41').textContent).toBe('admin.reviewers.lastSeenUnknown')
  })

  it('the shared header style on Team; the platform screens keep theirs, with the Email column', () => {
    const { unmount } = render(<StaffTable rows={[row({ id: 42 })]} canAct team={team} />)
    expect(ui().getAllByRole('columnheader')[0].className).toContain('uppercase')
    unmount()
    render(<StaffTable rows={[row({ id: 42 })]} canAct />)
    expect(heads()).toEqual(['admin.nameHeader', 'admin.emailHeader', 'admin.roleHeader', 'admin.statusHeader',
      'admin.actionHeader'])
    expect(ui().getAllByRole('columnheader')[0].className).not.toContain('uppercase')
    expect(ui().queryByTestId('team-last-seen-42')).toBeNull()
  })

  it('O9 (owner 2026-11-10): shows NO phone number on the Admins table, on the table or the phone card', () => {
    const { container } = render(<StaffTable rows={[row({ id: 43, role: 'admin', phone: '012-0000 0000' } as Partial<AdminItem>)]}
      canAct team={team} />)
    expect(container.querySelector('[data-testid="team-phone-43"]')).toBeNull()
    expect(container.textContent).not.toContain('012-0000 0000')
  })

  it('O9 is the Admins table only: the platform screens keep the phone the server sent', () => {
    const { container } = render(<StaffTable rows={[row({ id: 44, role: 'org_admin', phone: '012-0000 0000' } as Partial<AdminItem>)]}
      canAct={false} />)
    expect(container.querySelectorAll('[data-testid="team-phone-44"]').length).toBe(2)   // card + table
  })

  it('the empty row spans every column', () => {
    render(<StaffTable rows={[]} canAct team={team} />)
    expect(ui().getByText('admin.noAdmins').closest('td')?.getAttribute('colspan')).toBe('5')
  })
})
