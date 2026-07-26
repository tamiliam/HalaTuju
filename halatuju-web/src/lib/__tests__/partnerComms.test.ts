/**
 * Partner-email card helpers (2026-07-26).
 *
 * The load-bearing assertion here is the honest reach count: the card must state that today it
 * reaches ZERO of nine referral partners, rather than looking as though switching an email on
 * would do something. The rest pins the small things a refactor could quietly break.
 */
import {
  PARTNER_EMAIL_KINDS, errorKey, everSent, insertPlaceholder, kindKey,
  nobodyReachable, reach, unreachable,
} from '@/lib/partnerComms'
import type { PartnerEmailOrg, PartnerEmailTemplate } from '@/lib/admin-api'

const org = (o: Partial<PartnerEmailOrg>): PartnerEmailOrg => ({
  id: 1, code: 'smc', name: 'Sri Murugan Centre', students: 62,
  has_email: false, is_house_org: false, qualifies: false, ...o,
})

const tpl = (t: Partial<PartnerEmailTemplate>): PartnerEmailTemplate => ({
  kind: 'weekly_summary', enabled: false, subject: 's', body: 'b', placeholders: [],
  updated_by_email: '', updated_at: null, last_sent_at: null, last_sent_orgs: 0, ...t,
})

describe('PARTNER_EMAIL_KINDS', () => {
  it('lists the five emails in card order', () => {
    expect(PARTNER_EMAIL_KINDS).toEqual([
      'weekly_summary', 'shortlisted_followup', 'awaiting_review', 'awarded', 'assigned',
    ])
  })

  it('builds a stable i18n key per kind', () => {
    expect(kindKey('awarded')).toBe('admin.sources.emails.kind.awarded')
  })
})

describe('reach', () => {
  it('today’s honest answer: nine partners, none reachable', () => {
    const orgs = [
      org({ id: 1, code: 'brightpath', is_house_org: true, has_email: true }),
      ...Array.from({ length: 9 }, (_, i) => org({ id: i + 2, code: `p${i}` })),
    ]
    expect(reach(orgs)).toEqual({ reachable: 0, partners: 9 })
    expect(nobodyReachable(orgs)).toBe(true)
  })

  it('never counts the house organisation as a partner, even with an address', () => {
    const orgs = [org({ code: 'brightpath', is_house_org: true, has_email: true, qualifies: false })]
    expect(reach(orgs)).toEqual({ reachable: 0, partners: 0 })
  })

  it('counts a partner the server marked as qualifying', () => {
    const orgs = [
      org({ id: 1, code: 'smc', has_email: true, qualifies: true }),
      org({ id: 2, code: 'pptm' }),
    ]
    expect(reach(orgs)).toEqual({ reachable: 1, partners: 2 })
    expect(nobodyReachable(orgs)).toBe(false)
  })

  it('trusts the server’s qualifies flag rather than re-deriving it', () => {
    // has_email true but qualifies false (e.g. the org went inactive) — the card must not
    // second-guess the server, because the real rule also excludes the house org and inactive rows.
    const orgs = [org({ has_email: true, qualifies: false })]
    expect(reach(orgs).reachable).toBe(0)
  })
})

describe('unreachable', () => {
  it('names the partners that need an address, excluding the house org', () => {
    const orgs = [
      org({ id: 1, code: 'brightpath', is_house_org: true }),
      org({ id: 2, code: 'smc', has_email: true, qualifies: true }),
      org({ id: 3, code: 'pptm' }),
      org({ id: 4, code: 'hss' }),
    ]
    expect(unreachable(orgs).map((o) => o.code)).toEqual(['pptm', 'hss'])
  })
})

describe('everSent', () => {
  it('is false until a send actually succeeded', () => {
    expect(everSent(tpl({}))).toBe(false)
  })

  it('is true once the log records one', () => {
    expect(everSent(tpl({ last_sent_at: '2026-07-21T00:03:00Z' }))).toBe(true)
  })
})

describe('insertPlaceholder', () => {
  it('inserts at the caret and reports where the caret lands', () => {
    expect(insertPlaceholder('Dear ,', '{contact_person}', 5))
      .toEqual({ value: 'Dear {contact_person},', caret: 21 })
  })

  it('appends when the caret is past the end', () => {
    expect(insertPlaceholder('abc', '{x}', 99).value).toBe('abc{x}')
  })

  it('prepends on a negative caret rather than throwing', () => {
    expect(insertPlaceholder('abc', '{x}', -3).value).toBe('{x}abc')
  })
})

describe('errorKey', () => {
  it('maps each refusal the server can return', () => {
    expect(errorKey('unknown_placeholder')).toBe('admin.sources.emails.error.unknownPlaceholder')
    expect(errorKey('conduit_phrasing')).toBe('admin.sources.emails.error.conduitPhrasing')
    expect(errorKey('subject_and_body_required')).toBe('admin.sources.emails.error.required')
  })

  it('falls back to the generic failure for anything unmapped', () => {
    expect(errorKey('something_new')).toBe('admin.actionFailed')
    expect(errorKey(undefined)).toBe('admin.actionFailed')
  })
})
