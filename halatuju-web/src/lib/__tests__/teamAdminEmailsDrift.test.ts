/**
 * Team tables T4 — the drift test for Team -> Emails -> Admin emails.
 *
 * The rows come from the server (`apps/scholarship/admin_email_catalogue.py`, the ONE registry that names
 * each sender; its own pytest partitions every non-student `send_*` into it or NOT_ADMIN_SENDERS). The web
 * holds only the WORDS. A key the server serves with no words here would draw a raw i18n key on the Team
 * page, so every catalogue key must be worded — what, when, to whom — in all three languages, and nothing
 * may be worded that the server no longer serves.
 */
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import { readApi } from '@/test/apiSource'

const src = readApi('apps/scholarship/admin_email_catalogue.py')
const keys = [...src.matchAll(/^\s+Entry\('([a-z_]+)',/gm)].map((m) => m[1])

type Emails = Record<'kind' | 'when' | 'to', Record<string, string>>
const emailsOf = (cat: unknown) =>
  (cat as { admin: { team: { emails: Emails } } }).admin.team.emails

describe('the admin-email registry and its words agree', () => {
  test('parse sanity: the catalogue was really read', () => {
    expect(keys.length).toBe(12)   // A1.13b: + withdrawal_request, withdrawal_outcome
    expect(keys[0]).toBe('payment_approval')
  })

  test.each([['en', en], ['ms', ms], ['ta', ta]])('%s words every key, and only those keys', (_l, cat) => {
    const e = emailsOf(cat)
    for (const part of ['kind', 'when', 'to'] as const) {
      expect(Object.keys(e[part]).sort()).toEqual([...keys].sort())
      for (const k of keys) expect(e[part][k].trim().length).toBeGreaterThan(0)
    }
  })

  test('no row shows an address — the recipients are roles, never an inbox', () => {
    for (const cat of [en, ms, ta]) {
      for (const k of keys) expect(emailsOf(cat).to[k]).not.toMatch(/@/)
    }
  })
})
