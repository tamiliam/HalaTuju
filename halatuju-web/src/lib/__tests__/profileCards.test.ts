/**
 * The Profile page's card registry (`lib/profileCards.ts`, common profile S1, 2026-10-31).
 *
 * The role snapshot below is LITERAL on purpose (as `navigation.test.ts`'s is): it is the owner's
 * card matrix, a fact outside the registry, so a change to who sees a card has to be typed out here.
 * The permission sets are the server's presets (`apps/courses/staff_permissions.py`), as
 * `admin/role/` serves them resolved.
 */
import * as fs from 'fs'
import * as path from 'path'

import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'
import { adminLanding, mustCompleteProfile } from '@/lib/adminLanding'
import {
  PROFILE_CARDS, accessLines, cardsFor, profileContext, reviewsCases, type ProfileCardContext,
} from '@/lib/profileCards'

const PRESET: Record<string, string[]> = {
  super: ['review', 'see_all', 'qc', 'spending', 'payments_prepare', 'payments_check', 'payments_approve',
          'manage_team'],
  org_admin: ['see_all', 'qc', 'spending', 'manage_team'],
  admin: ['see_all', 'spending', 'payments_prepare'],
  finance: ['payments_approve'],
  reviewer: ['review'],
  qc: ['see_all', 'qc'],
  partner: [],
  source_partner: [],
}
const ctx = (role: string, permissions = PRESET[role]): ProfileCardContext =>
  ({ role, permissions, isSuper: role === 'super' })

const REVIEWER_CARDS = ['contact', 'qualifications', 'address', 'takingPart']

describe('each role sees exactly its cards, in page order', () => {
  it.each([
    ['super', ['you', 'access', 'signin']],
    ['org_admin', ['you', 'access', 'signin']],
    ['admin', ['you', 'access', 'signin']],
    ['finance', ['you', 'access', 'signin']],
    ['qc', ['you', 'access', 'signin']],
    ['reviewer', ['you', 'contact', 'access', 'qualifications', 'address', 'takingPart', 'signin']],
    ['partner', ['you', 'access', 'organisation', 'signin']],
    ['source_partner', ['you', 'access', 'organisation', 'signin']],
  ])('%s', (role, cards) => {
    expect(cardsFor(ctx(role))).toEqual(cards)
  })
})

describe('the reviewer cards follow the `review` PERMISSION, not the Reviewer role', () => {
  it.each(['admin', 'org_admin', 'qc', 'finance'])('%s given `review` gets them', (role) => {
    const got = cardsFor(ctx(role, [...PRESET[role], 'review']))
    for (const id of REVIEWER_CARDS) expect(got).toContain(id)
  })

  it('a reviewer whose permissions lost `review` loses them', () => {
    const got = cardsFor(ctx('reviewer', []))
    for (const id of REVIEWER_CARDS) expect(got).not.toContain(id)
    expect(got).toEqual(['you', 'access', 'signin'])
  })

  it('a super — who holds every key — never gets them', () => {
    expect(reviewsCases(ctx('super'))).toBe(false)
    // Whatever the payload says, and whatever role column a legacy super row carries.
    expect(cardsFor({ role: 'super', permissions: ['review'], isSuper: true })).toEqual(['you', 'access', 'signin'])
    const legacy = profileContext({ role: 'reviewer', is_super_admin: true, permissions: ['review'] })
    expect(legacy).toEqual({ role: 'super', permissions: ['review'], isSuper: true })
    expect(cardsFor(legacy)).toEqual(['you', 'access', 'signin'])
  })

  it('a payload with no permissions shows no reviewer card (never invents one)', () => {
    expect(cardsFor({ role: 'reviewer', permissions: undefined, isSuper: false })).toEqual(['you', 'access', 'signin'])
  })
})

describe('the registry itself', () => {
  it('has one entry per card, with distinct orders', () => {
    const ids = PROFILE_CARDS.map((c) => c.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(new Set(PROFILE_CARDS.map((c) => c.order)).size).toBe(PROFILE_CARDS.length)
  })

  it('every card has its component on the page, and the page has no card the registry lacks', () => {
    const page = fs.readFileSync(path.join(__dirname, '..', '..', 'app', 'admin', 'profile', 'page.tsx'), 'utf8')
    const block = page.slice(page.indexOf('const CARDS'), page.indexOf('}', page.indexOf('const CARDS')))
    const onPage = [...block.matchAll(/^\s+(\w+): lazySource\(/gm)].map((m) => m[1]).sort()
    expect(onPage).toEqual(PROFILE_CARDS.map((c) => c.id).sort())
  })
})

describe('"You can" lines', () => {
  const resolve = (msgs: unknown, key: string): unknown =>
    key.split('.').reduce<unknown>((cur, k) => (cur && typeof cur === 'object' ? (cur as Record<string, unknown>)[k] : undefined), msgs)

  it('a super is told one line; an org admin its role line and its named keys; a partner and a source their own', () => {
    expect(accessLines(ctx('super'))).toEqual(['admin.myProfile.can.super'])
    expect(accessLines(ctx('org_admin'))).toEqual(['admin.myProfile.can.org_admin', 'admin.perm.see_all.name',
      'admin.perm.qc.name', 'admin.perm.spending.name'])
    expect(accessLines(ctx('reviewer'))).toEqual(['admin.perm.review.name'])
    expect(accessLines(ctx('partner'))).toEqual(['admin.myProfile.can.partner'])
    expect(accessLines(ctx('source_partner'))).toEqual(['admin.myProfile.can.source_partner'])
    expect(accessLines(ctx('reviewer', []))).toEqual(['admin.myProfile.can.profileOnly'])
  })

  it.each([['en', en], ['ms', ms], ['ta', ta]] as const)('every line resolves in %s', (_l, msgs) => {
    const keys = new Set(Object.keys(PRESET).flatMap((r) => accessLines(ctx(r))))
    keys.add('admin.myProfile.can.profileOnly')
    for (const k of ['review', 'see_all', 'qc', 'spending', 'payments_prepare', 'payments_check', 'payments_approve']) {
      keys.add(`admin.perm.${k}.name`)
    }
    for (const key of keys) expect(typeof resolve(msgs, key)).toBe('string')
  })
})

describe('the first-sign-in HOLD stays Reviewer-ROLE only (owner ruling 2026-10-31)', () => {
  // ⚠ Pinned on purpose: `review` widens the CARDS, never the hold. An org admin or admin given
  // `review` with an empty profile must never be locked out of the console by a missing field.
  it.each(['admin', 'org_admin', 'qc', 'finance'])('%s holding `review` is never held', (role) => {
    const r = { role, permissions: [...PRESET[role], 'review'], reviewer_profile_complete: false }
    expect(mustCompleteProfile(r, '/admin/scholarship')).toBe(false)
    expect(adminLanding(r)).not.toBe('/admin/profile')
  })

  it('a Reviewer with an incomplete profile still is', () => {
    const r = { role: 'reviewer', permissions: ['review'], reviewer_profile_complete: false }
    expect(mustCompleteProfile(r, '/admin/scholarship')).toBe(true)
    expect(adminLanding(r)).toBe('/admin/profile')
  })
})
