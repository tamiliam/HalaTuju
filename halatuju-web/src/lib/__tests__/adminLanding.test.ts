import { adminLanding, mustCompleteProfile } from '@/lib/adminLanding'
import { defaultRoute, ROLE_NAMES } from '@/lib/navigation'
import { missingReviewerFields, reviewerProfileComplete } from '@/lib/reviewerProfile'
import type { ReviewerProfile } from '@/lib/admin-api'

const full: ReviewerProfile = {
  highest_qualification: 'Degree', university: 'UM', graduation_year: 2015,
  field_of_study: 'Engineering', phone: '+60123', address: '',
  street_address: '', postcode: '', city: '', state: '',
  english_fluency: 'fluent', bm_fluency: '', tamil_fluency: '',
  share_phone_with_students: true,
  paused: false,
}

describe('adminLanding', () => {
  // ⚠ `admin` MOVED, AND THAT IS THE POINT OF THE 2026-09-08 CHANGE. `/admin` is the PLATFORM
  // dashboard (super + partner); an `admin` never belonged there and was bounced off it to a page
  // chosen for somebody else. It now lands on its organisation's own Overview. `defaultRoute` in
  // navigation.test.ts pins the whole table; this file only proves the delegation is real.
  it('sends a super to the platform dashboard, an admin to their organisation', () => {
    expect(adminLanding({ role: 'super' })).toBe('/admin')
    expect(adminLanding({ role: 'admin' })).toBe('/admin/organisation')
  })
  it('sends a viewer + a complete reviewer to the workspace', () => {
    expect(adminLanding({ role: 'viewer' })).toBe('/admin/scholarship')
    expect(adminLanding({ role: 'reviewer', reviewer_profile_complete: true })).toBe('/admin/scholarship')
  })
  it('holds an incomplete reviewer on the profile page', () => {
    expect(adminLanding({ role: 'reviewer', reviewer_profile_complete: false })).toBe('/admin/profile')
  })
  it('never traps on an OLD payload that omits the flag (undefined ≠ false)', () => {
    expect(adminLanding({ role: 'reviewer' })).toBe('/admin/scholarship')
  })

  // ⚠ THE DOCSTRING CLAIMED THIS FOR MONTHS AND IT WAS NOT TRUE — `adminLanding` held its own
  // hand-copied copy of the three lines, and they agreed only because nobody had edited either.
  // Deriving the route from the registry is exactly the change that would have split them.
  it('is the SAME function as defaultRoute, not a second copy of the rule', () => {
    for (const r of [...ROLE_NAMES, 'viewer', 'nonsense'] as const) {
      expect(adminLanding({ role: r })).toBe(defaultRoute({ role: r }))
    }
    expect(adminLanding({ role: 'reviewer', reviewer_profile_complete: false }))
      .toBe(defaultRoute({ role: 'reviewer' }, false))
  })
})

describe('mustCompleteProfile', () => {
  const incomplete = { role: 'reviewer', reviewer_profile_complete: false }
  it('bounces an incomplete reviewer off a normal admin page', () => {
    expect(mustCompleteProfile(incomplete, '/admin/scholarship')).toBe(true)
    expect(mustCompleteProfile(incomplete, '/admin/scholarship/12')).toBe(true)
  })
  it('does NOT bounce from the profile / set-password / auth / login pages (no loop)', () => {
    for (const p of ['/admin/profile', '/admin/set-password', '/admin/auth/callback', '/admin/login']) {
      expect(mustCompleteProfile(incomplete, p)).toBe(false)
    }
  })
  it('leaves everyone else alone', () => {
    expect(mustCompleteProfile({ role: 'reviewer', reviewer_profile_complete: true }, '/admin/scholarship')).toBe(false)
    expect(mustCompleteProfile({ role: 'viewer' }, '/admin/scholarship')).toBe(false)
    expect(mustCompleteProfile({ role: 'super' }, '/admin/scholarship')).toBe(false)
    expect(mustCompleteProfile(null, '/admin/scholarship')).toBe(false)
  })
})

describe('missingReviewerFields (client mirror)', () => {
  it('is empty when fully filled', () => {
    expect(missingReviewerFields('Kanes', full)).toEqual([])
    expect(reviewerProfileComplete('Kanes', full)).toBe(true)
  })
  it('flags a blank name', () => {
    expect(missingReviewerFields('', full)).toContain('name')
  })
  it('flags every missing credential + phone', () => {
    for (const [k, patch] of [
      ['highest_qualification', { highest_qualification: '' }],
      ['university', { university: '' }],
      ['graduation_year', { graduation_year: null }],
      ['field_of_study', { field_of_study: '' }],
      ['phone', { phone: '' }],
    ] as const) {
      expect(missingReviewerFields('Kanes', { ...full, ...patch })).toContain(k)
    }
  })
  it('flags languages only when none is conversational/fluent', () => {
    const none = { ...full, english_fluency: '' as const, bm_fluency: '' as const, tamil_fluency: '' as const }
    expect(missingReviewerFields('Kanes', none)).toContain('languages')
    const one = { ...none, tamil_fluency: 'conversational' as const }
    expect(missingReviewerFields('Kanes', one)).not.toContain('languages')
  })
  it('a null profile is entirely incomplete', () => {
    expect(reviewerProfileComplete('Kanes', null)).toBe(false)
  })
})
