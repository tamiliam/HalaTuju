/**
 * Sprint M2a (U1, U4, U5): the Team addresses — each group's page, the first page in the order Admins,
 * Reviewers, Mentors, the wrong-group replace and the header chips' links.
 */
import { chipLinks, firstGroupPage, groupPageHref, teamTabHref, wrongGroupTarget } from '@/lib/teamPaths'

const ALL = { admins: true, reviewers: true, mentors: true }

describe('groupPageHref', () => {
  it('admins and reviewers by the staff id, mentors by the mentor record id', () => {
    const ids = { admin_id: 5, mentor_id: 3 }
    expect(groupPageHref('admins', ids)).toBe('/admin/organisation/team/admins/5')
    expect(groupPageHref('reviewers', ids)).toBe('/admin/organisation/team/reviewers/5')
    expect(groupPageHref('mentors', ids)).toBe('/admin/organisation/team/mentors/3')
  })

  it('no id, no page', () => {
    expect(groupPageHref('mentors', { admin_id: 5, mentor_id: null })).toBeNull()
    expect(groupPageHref('admins', { mentor_id: 3 })).toBeNull()
  })

  it('a tab address', () => {
    expect(teamTabHref('staff')).toBe('/admin/organisation/team?tab=staff')
    expect(teamTabHref('mentors')).toBe('/admin/organisation/team?tab=mentors')
  })
})

describe('firstGroupPage: Admins, then Reviewers, then Mentors', () => {
  it.each([
    [['reviewers', 'admins'], '/admin/organisation/team/admins/5'],
    [['mentors', 'reviewers'], '/admin/organisation/team/reviewers/5'],
    [['mentors'], '/admin/organisation/team/mentors/3'],
  ])('%p → %s', (tables, href) => {
    expect(firstGroupPage(tables, { admin_id: 5, mentor_id: 3 })).toBe(href)
  })

  it('in no group: no page (U5)', () => {
    expect(firstGroupPage([], { admin_id: 5 })).toBeNull()
    expect(firstGroupPage(undefined, { admin_id: 5 })).toBeNull()
  })

  it('skips a group it has no id for', () => {
    expect(firstGroupPage(['mentors'], { admin_id: 5, mentor_id: null })).toBeNull()
  })
})

describe('wrongGroupTarget', () => {
  const TWO_GROUPS = { admin_id: 2, mentor_id: null, tables: ['admins', 'reviewers'] }

  it('stays when the person is in the page\'s group', () => {
    expect(wrongGroupTarget('reviewers', TWO_GROUPS, '')).toBeNull()
    expect(wrongGroupTarget('admins', TWO_GROUPS, '#permissions')).toBeNull()
  })

  it('a reviewer-only person at the admin page goes to their reviewer page', () => {
    expect(wrongGroupTarget('admins', { admin_id: 5, tables: ['reviewers'] }, ''))
      .toBe('/admin/organisation/team/reviewers/5')
  })

  it('keeps #permissions and nothing else', () => {
    expect(wrongGroupTarget('mentors', TWO_GROUPS, '#permissions')).toBe('/admin/organisation/team/admins/2#permissions')
    expect(wrongGroupTarget('mentors', TWO_GROUPS, '#other')).toBe('/admin/organisation/team/admins/2')
  })

  it('a pure mentor at the reviewer page goes to the mentor page by mentor id', () => {
    expect(wrongGroupTarget('reviewers', { admin_id: 9, mentor_id: 3, tables: ['mentors'] }, ''))
      .toBe('/admin/organisation/team/mentors/3')
  })

  it('in no group: the Staff tab (U5)', () => {
    expect(wrongGroupTarget('admins', { admin_id: 7, tables: [] }, '#permissions'))
      .toBe('/admin/organisation/team?tab=staff')
  })

  // Lead's review of M2a (2026-11-12, the 2026-09-09 ruling: a closed account's record still OPENS). The
  // server serves `tables: []` for any inactive login, so the rule must not read that as "in no group".
  it('never moves a revoked or suspended person: their page opens as it did before M2a', () => {
    expect(wrongGroupTarget('reviewers', { admin_id: 5, tables: [], is_active: false }, '')).toBeNull()
    expect(wrongGroupTarget('mentors', { admin_id: 9, mentor_id: null, tables: [], is_active: false }, '')).toBeNull()
    expect(wrongGroupTarget('admins', { admin_id: 5, tables: ['reviewers'], is_active: false }, '#permissions'))
      .toBeNull()
  })

  it('an ACTIVE person in no group still goes to Staff (U5)', () => {
    expect(wrongGroupTarget('reviewers', { admin_id: 5, tables: [], is_active: true }, ''))
      .toBe('/admin/organisation/team?tab=staff')
  })
})

describe('chipLinks (U4)', () => {
  const EVERYWHERE = { admin_id: 2, mentor_id: 3, tables: ['admins', 'reviewers', 'mentors'] }

  it('links the OTHER groups only; the current chip is not a link', () => {
    expect(chipLinks(EVERYWHERE, 'reviewers', ALL)).toEqual({
      admins: '/admin/organisation/team/admins/2',
      mentors: '/admin/organisation/team/mentors/3',
    })
  })

  it('a group the viewer may not open stays plain', () => {
    expect(chipLinks(EVERYWHERE, 'reviewers', { ...ALL, admins: false, mentors: false })).toEqual({})
  })

  it('a mentor chip without a mentor id stays plain', () => {
    expect(chipLinks({ ...EVERYWHERE, mentor_id: null }, 'admins', ALL)).toEqual({
      reviewers: '/admin/organisation/team/reviewers/2',
    })
  })

  it('never links a group the person is not in', () => {
    expect(chipLinks({ admin_id: 2, mentor_id: 3, tables: ['admins'] }, 'admins', ALL)).toEqual({})
  })
})
