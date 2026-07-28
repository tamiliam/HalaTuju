import {
  ALREADY_LIVE, errorKey, ordered, sendsToday, switchedOn,
} from '../sponsorComms'
import type { SponsorEmailTemplate } from '../admin-api'

const tpl = (kind: string, enabled = false): SponsorEmailTemplate => ({
  kind, label: kind, enabled, subject: 's', body: 'b', placeholders: [],
  updated_by_email: '', updated_at: null, last_sent_at: null, last_sent_count: 0,
})

describe('ordered', () => {
  it('lists the nine in the sponsor journey, not alphabetically', () => {
    // An admin reading the panel is following a sponsor from registration to being told about
    // students; the list should read that way rather than by accident of the server's ordering.
    const shuffled = ['weekly_digest', 'welcome', 'credit_confirmed', 'approved'].map((k) => tpl(k))
    expect(ordered(shuffled).map((t) => t.kind))
      .toEqual(['welcome', 'approved', 'credit_confirmed', 'weekly_digest'])
  })

  it('drops a kind the panel has no copy for rather than showing it in a random place', () => {
    expect(ordered([tpl('welcome'), tpl('some_future_kind')]).map((t) => t.kind))
      .toEqual(['welcome'])
  })
})

describe('sendsToday', () => {
  it('is true for the three that are ALREADY live through their pre-S3 sender', () => {
    // These reach sponsors right now with their template switched off. Showing them as simply
    // "off" would be a lie about an email that is demonstrably going out.
    for (const kind of ALREADY_LIVE) {
      expect(sendsToday(kind, false, false)).toBe(true)
    }
  })

  it('is false for a new kind until BOTH gates are open', () => {
    expect(sendsToday('welcome', false, false)).toBe(false)
    expect(sendsToday('welcome', true, false)).toBe(false)   // platform gate shut
    expect(sendsToday('welcome', false, true)).toBe(false)   // template switched off
    expect(sendsToday('welcome', true, true)).toBe(true)
  })
})

describe('switchedOn', () => {
  it('counts only the enabled templates', () => {
    expect(switchedOn([tpl('welcome', true), tpl('approved'), tpl('rejected', true)])).toBe(2)
  })
})

describe('errorKey', () => {
  it('maps the two refusals the server can answer with', () => {
    expect(errorKey('unknown_placeholder'))
      .toBe('admin.sponsors.emails.error.unknownPlaceholder')
    expect(errorKey('banned_phrasing')).toBe('admin.sponsors.emails.error.bannedPhrasing')
  })

  it('falls back rather than rendering a raw key path for a code it has never seen', () => {
    expect(errorKey('a_brand_new_code')).toBe('admin.actionFailed')
    expect(errorKey(undefined)).toBe('admin.actionFailed')
  })
})
