/**
 * @jest-environment jsdom
 *
 * Sprint M2d A2 (owner, 2026-11-13): on the Team page's own tables — Reviewers and Admins — every heading
 * sorts except Action, with one arrow placement, and "Not recorded" goes last in both directions. The sort
 * rules are `lib/__tests__/teamSort.test.ts`'s; Members, Mentors and Invitations are
 * `components/admin/teamSortHeaders.test.tsx`'s. A new file so `page.test.tsx` (ledgered) does not grow.
 * Synthetic names only.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import AdminTeamPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-auth-context', () => ({ useAdminAuth: () => ({ token: 'tok', role: { role: 'org_admin' } }) }))
jest.mock('@/lib/admin-api')
let tabParam = 'reviewers'
jest.mock('next/navigation', () => ({
  ...jest.requireActual('next/navigation'),
  useSearchParams: () => ({ get: (k: string) => (k === 'tab' ? tabParam : null) }),
}))
jest.mock('@/components/admin/StaffList', () => ({ __esModule: true, default: () => <div /> }))
jest.mock('@/components/mentors/MentorsAdmin', () => ({ __esModule: true, default: () => <div /> }))

const mockApi = api as jest.Mocked<typeof api>

const reviewer = (id: number, name: string, last_seen_at: string | null, awaiting_review = 0) => ({
  id, name, email: `r${id}@example.org`, role: 'reviewer', languages: [], open_now: 0, awaiting_review,
  interviewing: 0, completed: 0, turnaround_days: null, paused: false, paused_at: null, is_active: true,
  last_seen_at, gifts: [], tables: ['reviewers'], manageable: true,
}) as unknown as api.AdminReviewer
const admin = (id: number, name: string, last_seen_at: string | null) => ({
  id, name, email: `a${id}@example.org`, role: 'admin', is_active: true, is_super_admin: false, org_name: null,
  created_at: '2026-01-01T00:00:00Z', manageable: true, tables: ['admins'], lead: false, last_seen_at, remove: {},
}) as unknown as api.AdminItem

// Never seen, out of name order, either side of the two who were.
const REVIEWERS = [reviewer(1, 'Zara Test', null), reviewer(2, 'Old Test', '2026-01-01T00:00:00Z', 2),
  reviewer(3, 'Ana Test', null, 1), reviewer(4, 'New Test', '2026-11-01T00:00:00Z')]
const ADMINS = [admin(11, 'Zara Admin', null), admin(12, 'Old Admin', '2026-01-01T00:00:00Z'),
  admin(13, 'Ana Admin', null), admin(14, 'New Admin', '2026-11-01T00:00:00Z')]

beforeEach(() => {
  jest.clearAllMocks()
  tabParam = 'reviewers'
  mockApi.listReviewers.mockResolvedValue({ reviewers: REVIEWERS, programmes: [] })
  mockApi.getAdmins.mockResolvedValue({ admins: ADMINS })
})

const table = () => document.querySelector('[data-testid="table-scroller"] table') as HTMLElement
const headings = () => Array.from(table().querySelectorAll('thead th')) as HTMLElement[]
const order = () => Array.from(table().querySelectorAll('tbody tr'))
  .map((tr) => ['Zara', 'Old', 'Ana', 'New'].find((n) => tr.textContent?.includes(n)))
const heading = (label: string) => within(table()).getByRole('button', { name: label })

function sortableExceptAction() {
  const ths = headings()
  const action = ths[ths.length - 1]
  expect(action.textContent).toBe('admin.actionHeader')
  expect(action.querySelector('button')).toBeNull()
  for (const th of ths.slice(0, -1)) {
    expect(th.querySelectorAll('button')).toHaveLength(1)
    expect(th.getAttribute('aria-sort')).toMatch(/^(none|ascending|descending)$/)
  }
}

const open = async (tab: string, name: string) => {
  tabParam = tab
  render(<AdminTeamPage />)
  await waitFor(() => expect(within(table()).getAllByText(name).length).toBeGreaterThan(0))
}

describe('Reviewers', () => {
  it('every heading is a sort button except Action', async () => {
    await open('reviewers', 'Zara Test')
    expect(headings()).toHaveLength(9)
    sortableExceptAction()
  })

  it('Last seen: "Not recorded" last both ways, the newest first on the first click', async () => {
    await open('reviewers', 'Zara Test')
    fireEvent.click(heading('admin.reviewers.colLastSeen'))
    expect(order()).toEqual(['New', 'Old', 'Ana', 'Zara'])
    fireEvent.click(heading('admin.reviewers.colLastSeen'))
    expect(order()).toEqual(['Old', 'New', 'Ana', 'Zara'])
  })

  it('a number heading ends where its figures end: right-aligned, the arrow BEFORE the label', async () => {
    await open('reviewers', 'Zara Test')
    // Reviewers opens on Awaiting review (busiest first), so Interviewing is the inactive number heading.
    const button = heading('admin.reviewers.colInterviewing')
    expect(button.closest('th')?.className).toContain('text-right')
    expect(button.className).toContain('justify-end')
    expect(button.querySelector('[aria-hidden]')).toBeNull()   // no arrow while inactive
    fireEvent.click(button)
    expect(button.firstElementChild?.getAttribute('aria-hidden')).not.toBeNull()
    expect(button.textContent).toMatch(/^[▲▼]admin\.reviewers\.colInterviewing$/)
    // A left-aligned heading keeps its arrow after the label.
    fireEvent.click(heading('admin.nameHeader'))
    expect(heading('admin.nameHeader').textContent).toBe('admin.nameHeader▲')
  })
})

describe('Admins', () => {
  it('every heading is a sort button except Action', async () => {
    await open('admins', 'Zara Admin')
    expect(headings().map((th) => th.textContent?.replace(/[▲▼]/g, ''))).toEqual([
      'admin.nameHeader', 'admin.team.colAlsoIn', 'admin.statusHeader', 'admin.reviewers.colLastSeen',
      'admin.actionHeader'])
    sortableExceptAction()
  })

  it('Last seen: "Not recorded" last both ways', async () => {
    await open('admins', 'Zara Admin')
    fireEvent.click(heading('admin.reviewers.colLastSeen'))
    expect(order()).toEqual(['New', 'Old', 'Ana', 'Zara'])
    fireEvent.click(heading('admin.reviewers.colLastSeen'))
    expect(order()).toEqual(['Old', 'New', 'Ana', 'Zara'])
    expect(screen.getAllByText('Ana Admin').length).toBeGreaterThan(0)
  })
})
