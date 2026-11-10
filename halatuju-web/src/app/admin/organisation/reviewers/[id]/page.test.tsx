/**
 * @jest-environment jsdom
 *
 * One reviewer, rendered (request #10, 2026-08-02; one person page since Sprint T3, 2026-11-09 — the
 * per-kind T3 checks are in `components/admin/person/TeamPersonPage.test.tsx`).
 *
 * The block that matters most is the reopens list. A reopened decision is not by itself a mistake
 * by the reviewer — several of BrightPath's were caused by our own defects — so the reason
 * recorded at the time must appear with every entry, and a bare total must not appear at all.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import AdminReviewerDetailPage from './page'
import * as api from '@/lib/admin-api'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
let mockParamId = '5'
const mockPush = jest.fn()
jest.mock('next/navigation', () => ({ useParams: () => ({ id: mockParamId }), useRouter: () => ({ push: mockPush }) }))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
let viewerRole: { role: string; is_super_admin?: boolean } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: viewerRole }),
}))
jest.mock('@/lib/admin-api')
// The permission editor has its own request (#39 Sprint 4) and its own test (`PermissionEditor.test.tsx`);
// here only WHETHER the page shows it matters. (T3: it rides in the person page's own chunk.)
jest.mock('@/components/admin/PermissionEditor', () => ({
  __esModule: true,
  default: ({ adminId }: { adminId: number }) => <div data-testid="perm-editor">{adminId}</div>,
}))

const mockApi = api as jest.Mocked<typeof api>

const BASE = {
  id: 5, name: 'Kavitha Raman', email: 'kavitha@example.org', role: 'reviewer',
  languages: ['ta', 'en'], open_now: 3, awaiting_review: 1, interviewing: 2, completed: 12, turnaround_days: 4.5, paused: false, paused_at: null,
  pausable: true,   // T3 review: a payload without it offers no Pause
  recommended: 6, declined: 0, rejected_after_review: 2, awaiting_qc: 0,
  created_at: '2026-03-01T00:00:00Z',
  qualification: 'MSc', university: 'Universiti Malaya', graduation_year: 2014,
  field_of_study: 'Physics',
  phone: '012-3456789', share_phone_with_students: false,
  // [] = every gift, the default. One gift in the choices, so the gift row does not render by
  // default — today's BrightPath shape.
  gifts: [], organisation_id: 1,
  programmes: [{ id: 7, code: 'flagship', name: 'BrightPath Bursary', is_active: true }],
  reopens: [
    {
      id: 21, application_id: 88, reopened_by: 'tamiliam@gmail.com',
      reason: 'The pathway engine mis-read an STPM announcement as the offer letter.',
      at: '2026-07-11T00:00:00Z',
    },
  ],
} as unknown as api.AdminReviewerDetail

/** Sprint T3: the `person` block the server builds from the same record (`staff_person.person_block`). */
const withPerson = (d: api.AdminReviewerDetail): api.AdminReviewerDetail => {
  const r = d as api.AdminReviewerDetail & Record<string, unknown>
  const order = ['en', 'ms', 'ta']
  return {
    ...d,
    person: d.person ?? {
      admin_id: d.id, mentor_id: null, name: d.name, email: d.email, tables: ['reviewers'], lead: !!r.lead,
      mentor_only: false, is_active: r.is_active !== false, paused: !!d.paused, joined_at: String(r.created_at),
      signed_in: true, last_seen_at: '2026-11-01T00:00:00Z',
      profile: {
        job_title: '', about: '', qualification: String(r.qualification ?? ''),
        university: String(r.university ?? ''), field_of_study: String(r.field_of_study ?? ''),
        graduation_year: (r.graduation_year as number | null) ?? null, phone: String(r.phone ?? ''),
        languages: order.filter((c) => ((r.languages as string[]) ?? []).includes(c)),
        other_language: String(r.other_language ?? ''),
      },
    },
  }
}
const DETAIL = withPerson(BASE)

