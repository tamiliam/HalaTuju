import {
  ALREADY_LIVE, errorKey, ordered, sendingDespiteSwitch, sendsToday, switchedOn,
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
  it('reads the pre-S3 world while the platform gate is shut', () => {
    // Templates are inert; only the three legacy senders run, whatever the switches say.
    for (const kind of ALREADY_LIVE) {
      expect(sendsToday(kind, false, false)).toBe(true)
      expect(sendsToday(kind, true, false)).toBe(true)
    }
    expect(sendsToday('welcome', true, false)).toBe(false)   // a new kind cannot send yet
  })

  it('hands over completely once the platform gate opens', () => {
    // This is the half that matters after the owner's seeding decision: the adopted three ship
    // switched ON, so "off" now means STOP — and it has to actually stop.
    expect(sendsToday('weekly_digest', true, true)).toBe(true)
    expect(sendsToday('weekly_digest', false, true)).toBe(false)
    expect(sendsToday('welcome', true, true)).toBe(true)
    expect(sendsToday('welcome', false, true)).toBe(false)
  })
})

describe('sendingDespiteSwitch', () => {
  it('flags a row that is going out even though its switch reads off', () => {
    expect(sendingDespiteSwitch('weekly_digest', false, false)).toBe(true)
  })

  it('says nothing once the switch tells the truth by itself', () => {
    expect(sendingDespiteSwitch('weekly_digest', true, false)).toBe(false)   // on and sending
    expect(sendingDespiteSwitch('weekly_digest', false, true)).toBe(false)   // off and stopped
    expect(sendingDespiteSwitch('welcome', false, false)).toBe(false)        // never sent
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
