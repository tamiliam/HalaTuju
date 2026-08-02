/**
 * @jest-environment jsdom
 *
 * One reviewer, rendered (request #10, 2026-08-02).
 *
 * The block that matters most is the reopens list. A reopened decision is not by itself a mistake
 * by the reviewer — several of BrightPath's were caused by our own defects — so the reason
 * recorded at the time must appear with every entry, and a bare total must not appear at all.
 */
import { render, screen, waitFor } from '@testing-library/react'
import AdminReviewerDetailPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
jest.mock('next/navigation', () => ({ useParams: () => ({ id: '5' }) }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
let viewerRole: { role: string; is_super_admin?: boolean } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: viewerRole }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const DETAIL = {
  id: 5, name: 'Kavitha Raman', email: 'kavitha@example.org', role: 'reviewer',
  languages: ['ta', 'en'], open_now: 3, completed: 12, turnaround_days: 4.5, paused: false,
  decided_by_other: 2, progressed: 9, declined: 3,
  created_at: '2026-03-01T00:00:00Z',
  qualification: 'MSc', university: 'Universiti Malaya', graduation_year: 2014,
  field_of_study: 'Physics',
  phone: '012-3456789', share_phone_with_students: false,
  reopens: [
    {
      id: 21, application_id: 88, reopened_by: 'tamiliam@gmail.com',
      reason: 'The pathway engine mis-read an STPM announcement as the offer letter.',
      at: '2026-07-11T00:00:00Z',
    },
  ],
} as unknown as api.AdminReviewerDetail

beforeEach(() => {
  jest.clearAllMocks()
  viewerRole = { role: 'org_admin' }
  mockApi.getReviewerDetail.mockResolvedValue(DETAIL)
})

const loaded = async (over: Partial<api.AdminReviewerDetail> = {}) => {
  mockApi.getReviewerDetail.mockResolvedValue({ ...DETAIL, ...over } as api.AdminReviewerDetail)
  render(<AdminReviewerDetailPage />)
  await waitFor(() => expect(screen.getByText('admin.reviewers.detail.workload')).toBeTruthy())
}

describe('the reopens block — the reason this page exists', () => {
  it('shows the reason recorded at the time, with every entry', async () => {
    await loaded()
    expect(screen.getByText(
      'The pathway engine mis-read an STPM announcement as the offer letter.')).toBeTruthy()
    expect(screen.getByText('admin.reviewers.detail.application').closest('a')!
      .getAttribute('href')).toBe('/admin/scholarship/88')
  })

  it('carries the caveat that a reopen is not by itself the reviewer\'s mistake', async () => {
    await loaded()
    expect(screen.getByText('admin.reviewers.detail.reopensNote')).toBeTruthy()
  })

  it('says so plainly when a reviewer has none', async () => {
    await loaded({ reopens: [] })
    expect(screen.getByText('admin.reviewers.detail.noReopens')).toBeTruthy()
  })
})

describe('the PII ruling, rendered', () => {
  it('shows the phone AND says it is staff-only when consent was withheld', async () => {
    await loaded()
    expect(screen.getByText('012-3456789')).toBeTruthy()
    expect(screen.getByText('admin.reviewers.detail.phone_staff_only')).toBeTruthy()
    expect(screen.queryByText('admin.reviewers.detail.phone_shared')).toBeNull()
  })

  it('says a number may reach students when the reviewer agreed to that', async () => {
    await loaded({ share_phone_with_students: true })
    expect(screen.getByText('admin.reviewers.detail.phone_shared')).toBeTruthy()
  })

  it('never renders a home address, even if one arrives in the payload', async () => {
    // The backend does not serialise it, and a test there asserts that. This is the other half of
    // the guard: the page draws named fields, never whatever the payload happens to carry — so a
    // future backend slip cannot leak an address through this screen.
    await loaded({ street_address: '12 Jalan Rahmat' } as unknown as Partial<api.AdminReviewerDetail>)
    expect(document.body.innerHTML).not.toMatch(/Jalan Rahmat/)
    expect(document.body.innerHTML).not.toMatch(/address/i)
  })
})

describe('the outcome bar', () => {
  it('states cases decided by somebody else separately, not inside the bar', async () => {
    await loaded()
    expect(screen.getByText('admin.reviewers.detail.decidedByOther')).toBeTruthy()
    // The counts sit beside their labels: 9 progressed + 3 declined = the 12 completed, and the
    // 2 decided by somebody else are named separately rather than folded in.
    expect(screen.getByText(/detail\.progressed/).textContent).toContain('9')
    expect(screen.getByText(/detail\.declined/).textContent).toContain('3')
  })

  it('draws no bar at all when nothing was decided', async () => {
    await loaded({ progressed: 0, declined: 0, completed: 0, decided_by_other: 0 })
    expect(screen.getByText('admin.reviewers.detail.noOutcomes')).toBeTruthy()
  })
})

describe('the honest empty states', () => {
  it('says "no reviews yet" instead of a turnaround of zero', async () => {
    await loaded({ turnaround_days: null })
    expect(screen.getByText('admin.reviewers.noTurnaround')).toBeTruthy()
  })

  it('drops the credential rows a reviewer never filled in', async () => {
    await loaded({ qualification: '', university: '', graduation_year: null, field_of_study: '' })
    expect(screen.getByText('admin.reviewers.detail.noCredentials')).toBeTruthy()
    expect(screen.queryByText('admin.reviewers.detail.university')).toBeNull()
  })

  it('says nothing has ever been assigned when that is the case', async () => {
    await loaded({ open_now: 0, completed: 0, decided_by_other: 0 })
    expect(screen.getByText('admin.reviewers.detail.noHistory')).toBeTruthy()
  })
})

describe('the role gate and failure', () => {
  it('refuses a reviewer looking at a colleague', async () => {
    viewerRole = { role: 'reviewer' }
    render(<AdminReviewerDetailPage />)
    await waitFor(() => expect(screen.getByText('apiErrors.superAdminRequired')).toBeTruthy())
    expect(screen.queryByText('Kavitha Raman')).toBeNull()
  })

  it('shows an error rather than a half-empty record when the fetch fails', async () => {
    mockApi.getReviewerDetail.mockRejectedValue(new Error('boom'))
    render(<AdminReviewerDetailPage />)
    await waitFor(() =>
      expect(screen.getByText('admin.reviewers.detail.loadFailed')).toBeTruthy())
    expect(screen.queryByText('admin.reviewers.detail.workload')).toBeNull()
  })

  it('links back to the list it came from', async () => {
    await loaded()
    expect(screen.getByText('← admin.reviewers.detail.back').closest('a')!
      .getAttribute('href')).toBe('/admin/organisation/reviewers')
  })
})