beforeEach(() => {
  jest.clearAllMocks()
  mockParamId = '5'
  viewerRole = { role: 'org_admin' }
  mockApi.getReviewerDetail.mockResolvedValue(DETAIL)
})

const loaded = async (over: Partial<api.AdminReviewerDetail> = {}) => {
  mockApi.getReviewerDetail.mockResolvedValue(withPerson({ ...BASE, ...over } as api.AdminReviewerDetail))
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

describe('languages live here, not on the Team table (owner 2026-11-07)', () => {
  it('lists the interview languages and the optional fourth one by name', async () => {
    await loaded({ other_language: 'Kadazandusun' } as Partial<api.AdminReviewerDetail>)
    expect(screen.getByText('admin.reviewers.colLanguages')).toBeTruthy()
    const line = screen.getByText('admin.reviewers.colLanguages').nextElementSibling!.textContent!
    for (const part of ['admin.reviewers.lang.ta', 'admin.reviewers.lang.en', 'Kadazandusun']) {
      expect(line).toContain(part)
    }
  })
})

describe('the honest empty states', () => {
  it('says "no reviews yet" instead of a turnaround of zero', async () => {
    await loaded({ turnaround_days: null })
    expect(screen.getByText('admin.reviewers.noTurnaround')).toBeTruthy()
  })

  it('T3 (M3): keeps the credential rows a reviewer never filled in, each reading Not given', async () => {
    await loaded({ qualification: '', university: '', graduation_year: null, field_of_study: '' })
    for (const k of ['qualification', 'university', 'graduationYear', 'fieldOfStudy']) {
      expect(screen.getByTestId(`person-field-${k}`).textContent).toBe('admin.reviewers.detail.phoneNone')
    }
    expect(screen.getByText('admin.reviewers.detail.university')).toBeTruthy()
  })

  it('says nothing has ever been assigned when that is the case', async () => {
    await loaded({ open_now: 0, awaiting_review: 0, interviewing: 0, completed: 0 })
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

  it('shows the shared not-found state rather than a half-empty record on a 404',
     async () => {
       // ⚠ The wording moved to `components/admin/RecordState` on 2026-10-05 and
       // `admin.reviewers.detail.loadFailed` was deleted with it: this screen's own sentence
       // named a cause the rejection does not carry — the identical 404 is a reviewer belonging
       // to another organisation, which the fence refuses to admit exists. What this test has
       // always been about is unchanged: not a half-drawn record.
       mockApi.getReviewerDetail.mockRejectedValue(Object.assign(new Error('boom'), { status: 404 }))
       render(<AdminReviewerDetailPage />)
       await waitFor(() => expect(screen.getByTestId('record-not-found')).toBeTruthy())
       expect(screen.queryByText('admin.reviewers.detail.outcomes')).toBeNull()
     })

  it('says the page could not load — not "not found" — when the fetch fails otherwise (T3 review)',
     async () => {
       // Neutral either way: it names no cause, so it leaks nothing the fence keeps back.
       mockApi.getReviewerDetail.mockRejectedValue(new Error('boom'))
       render(<AdminReviewerDetailPage />)
       expect((await screen.findByRole('alert')).textContent).toBe('admin.person.loadFailed')
       expect(screen.queryByTestId('record-not-found')).toBeNull()
       expect(screen.queryByText('admin.reviewers.detail.outcomes')).toBeNull()
     })

  it('says not found, never loads for ever, for an address that is not a number', async () => {
    // `reviewers/admins` with no id falls through to this page (2026-10-22).
    mockParamId = 'admins'
    render(<AdminReviewerDetailPage />)
    await waitFor(() => expect(screen.getByTestId('record-not-found')).toBeTruthy())
    expect(mockApi.getReviewerDetail).not.toHaveBeenCalled()
  })

  it('links back to the tab it came from', async () => {
    await loaded()
    expect(screen.getByText('← admin.person.backTo.reviewers').closest('a')!
      .getAttribute('href')).toBe('/admin/organisation/reviewers?tab=reviewers')
  })
})

/**
 * Which gifts a reviewer covers (S-ASSIGN 2026-09-04; MULTI-GIFT, owner design 2026-11-06).
 *
 * Chips, and a pencil that opens a tick list. ⚠ It is a NARROWING, not a fence — it decides who is
 * OFFERED a case; the org boundary is server-side and a reviewer already holding another gift's
 * case keeps it. `[]` = EVERY gift, the default.
 */
describe('which gifts a reviewer covers', () => {
  const TWO_GIFTS = [
    { id: 7, code: 'flagship', name: 'BrightPath Bursary', is_active: true },
    { id: 9, code: 'sabah', name: 'Sabah Bursary', is_active: false },
  ]
  const SABAH = { id: 9, code: 'sabah', name: 'Sabah Bursary' }
  const tick = (id: string) => screen.getByTestId(id) as HTMLInputElement

  it('⚠ says nothing when the organisation runs ONE gift', async () => {
    // Owner, 2026-08-02: with one programme the row could only ever say one thing. That ruling
    // still holds for a one-gift organisation, and this is the fixture's default.
    await loaded()
    expect(screen.queryByText('admin.reviewers.detail.giftLabel')).toBeNull()
  })

  it('shows the gifts once there are two', async () => {
    await loaded({ programmes: TWO_GIFTS, gifts: [SABAH] })
    expect(screen.getByText('admin.reviewers.detail.giftLabel')).toBeTruthy()
    expect(screen.getByTestId('gifts-5').textContent).toBe('Sabah Bursary')
  })

  it('⚠ shows no gifts as the EVERY GIFT chip, never as a blank', async () => {
    await loaded({ programmes: TWO_GIFTS, gifts: [] })
    expect(screen.getByTestId('gifts-5').textContent).toBe('admin.reviewers.gifts.every')
  })

  it('opens the pop-over with Every gift ticked and the gifts greyed', async () => {
    await loaded({ programmes: TWO_GIFTS, gifts: [] })
    fireEvent.click(screen.getByTestId('gifts-edit-5'))
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(tick('gifts-ticks-5-every').checked).toBe(true)
    expect(tick('gifts-ticks-5-gift-7').disabled).toBe(true)
    expect(tick('gifts-ticks-5-gift-9').disabled).toBe(true)
    // A gift that is not switched on yet is still offered — a gift is STAFFED before it opens.
    expect(screen.getByText('admin.reviewers.detail.giftNotOpen')).toBeTruthy()
  })

  it('posts the ticked gifts and patches only that row', async () => {
    mockApi.setReviewerGifts.mockResolvedValue({ id: 5, gifts: [SABAH] })
    await loaded({ programmes: TWO_GIFTS, gifts: [] })
    fireEvent.click(screen.getByTestId('gifts-edit-5'))
    fireEvent.click(tick('gifts-ticks-5-every'))
    expect(tick('gifts-ticks-5-gift-9').disabled).toBe(false)
    fireEvent.click(tick('gifts-ticks-5-gift-9'))
    fireEvent.click(screen.getByTestId('gifts-save-5'))
    await waitFor(() => expect(mockApi.setReviewerGifts).toHaveBeenCalledWith(5, [9], { token: 'tok' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(screen.getByTestId('gifts-5').textContent).toBe('Sabah Bursary')
    // Nothing else on the record moves, so a full re-fetch would only make the page flicker.
    expect(mockApi.getReviewerDetail).toHaveBeenCalledTimes(1)
  })

  it('ticking Every gift clears the gifts and saves an empty list', async () => {
    mockApi.setReviewerGifts.mockResolvedValue({ id: 5, gifts: [] })
    await loaded({ programmes: TWO_GIFTS, gifts: [SABAH] })
    fireEvent.click(screen.getByTestId('gifts-edit-5'))
    expect(tick('gifts-ticks-5-gift-9').checked).toBe(true)
    fireEvent.click(tick('gifts-ticks-5-every'))
    expect(tick('gifts-ticks-5-gift-9').checked).toBe(false)
    expect(tick('gifts-ticks-5-gift-9').disabled).toBe(true)
    fireEvent.click(screen.getByTestId('gifts-save-5'))
    await waitFor(() => expect(mockApi.setReviewerGifts).toHaveBeenCalledWith(5, [], { token: 'tok' }))
  })

  it('clearing the last gift tick puts Every gift back on', async () => {
    await loaded({ programmes: TWO_GIFTS, gifts: [SABAH] })
    fireEvent.click(screen.getByTestId('gifts-edit-5'))
    fireEvent.click(tick('gifts-ticks-5-gift-9'))
    expect(tick('gifts-ticks-5-every').checked).toBe(true)
  })

  it('Cancel closes without saving', async () => {
    await loaded({ programmes: TWO_GIFTS, gifts: [] })
    fireEvent.click(screen.getByTestId('gifts-edit-5'))
    fireEvent.click(tick('gifts-ticks-5-every'))
    fireEvent.click(tick('gifts-ticks-5-gift-7'))
    fireEvent.click(screen.getByText('common.cancel'))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(mockApi.setReviewerGifts).not.toHaveBeenCalled()
    expect(screen.getByTestId('gifts-5').textContent).toBe('admin.reviewers.gifts.every')
  })

  it('⚠ shows a plain admin the gifts as chips, with no way to change them', async () => {
    // Narrower than reading the page, exactly like pause: `admin` and `finance` may look;
    // deciding who gets which work is staff management.
    viewerRole = { role: 'admin' }
    await loaded({ programmes: TWO_GIFTS, gifts: [SABAH] })
    expect(screen.getByText('Sabah Bursary')).toBeTruthy()
    expect(screen.queryByTestId('gifts-edit-5')).toBeNull()
  })

  it('names the failure and keeps the pop-over open', async () => {
    mockApi.setReviewerGifts.mockRejectedValue(new Error('boom'))
    await loaded({ programmes: TWO_GIFTS, gifts: [] })
    fireEvent.click(screen.getByTestId('gifts-edit-5'))
    fireEvent.click(screen.getByTestId('gifts-save-5'))
    await waitFor(() =>
      expect(screen.getByText('admin.reviewers.detail.giftFailed')).toBeTruthy())
    expect(screen.getByRole('dialog')).toBeTruthy()
  })
})

describe('#39 Sprint 4: the permission card, and Pause on the target rule of the server', () => {
  // 2026-10-22 (owner's option A): the card lives on a Permissions TAB, beside Profile.
  afterEach(() => { window.history.replaceState(null, '', '/') })

  it('gives the organisation admin a Profile | Permissions bar, opening on Profile', async () => {
    await loaded()
    const tabs = screen.getAllByRole('tab').map((b) => b.textContent)
    expect(tabs).toEqual(['admin.person.tabProfile', 'admin.person.tabPermissions'])
    expect(screen.queryByTestId('perm-editor')).toBeNull()
    fireEvent.click(screen.getByText('admin.person.tabPermissions'))
    expect(screen.getByTestId('perm-editor').textContent).toBe('5')
    // The Profile content steps aside while the card is open, and the address says which tab.
    expect(screen.queryByText('admin.reviewers.detail.outcomes')).toBeNull()
    expect(window.location.hash).toBe('#permissions')
    fireEvent.click(screen.getByText('admin.person.tabProfile'))
    expect(screen.getByText('admin.reviewers.detail.outcomes')).toBeTruthy()
    expect(window.location.hash).toBe('')
  })

  it('opens straight on Permissions from #permissions', async () => {
    window.history.replaceState(null, '', '/x#permissions')
    mockApi.getReviewerDetail.mockResolvedValue(DETAIL)
    render(<AdminReviewerDetailPage />)
    await waitFor(() => expect(screen.getByTestId('perm-editor')).toBeTruthy())
  })

  it('shows a super the tab too', async () => {
    viewerRole = { role: 'reviewer', is_super_admin: true }
    await loaded()
    fireEvent.click(screen.getByText('admin.person.tabPermissions'))
    expect(screen.getByTestId('perm-editor')).toBeTruthy()
  })

  it('never shows a plain admin or finance the card — their Permissions tab holds one line (Q1)', async () => {
    for (const r of ['admin', 'finance']) {
      window.history.replaceState(null, '', '/x#permissions')     // even when asked by the address
      viewerRole = { role: r }
      const { unmount } = render(<AdminReviewerDetailPage />)
      expect((await screen.findByTestId('person-perm-not-allowed')).textContent).toBe('admin.person.notAllowed')
      expect(screen.queryByTestId('perm-editor')).toBeNull()
      fireEvent.click(screen.getByText('admin.person.tabProfile'))
      expect(screen.getByText('admin.reviewers.detail.outcomes')).toBeTruthy()
      unmount()
    }
  })

  it('offers Pause only where the endpoint takes it (`pausable`)', async () => {
    await loaded({ pausable: false })
    expect(screen.queryByText('admin.reviewers.detail.pause')).toBeNull()
  })

  it('offers Pause to a Finance + Review person the endpoint accepts', async () => {
    await loaded({ role: 'finance', pausable: true })
    expect(screen.getByText('admin.reviewers.detail.pause')).toBeTruthy()
  })
})

/* Mobile M8 follow-up (owner's iPhone, 2026-11-04): four figures in one unwrapped row ran 70 px past the card at
 * 360. Below md they are two by two across the card; from md the row is the one it always was. */
describe('the summary figures on a phone', () => {
  it('are a two-by-two grid below md and the unchanged row from md', async () => {
    await loaded()
    const figures = screen.getByTestId('reviewer-figures').className.split(' ')
    for (const c of ['max-md:grid', 'max-md:grid-cols-2', 'max-md:w-full']) expect(figures).toContain(c)
    for (const c of ['flex', 'gap-6', 'md:gap-8']) expect(figures).toContain(c)
    expect(screen.getByTestId('reviewer-figures').children).toHaveLength(4)
  })
})

describe('M1b (owner O3): Suspend and Delete live on Team -> Staff, not on a reviewer\'s page', () => {
  it('a reviewer with no work: Pause stays, but no Revoke and no Delete', async () => {
    await loaded({ is_active: true, deletable: true, work: {} } as Partial<api.AdminReviewerDetail>)
    expect(screen.queryByText('admin.revoke')).toBeNull()
    expect(screen.queryByText('admin.delete')).toBeNull()
    expect(screen.queryByTestId('staff-delete')).toBeNull()
    expect(screen.queryByTestId('staff-delete-greyed')).toBeNull()
  })

  it('a revoked reviewer reads Revoked, with no Restore here', async () => {
    await loaded({ is_active: false, deletable: false, work: { assigned_applications: 3 } } as Partial<api.AdminReviewerDetail>)
    expect(screen.queryByText('admin.restore')).toBeNull()
  })

  it('O10: an organisation admin sees a fellow organisation admin read-only — no Pause, no action row', async () => {
    await loaded({ role: 'org_admin', lead: true, is_active: true, pausable: true, deletable: true, work: {} } as Partial<api.AdminReviewerDetail>)
    expect(screen.queryByTestId('person-action-row')).toBeNull()
    expect(screen.queryByText('admin.reviewers.detail.pause')).toBeNull()
  })

  it('a super may still Pause that organisation admin, and has no Delete here either', async () => {
    viewerRole = { role: 'reviewer', is_super_admin: true }
    await loaded({ role: 'org_admin', lead: true, is_active: true, pausable: true, deletable: true, work: {} } as Partial<api.AdminReviewerDetail>)
    expect(screen.getByText('admin.reviewers.detail.pause')).toBeTruthy()
    expect(screen.queryByText('admin.delete')).toBeNull()
  })
})
