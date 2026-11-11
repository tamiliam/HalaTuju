/**
 * @jest-environment jsdom
 *
 * Sprint M2a (owner U2–U5, 2026-11-11): the split itself. A person in two groups has two pages, each with
 * only its own group's parts and About on all of them (U2, U3); the header chips link to the person's OTHER
 * group pages the viewer may open (U4); a group page opened for somebody not in that group replaces itself
 * with their first group page, or the Staff tab when they are in none (item 6, U5).
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import AdminGroupPage from './AdminGroupPage'
import ReviewerGroupPage from './ReviewerGroupPage'
import MentorGroupPage from './MentorGroupPage'
import * as admins from '@/lib/admin-api/admins'
import * as mentors from '@/lib/admin-api/mentors'
import * as reviewers from '@/lib/admin-api/reviewers'
import { mentorDetail, mentorRow, person, reviewerDetail, staffView } from '@/test/teamPerson'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) =>
    <a href={href} {...rest}>{children}</a>,
}))
const mockReplace = jest.fn()
jest.mock('next/navigation', () => ({ useRouter: () => ({ push: jest.fn(), replace: mockReplace }) }))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({ t: (k: string, v?: Record<string, string>) => (v ? `${k} ${JSON.stringify(v)}` : k) }),
}))
let viewer: { role: string; is_super_admin?: boolean } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: viewer }) }))
jest.mock('@/lib/admin-api/admins')
jest.mock('@/lib/admin-api/mentors')
jest.mock('@/lib/admin-api/reviewers')
const mA = admins as jest.Mocked<typeof admins>
const mM = mentors as jest.Mocked<typeof mentors>
const mR = reviewers as jest.Mocked<typeof reviewers>

beforeEach(() => {
  jest.clearAllMocks()
  viewer = { role: 'org_admin' }
  window.history.replaceState(null, '', '/')
})

const header = () => waitFor(() => expect(screen.getByTestId('person-header')).toBeTruthy())
const chipHrefs = () => Object.fromEntries(within(screen.getByTestId('person-tables')).queryAllByRole('link')
  .map((a) => [a.getAttribute('data-testid'), a.getAttribute('href')]))
const current = () => within(screen.getByTestId('person-tables')).getByText(/admin\.team\.chip\./, {
  selector: '[aria-current="page"]' }).textContent

// An Admin who also reviews and mentors: three pages, one per group.
const ALL_THREE = person({ admin_id: 2, mentor_id: 4, name: 'Meena Example', email: 'meena@example.test',
  tables: ['admins', 'reviewers', 'mentors'] })

describe('U2: each group page draws only its own parts; About on all three (U3)', () => {
  it('the admin page: no figures, no Covers, no Pause, no Outcomes; the Admins permissions only', async () => {
    mA.getStaffPermissions.mockResolvedValue(staffView(ALL_THREE))
    render(<AdminGroupPage id={2} />)
    await header()
    expect(mR.getReviewerDetail).not.toHaveBeenCalled()
    expect(mM.getMentorDetail).not.toHaveBeenCalled()
    for (const id of ['reviewer-figures', 'reviewer-outcomes', 'reviewer-reopens', 'mentor-figures', 'mentor-work',
      'person-action-row']) {
      expect(screen.queryByTestId(id)).toBeNull()
    }
    expect(screen.queryByText('admin.reviewers.detail.giftLabel')).toBeNull()
    expect(screen.queryByText('admin.reviewers.detail.pause')).toBeNull()
    expect(screen.getByTestId('person-profile')).toBeTruthy()
  })

  it('the reviewer page: figures, Covers, Pause and Outcomes; no mentor parts; no Admins permissions', async () => {
    mR.getReviewerDetail.mockResolvedValue(reviewerDetail(ALL_THREE, {
      programmes: [{ id: 1, name: 'Gift A' }, { id: 2, name: 'Gift B' }] }))
    mA.getStaffPermissions.mockResolvedValue(staffView(ALL_THREE, { permissions: ['see_all', 'review'] }))
    window.history.replaceState(null, '', '/x#permissions')
    render(<ReviewerGroupPage id={2} />)
    await header()
    expect(mM.getMentorDetail).not.toHaveBeenCalled()
    expect(screen.getByTestId('reviewer-figures')).toBeTruthy()
    expect(screen.getByText('admin.reviewers.detail.giftLabel')).toBeTruthy()
    expect(screen.getByText('admin.reviewers.detail.pause')).toBeTruthy()
    expect(screen.queryByTestId('mentor-figures')).toBeNull()
    expect(await screen.findByTestId('perm-section-reviewers')).toBeTruthy()
    expect(screen.queryByTestId('perm-section-admins')).toBeNull()
  })

  it('the mentor page: mentor figures and scholars, About; no reviewer parts, no Permissions tab', async () => {
    mM.getMentorDetail.mockResolvedValue(mentorDetail(ALL_THREE, { mentor: mentorRow({ id: 4, staff_role: 'admin' }) }))
    render(<MentorGroupPage id={4} />)
    await header()
    expect(await screen.findByTestId('mentor-work')).toBeTruthy()
    expect(screen.getByTestId('mentor-figures')).toBeTruthy()
    expect(screen.getByTestId('person-profile')).toBeTruthy()
    expect(screen.queryByTestId('reviewer-outcomes')).toBeNull()
    expect(screen.queryAllByRole('tab')).toHaveLength(0)
    expect(mR.getReviewerDetail).not.toHaveBeenCalled()
    expect(mA.getStaffPermissions).not.toHaveBeenCalled()
  })
})

describe('U4: the header chips link to the person\'s other group pages', () => {
  it('links the other groups; the current chip is plain with aria-current', async () => {
    mR.getReviewerDetail.mockResolvedValue(reviewerDetail(ALL_THREE))
    render(<ReviewerGroupPage id={2} />)
    await header()
    expect(chipHrefs()).toEqual({
      'chip-link-admins': '/admin/organisation/team/admins/2',
      'chip-link-mentors': '/admin/organisation/team/mentors/4',
    })
    expect(current()).toBe('admin.team.chip.reviewers')
  })

  it('the admin page links Reviewers by the staff id and Mentors by the mentor id', async () => {
    mA.getStaffPermissions.mockResolvedValue(staffView(ALL_THREE))
    render(<AdminGroupPage id={2} />)
    await header()
    expect(chipHrefs()).toEqual({
      'chip-link-reviewers': '/admin/organisation/team/reviewers/2',
      'chip-link-mentors': '/admin/organisation/team/mentors/4',
    })
    expect(current()).toBe('admin.team.chip.admins')
  })

  it('a viewer who may not open a group\'s page sees that chip plain (an `admin` reader: no admin page)', async () => {
    viewer = { role: 'admin' }
    mR.getReviewerDetail.mockResolvedValue(reviewerDetail(ALL_THREE))
    render(<ReviewerGroupPage id={2} />)
    await header()
    expect(chipHrefs()).toEqual({ 'chip-link-mentors': '/admin/organisation/team/mentors/4' })
  })

  it('a `finance` reader: neither the admin nor the mentor page, so no chip links', async () => {
    viewer = { role: 'finance' }
    mR.getReviewerDetail.mockResolvedValue(reviewerDetail(ALL_THREE))
    render(<ReviewerGroupPage id={2} />)
    await header()
    expect(chipHrefs()).toEqual({})
  })

  it('a mentor chip without a mentor id stays plain', async () => {
    mR.getReviewerDetail.mockResolvedValue(reviewerDetail({ ...ALL_THREE, mentor_id: null }))
    render(<ReviewerGroupPage id={2} />)
    await header()
    expect(chipHrefs()).toEqual({ 'chip-link-admins': '/admin/organisation/team/admins/2' })
  })
})

describe('item 6: the wrong group replaces itself', () => {
  it('a reviewer-only person at the admin page goes to their reviewer page, drawing nothing meanwhile', async () => {
    mA.getStaffPermissions.mockResolvedValue(staffView(person({ tables: ['reviewers'] })))
    render(<AdminGroupPage id={5} />)
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith('/admin/organisation/team/reviewers/5'))
    expect(screen.queryByTestId('person-header')).toBeNull()
  })

  it('keeps #permissions', async () => {
    window.history.replaceState(null, '', '/x?table=reviewers#permissions')
    mA.getStaffPermissions.mockResolvedValue(staffView(person({ tables: ['reviewers'] })))
    render(<AdminGroupPage id={5} />)
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith('/admin/organisation/team/reviewers/5#permissions'))
  })

  it('somebody in no group goes to the Staff tab (U5)', async () => {
    mA.getStaffPermissions.mockResolvedValue(staffView(person({ tables: [] })))
    render(<AdminGroupPage id={5} />)
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith('/admin/organisation/team?tab=staff'))
  })

  it('a person in the page\'s group stays', async () => {
    mR.getReviewerDetail.mockResolvedValue(reviewerDetail(person()))
    render(<ReviewerGroupPage id={5} />)
    await header()
    expect(mockReplace).not.toHaveBeenCalled()
  })
})
