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

  it('⚠ and Revoke — never Delete — for somebody with work on record', () => {
    // The whole rule, in one row: Kulaly has made 25 payment runs. Revoke stays, Delete does not.
    const t = act([row({ id: 4, name: 'Kulaly', role: 'admin', deletable: false,
                         work: { payment_runs_made: 25 },
                         invitation: { status: 'accepted' } as AdminItem['invitation'] })])
    expect(t.queryByText('admin.delete')).toBeNull()
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
})
