/**
 * Reading an invitation and a person's standing off the staff payload.
 *
 * ⚠ These assert FIXED inputs against LITERAL expected words. A test that recomputed the rule
 * would agree with a broken rule — the billing-month lesson, which cost eight hours of red tests
 * for exactly that reason.
 */
import { DORMANT_DAYS, isOutstanding, outstanding, sendState, standingOf } from '../invitations'
import type { AdminItem } from '../admin-api'

const person = (over: Partial<AdminItem>): AdminItem => ({
  id: 1, name: 'Someone', email: 's@example.org', is_super_admin: false, role: 'reviewer',
  is_active: true, org_name: null, created_at: '2026-01-01T00:00:00Z', ...over,
} as AdminItem)

const inv = (over: Partial<NonNullable<AdminItem['invitation']>> = {}) => ({
  status: 'invited' as const, sent_at: '2026-08-01T00:00:00Z', send_count: 1,
  last_send_ok: true, last_send_error: '', expires_at: null, credential_issued: true, ...over,
})

const NOW = new Date('2026-08-03T00:00:00Z')
const daysAgo = (n: number) =>
  new Date(NOW.getTime() - n * 86_400_000).toISOString()

describe('what a person is doing', () => {
  it('calls a revoked account revoked, whatever else is true of it', () => {
    // Nothing below revoked can be acted on — un-pausing a revoked account gives them nothing.
    expect(standingOf(person({ is_active: false, paused: true, last_seen_at: daysAgo(1) }), NOW))
      .toBe('revoked')
  })

  it('calls a paused person paused rather than dormant', () => {
    expect(standingOf(person({ paused: true, last_seen_at: daysAgo(400) }), NOW)).toBe('paused')
  })

  it('calls a long absence dormant', () => {
    expect(standingOf(person({ last_seen_at: daysAgo(DORMANT_DAYS + 1) }), NOW)).toBe('dormant')
  })

  it('does not call somebody dormant on the threshold day itself', () => {
    expect(standingOf(person({ last_seen_at: daysAgo(DORMANT_DAYS) }), NOW)).toBe('active')
  })

  it('says NOT RECORDED, never "never signed in", when the column is empty', () => {
    // Everyone predating the sign-in signal is empty. Accusing them of ignoring their invitation
    // would be a lie the screen tells on its first day.
    expect(standingOf(person({ last_seen_at: null }), NOW)).toBe('notRecorded')
  })
})

describe('which invitations are still waiting', () => {
  it('counts waiting, expired and unanswered as outstanding', () => {
    for (const status of ['invited', 'expired', 'no_reply'] as const) {
      expect(isOutstanding(person({ invitation: inv({ status }) }))).toBe(true)
    }
  })

  it('does not count settled ones', () => {
    for (const status of ['accepted', 'revoked'] as const) {
      expect(isOutstanding(person({ invitation: inv({ status }) }))).toBe(false)
    }
    expect(isOutstanding(person({ invitation: null }))).toBe(false)
  })

  it('puts the ones needing action first, then the longest waiting', () => {
    const rows = [
      person({ id: 1, invitation: inv({ status: 'invited', sent_at: '2026-08-02T00:00:00Z' }) }),
      person({ id: 2, invitation: inv({ status: 'no_reply', sent_at: '2026-07-01T00:00:00Z' }) }),
      person({ id: 3, invitation: inv({ status: 'expired', sent_at: '2026-07-20T00:00:00Z' }) }),
      person({ id: 4, invitation: inv({ status: 'accepted' }) }),
      person({ id: 5, invitation: inv({ status: 'invited', sent_at: '2026-07-10T00:00:00Z' }) }),
    ]
    // expired (a Resend is genuinely required) → no_reply → waiting, oldest first within each.
    expect(outstanding(rows).map((r) => r.id)).toEqual([3, 2, 5, 1])
  })
})

describe('what happened to the email', () => {
  it('reports a real failure as a failure', () => {
    expect(sendState(person({ invitation: inv({ last_send_ok: false }) }))).toBe('failed')
  })

  it('reports a delivered send as delivered', () => {
    expect(sendState(person({ invitation: inv({ last_send_ok: true }) }))).toBe('sent')
  })

  it('⚠ treats an UNKNOWN outcome as not recorded, never as a failure', () => {
    // Every backfilled row is null: whether a historic email arrived is unknowable, and rendering
    // that as "Failed" would accuse us of bouncing mail we have no evidence about.
    expect(sendState(person({ invitation: inv({ last_send_ok: null }) }))).toBe('notRecorded')
  })

  it('reports nothing recorded when there is no invitation at all', () => {
    expect(sendState(person({ invitation: null }))).toBe('notRecorded')
  })
})
