/**
 * Role-aware manual — visibility, landing, anchor integrity, FAQ filtering.
 * Pure helpers only (no rendering); guards the role→content contract against drift.
 */
import {
  CHAPTERS, visibleChapters, defaultChapterSlug, resolveTarget, manualRole,
  type ManualRole,
} from '../index'
import {
  FAQ, defaultFaqAudiences, canSeeAllFaq, ALL_FAQ_AUDIENCES, type QA,
} from '../faq'
import type { Audience } from '../types'

const ROLE_CHAPTERS = ['role-reviewer', 'role-qc', 'role-org-admin', 'role-admin-general',
                       'role-finance']
const slugs = (role: ManualRole | undefined) => visibleChapters(role).map((c) => c.slug)

describe('chapter visibility per role', () => {
  test('basics + help are always visible', () => {
    for (const r of [undefined, 'reviewer', 'qc', 'org_admin', 'admin', 'finance', 'super'] as (ManualRole | undefined)[]) {
      const s = slugs(r)
      expect(s).toEqual(expect.arrayContaining([
        'basics-programme', 'basics-four-checks', 'basics-statuses', 'basics-confidentiality', 'help-getting-help',
      ]))
    }
  })

  test('a single-role staff sees ONLY their own role chapter', () => {
    expect(slugs('reviewer')).toContain('role-reviewer')
    expect(slugs('reviewer')).not.toContain('role-qc')
    expect(slugs('reviewer')).not.toContain('role-org-admin')
    expect(slugs('qc')).toEqual(expect.arrayContaining(['role-qc']))
    expect(slugs('qc')).not.toContain('role-reviewer')
    expect(slugs('admin')).toContain('role-admin-general')
    expect(slugs('admin')).not.toContain('role-qc')
    // Finance is a single-role staff member like the rest — its chapter and nobody else's.
    expect(slugs('finance')).toContain('role-finance')
    expect(slugs('finance')).not.toContain('role-reviewer')
    expect(slugs('finance')).not.toContain('role-org-admin')
    expect(slugs('reviewer')).not.toContain('role-finance')
  })

  test('org_admin and super see ALL role chapters', () => {
    for (const r of ['org_admin', 'super'] as ManualRole[]) {
      expect(slugs(r)).toEqual(expect.arrayContaining(ROLE_CHAPTERS))
    }
  })

  test('a partner / unknown role sees no role chapter', () => {
    expect(manualRole({ role: 'partner' })).toBeUndefined()
    for (const rc of ROLE_CHAPTERS) expect(slugs(undefined)).not.toContain(rc)
  })
})

describe('default landing chapter', () => {
  test.each([
    ['reviewer', 'role-reviewer'],
    ['qc', 'role-qc'],
    ['org_admin', 'role-org-admin'],
    ['admin', 'role-admin-general'],
  ] as [ManualRole, string][])('%s lands on its own chapter', (role, slug) => {
    expect(defaultChapterSlug(role)).toBe(slug)
  })

  test('super and unknown land on the first Basics chapter', () => {
    expect(defaultChapterSlug('super')).toBe('basics-programme')
    expect(defaultChapterSlug(undefined)).toBe('basics-programme')
  })
})

describe('manualRole normalisation', () => {
  test('is_super_admin flag wins', () => {
    expect(manualRole({ role: 'reviewer', is_super_admin: true })).toBe('super')
    expect(manualRole({ role: 'super' })).toBe('super')
  })
  test('concrete roles pass through, others drop', () => {
    expect(manualRole({ role: 'org_admin' })).toBe('org_admin')
    expect(manualRole({ role: 'partner' })).toBeUndefined()
    expect(manualRole(null)).toBeUndefined()
  })
})

describe('resolveTarget (deep links)', () => {
  test('a visible chapter slug resolves to itself', () => {
    expect(resolveTarget('#role-org-admin', 'org_admin')).toEqual({ slug: 'role-org-admin' })
  })
  test('a visible section anchor resolves to its chapter + anchor', () => {
    expect(resolveTarget('#org-admin-assigning', 'org_admin')).toEqual({
      slug: 'role-org-admin', anchor: 'org-admin-assigning',
    })
  })
  test('a hidden chapter falls back to the default (no anchor, no error)', () => {
    // A reviewer deep-linked to the QC chapter lands on their own chapter instead.
    expect(resolveTarget('#role-qc', 'reviewer')).toEqual({ slug: 'role-reviewer' })
    expect(resolveTarget('#qc-gap-floor', 'reviewer')).toEqual({ slug: 'role-reviewer' })
  })
  test('an empty or unknown hash lands on the default chapter', () => {
    expect(resolveTarget('', 'qc')).toEqual({ slug: 'role-qc' })
    expect(resolveTarget('#nope', 'admin')).toEqual({ slug: 'role-admin-general' })
  })
})

describe('anchor integrity', () => {
  test('chapter slugs are unique', () => {
    const s = CHAPTERS.map((c) => c.slug)
    expect(new Set(s).size).toBe(s.length)
  })
  test('section anchors are unique across the whole manual', () => {
    const anchors = CHAPTERS.flatMap((c) => c.sections.map((x) => x.anchor))
    expect(anchors.every((a) => a && a.length > 0)).toBe(true)
    expect(new Set(anchors).size).toBe(anchors.length)
  })
  test('every chapter (a sidebar link) has at least one rendered section', () => {
    for (const c of CHAPTERS) expect(c.sections.length).toBeGreaterThan(0)
  })
})

describe('FAQ audience filtering', () => {
  test('every audience has at least one Q&A', () => {
    for (const a of ALL_FAQ_AUDIENCES) expect((FAQ[a] as QA[]).length).toBeGreaterThan(0)
  })
  test('default filter = Everyone + own role', () => {
    expect(defaultFaqAudiences('reviewer')).toEqual(['everyone', 'reviewer'])
    expect(defaultFaqAudiences('org_admin')).toEqual(['everyone', 'org_admin'])
    expect(defaultFaqAudiences('admin')).toEqual(['everyone', 'admin'])
  })
  test('super defaults to all audiences', () => {
    expect(defaultFaqAudiences('super') as Audience[]).toEqual(ALL_FAQ_AUDIENCES)
  })
  test('only org_admin and super may widen to All', () => {
    expect(canSeeAllFaq('org_admin')).toBe(true)
    expect(canSeeAllFaq('super')).toBe(true)
    expect(canSeeAllFaq('reviewer')).toBe(false)
    expect(canSeeAllFaq('qc')).toBe(false)
    expect(canSeeAllFaq('admin')).toBe(false)
  })
})
