/**
 * @jest-environment jsdom
 *
 * One reviewer, rendered (request #10, 2026-08-02).
 *
 * The block that matters most is the reopens list. A reopened decision is not by itself a mistake
 * by the reviewer — several of BrightPath's were caused by our own defects — so the reason
 * recorded at the time must appear with every entry, and a bare total must not appear at all.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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
  languages: ['ta', 'en'], open_now: 3, completed: 12, turnaround_days: 4.5, paused: false, paused_at: null,
  recommended: 6, declined: 0, rejected_after_review: 2, awaiting_qc: 0,
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
  await waitFor(() => expect(screen.getByText('admin.reviewers.detail.outcomes')).toBeTruthy())
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
  it('shows the phone WITH its country code, and says it is staff-only', async () => {
    // Stored as the local part only; +60 is added at read time (see `displayPhone`).
    await loaded()
    expect(screen.getByText(/\+60 12-3456789/)).toBeTruthy()
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
  it('names all four bands, with their counts beside them', async () => {
    await loaded()
    expect(screen.getByText(/detail\.recommended/).textContent).toContain('6')
    expect(screen.getByText(/detail\.declined/).textContent).toContain('0')
    expect(screen.getByText(/detail\.rejectedAfterReview/).textContent).toContain('2')
    expect(screen.getByText(/detail\.awaitingQc/).textContent).toContain('0')
  })

  it('no longer excludes a case somebody else decided, nor footnotes it', async () => {
    // ⚠ Reversed by the owner, 2026-08-02: the excluded case was one the reviewer had genuinely
    // interviewed and written up. The footnote pointed at something nobody could act on.
    await loaded()
    expect(document.body.innerHTML).not.toMatch(/decidedByOther/)
  })

  it('draws no bar at all when nothing was decided', async () => {
    await loaded({
      recommended: 0, declined: 0, rejected_after_review: 0, awaiting_qc: 0, completed: 0,
    })
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
    await loaded({ open_now: 0, completed: 0 })
    expect(screen.getByText('admin.reviewers.detail.noHistory')).toBeTruthy()
  })
})

describe('pause, on somebody else\'s behalf', () => {
  it('offers the control WITHOUT a standing explanation taking up a line', async () => {
    // Owner review, 2026-08-02: the control does not need a box, and for an ACTIVE reviewer the
    // note was a paragraph explaining a link nobody had pressed. The reassurance that this is not
    // a revoke rides on the control itself instead.
    await loaded()
    const button = screen.getByText('admin.reviewers.detail.pause')
    expect(button.getAttribute('title')).toBe('admin.reviewers.detail.pauseNoteActive')
    expect(screen.queryByText('admin.reviewers.detail.pauseNoteActive')).toBeNull()
  })

  it('DOES spell it out once somebody is paused — that is when it tells you something', async () => {
    await loaded({ paused: true, paused_at: '2026-07-30T00:00:00Z' })
    expect(screen.getByText('admin.reviewers.detail.pauseNotePaused')).toBeTruthy()
  })

  it('offers the way BACK for a paused one — never a one-way conversation', async () => {
    await loaded({ paused: true, paused_at: '2026-07-30T00:00:00Z' })
    expect(screen.getByText('admin.reviewers.detail.unpause')).toBeTruthy()
    expect(screen.getByText('admin.reviewers.detail.pauseNotePaused')).toBeTruthy()
    expect(screen.queryByText('admin.reviewers.detail.pause')).toBeNull()
  })

  it('sends the change and flips the control without re-fetching the record', async () => {
    mockApi.setReviewerPaused.mockResolvedValue({
      id: 5, paused: true, paused_at: '2026-08-02T00:00:00Z',
    })
    await loaded()
    fireEvent.click(screen.getByText('admin.reviewers.detail.pause'))
    await waitFor(() => expect(screen.getByText('admin.reviewers.detail.unpause')).toBeTruthy())
    expect(mockApi.setReviewerPaused).toHaveBeenCalledWith(5, true, { token: 'tok' })
    expect(mockApi.getReviewerDetail).toHaveBeenCalledTimes(1)   // no reload — nothing else moved
  })

  it('says so when the change fails, and leaves the control where it was', async () => {
    mockApi.setReviewerPaused.mockRejectedValue(new Error('boom'))
    await loaded()
    fireEvent.click(screen.getByText('admin.reviewers.detail.pause'))
    await waitFor(() => expect(screen.getByText('admin.reviewers.detail.pauseFailed')).toBeTruthy())
    expect(screen.getByText('admin.reviewers.detail.pause')).toBeTruthy()
  })

  it('shows a plain `admin` the record but NOT the control', async () => {
    // Reading the surface and deciding who gets work are different powers; the role matrix gives
    // the second to super + org_admin only, and the endpoint re-gates regardless.
    viewerRole = { role: 'admin' }
    await loaded()
    expect(screen.getByText('Kavitha Raman')).toBeTruthy()
    expect(screen.queryByText('admin.reviewers.detail.pause')).toBeNull()
  })

  it('shows a super the control', async () => {
    viewerRole = { role: 'reviewer', is_super_admin: true }
    await loaded()
    expect(screen.getByText('admin.reviewers.detail.pause')).toBeTruthy()
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
    expect(screen.queryByText('admin.reviewers.detail.outcomes')).toBeNull()
  })

  it('links back to the list it came from', async () => {
    await loaded()
    expect(screen.getByText('← admin.reviewers.detail.back').closest('a')!
      .getAttribute('href')).toBe('/admin/organisation/reviewers')
  })
})
