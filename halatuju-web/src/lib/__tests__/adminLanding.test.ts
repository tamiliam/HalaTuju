import { adminLanding, mustCompleteProfile, outsiderMustLeave } from '@/lib/adminLanding'
import { defaultRoute, ROLE_NAMES } from '@/lib/navigation'
import { missingReviewerFields, reviewerProfileComplete } from '@/lib/reviewerProfile'
import type { ReviewerProfile } from '@/lib/admin-api'

const full: ReviewerProfile = {
  highest_qualification: 'Degree', university: 'UM', graduation_year: 2015,
  field_of_study: 'Engineering', phone: '+60123', address: '',
  street_address: '', postcode: '', city: '', state: '',
  english_fluency: 'fluent', bm_fluency: '', tamil_fluency: '',
  other_language: '', other_language_fluency: '',
  share_phone_with_students: true,
  paused: false,
}

describe('adminLanding', () => {
  // ⚠⚠ T5c P5 (owner, 2026-11-04): EVERYONE ON THE PARTNER LOGIN LANDS ON ORGANISATION → PROGRAMMES — admin,
  // reviewer, mentor alike. It is the first row of the organisation group and every partner-login role may
  // open it, so `defaultRoute` reaches it first. Kept: a super on the platform dashboard, a source user on its
  // Overview, and the incomplete reviewer held on Profile.
  // ⚠ `admin` MOVED, AND THAT IS THE POINT OF THE 2026-09-08 CHANGE. `/admin` is the PLATFORM
  // dashboard (super + partner); an `admin` never belonged there and was bounced off it to a page
  // chosen for somebody else. It now lands on its organisation's own Overview. `defaultRoute` in
  // navigation.test.ts pins the whole table; this file only proves the delegation is real.
  it('sends a super to the platform dashboard, an admin to their organisation', () => {
    expect(adminLanding({ role: 'super' })).toBe('/admin')
    expect(adminLanding({ role: 'admin' })).toBe('/admin/organisation/programmes')
  })
  // ⚠ MOVED 2026-09-15, AND IT IS WANTED. The Programme Overview's reviewer shape IS their own
  // queue — open cases, due soon, overdue, and how long students have waited — so it is nearer
  // their work than a list of every applicant in the gift. `defaultRoute` in navigation.test.ts
  // pins the whole table; this file only proves the delegation is real.
  it('sends a viewer + a complete reviewer to Programmes (T5c P5)', () => {
    expect(adminLanding({ role: 'viewer' })).toBe('/admin/organisation/programmes')
    expect(adminLanding({ role: 'reviewer', reviewer_profile_complete: true }))
      .toBe('/admin/organisation/programmes')
  })
  it('holds an incomplete reviewer on the profile page', () => {
    expect(adminLanding({ role: 'reviewer', reviewer_profile_complete: false })).toBe('/admin/profile')
  })
  it('never traps on an OLD payload that omits the flag (undefined ≠ false)', () => {
    expect(adminLanding({ role: 'reviewer' })).toBe('/admin/organisation/programmes')
  })
  // Source sign-in (2026-10-30): a source user lands on its own Overview — never on a reviewer's
  // landing by fallback, and never held on Profile (the reviewer onboarding gate is not theirs).
  it('sends a source user to its Overview, whatever the reviewer flag says', () => {
    expect(adminLanding({ role: 'source_partner' })).toBe('/admin/programme/overview')
    expect(adminLanding({ role: 'source_partner', reviewer_profile_complete: false }))
      .toBe('/admin/programme/overview')
    expect(mustCompleteProfile({ role: 'source_partner', reviewer_profile_complete: false },
      '/admin/scholarship')).toBe(false)
  })

  // Student maintenance S7a (2026-10-31) gave a mentor Profile; S7c gives My students, and it lands
  // there — never through the reviewer hold, which is not theirs (no hold for an incomplete mentor
  // profile exists today, so none is invented).
  it('sends a mentor to Programmes (T5c P5), and never holds it as a reviewer', () => {
    expect(adminLanding({ role: 'mentor' })).toBe('/admin/organisation/programmes')
    expect(adminLanding({ role: 'mentor', reviewer_profile_complete: true })).toBe('/admin/organisation/programmes')
    expect(adminLanding({ role: 'mentor', reviewer_profile_complete: false })).toBe('/admin/organisation/programmes')
    expect(mustCompleteProfile({ role: 'mentor', reviewer_profile_complete: false }, '/admin/scholarship'))
      .toBe(false)
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

describe('outsiderMustLeave (source users and mentors, S7a)', () => {
  it('sends a mentor away from every page but My students, Scholars and its Profile', () => {
    for (const p of ['/admin', '/admin/organisation/mentors', '/admin/scholarship', '/admin/scholarship/4',
      '/admin/programme/overview', '/admin/guide']) {
      expect(outsiderMustLeave({ role: 'mentor', permissions: [] }, p)).toBe(true)
    }
    // Sprint S1 (S1-h): Scholars, its current students only (the server answers 404 for anyone else's).
    expect(outsiderMustLeave({ role: 'mentor', permissions: [] }, '/admin/scholars')).toBe(false)
    expect(outsiderMustLeave({ role: 'mentor', permissions: [] }, '/admin/scholars/4')).toBe(false)
    expect(outsiderMustLeave({ role: 'mentor', permissions: [] }, '/admin/profile')).toBe(false)
    expect(outsiderMustLeave({ role: 'mentor', permissions: [] }, '/admin/my-students')).toBe(false)
    expect(outsiderMustLeave({ role: 'mentor', permissions: [] }, '/admin/my-students/104')).toBe(false)
  })
  it('sends a member ("No group", M1a) away from every page but its Profile', () => {
    for (const p of ['/admin', '/admin/organisation/programmes', '/admin/scholarship', '/admin/scholars',
      '/admin/my-students', '/admin/programme/overview', '/admin/guide']) {
      expect(outsiderMustLeave({ role: 'member', permissions: [] }, p)).toBe(true)
    }
    expect(outsiderMustLeave({ role: 'member', permissions: [] }, '/admin/profile')).toBe(false)
  })
  it('still holds a source user to its own pages, and never touches staff', () => {
    expect(outsiderMustLeave({ role: 'source_partner', permissions: [] }, '/admin/sources')).toBe(true)
    expect(outsiderMustLeave({ role: 'source_partner', permissions: [] }, '/admin/scholarship')).toBe(false)
    for (const role of ['super', 'org_admin', 'admin', 'reviewer']) {
      expect(outsiderMustLeave({ role, permissions: ['review'] }, '/admin/organisation/mentors')).toBe(false)
    }
    expect(outsiderMustLeave(null, '/admin')).toBe(false)
  })
})
