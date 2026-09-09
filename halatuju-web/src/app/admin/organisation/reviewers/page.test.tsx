/**
 * @jest-environment jsdom
 *
 * The reviewers table, rendered (request #10, 2026-08-02).
 *
 * The pure sort rules have their own tests; these pin what the SCREEN promises — including the two
 * things that must NOT be on it. A column removed by owner decision comes back the moment somebody
 * adds it "for completeness", and only a rendered test notices.
 */
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import AdminReviewersList from './page'
import * as api from '@/lib/admin-api'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
let viewerRole: { role: string; is_super_admin?: boolean } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: viewerRole }),
}))
jest.mock('@/lib/admin-api')

const mockApi = api as jest.Mocked<typeof api>

const REVIEWERS = [
  {
    id: 5, name: 'Kavitha Raman', email: 'kavitha@example.org', role: 'reviewer',
    languages: ['ta', 'en'], open_now: 3, completed: 12, turnaround_days: 4.5, paused: false, paused_at: null,
    is_active: true, last_seen_at: '2026-09-04T09:00:00Z',
  },
  {
    id: 6, name: 'Hafiz Rahman', email: 'hafiz@example.org', role: 'qc',
    languages: [], open_now: 0, completed: 0, turnaround_days: null, paused: false, paused_at: null,
    is_active: true, last_seen_at: null,
  },
] as unknown as api.AdminReviewer[]

/** The organisation's gifts. Only the COUNT matters to this page — the gift line under a name
 *  renders above one, per the ruling at the top of `page.tsx`. */
let giftChoices: api.AdminReviewerGift[] = []

/** The staff behind the Admins tab (2026-09-09). ⚠ Deliberately mixed: an org_admin who is IN, a
 *  finance admin who has been REVOKED, and a reviewer who must NOT appear on this tab — the split
 *  is the owner's two categories, so a reviewer leaking in would mean the tab is the whole staff
 *  list wearing a different name. */
const ADMINS = [
  { id: 11, name: 'Dina Ismail', email: 'dina@example.org', role: 'org_admin',
    is_active: true, is_super_admin: false, org_name: null, created_at: '2026-01-01T00:00:00Z' },
  { id: 12, name: 'Shanti Subramaniam', email: 'shanti@example.org', role: 'finance',
    is_active: false, is_super_admin: false, org_name: null, created_at: '2026-01-01T00:00:00Z' },
  { id: 13, name: 'Kavitha Raman', email: 'kavitha@example.org', role: 'reviewer',
    is_active: true, is_super_admin: false, org_name: null, created_at: '2026-01-01T00:00:00Z' },
] as unknown as api.AdminItem[]

beforeEach(() => {
  jest.clearAllMocks()
  viewerRole = { role: 'org_admin' }
  // One gift by default — today's BrightPath shape, where the gift line does not render.
  giftChoices = [{ id: 7, code: 'flagship', name: 'BrightPath Bursary', is_active: true }]
  mockApi.listReviewers.mockResolvedValue({ reviewers: REVIEWERS, programmes: giftChoices })
  // The Admins tab reads the staff list through `useStaffAdmin`, which loads on mount — the
  // auto-mock must answer it or the hook throws before anything renders.
  mockApi.getAdmins.mockResolvedValue({ admins: ADMINS })
})

/** ⚠ THE SAME ROWS ARE RENDERED TWICE (2026-09-08): once as phone cards, once as the desktop
 *  table. Which one you SEE is a CSS breakpoint, and jsdom applies no breakpoints — so every
 *  query below must say which rendering it means, or `getByText` finds two of everything.
 *
 *  These tests are about the TABLE, so `screen` is replaced by a scoped `ui`. The phone cards
 *  have their own describe at the foot of this file. */
const table = () => document.querySelector('[data-testid="table-scroller"]') as HTMLElement
const ui = () => within(table())
const cards = () => screen.getByTestId('reviewer-cards')

const loaded = async () => {
  render(<AdminReviewersList />)
  await waitFor(() => expect(screen.getAllByText('Kavitha Raman').length).toBeGreaterThan(0))
}

describe('what the table shows', () => {
  it('draws the six columns the surface was approved with', async () => {
    await loaded()
    for (const key of ['colName', 'colRole', 'colLanguages', 'colOpen', 'colCompleted',
      'colTurnaround', 'colStatus']) {
      expect(ui().getByText(`admin.reviewers.${key}`)).toBeTruthy()
    }
  })

  it('opens each reviewer\'s own record from their name', async () => {
    await loaded()
    expect(ui().getByText('Kavitha Raman').closest('a')!.getAttribute('href'))
      .toBe('/admin/organisation/reviewers/5')
  })

  it('names the languages someone can actually interview in', async () => {
    await loaded()
    expect(ui().getByText('admin.reviewers.lang.ta')).toBeTruthy()
    expect(ui().getByText('admin.reviewers.lang.en')).toBeTruthy()
    expect(screen.queryByText('admin.reviewers.lang.ms')).toBeNull()
  })
})

describe('the two figures that lie if you let them', () => {
  /** The turnaround cell of the row whose link points at `/…/<id>`. */
  const turnaroundOf = (id: number) => {
    const row = screen.getAllByRole('row').slice(1).find((r) =>
      r.querySelector('a')!.getAttribute('href')!.endsWith(`/${id}`))!
    return row.querySelectorAll('td')[5].textContent
  }

  it('says "no reviews yet" rather than showing a turnaround of nothing', async () => {
    await loaded()
    // Hafiz has decided nothing. Rendering 0 days would claim he is the fastest reviewer here.
    expect(turnaroundOf(6)).toBe('admin.reviewers.noTurnaround')
  })

  it('renders a real turnaround with its unit', async () => {
    await loaded()
    expect(turnaroundOf(5)).toBe('admin.reviewers.days')
  })
})

describe('what must NOT be on this table', () => {
  it('carries no corrections or reopens column', async () => {
    await loaded()
    // A bare count beside a volunteer's name reads as a competence score. The reopens live on the
    // detail page, each with the reason recorded at the time.
    const html = document.body.innerHTML
    expect(html).not.toMatch(/corrections/i)
    expect(html).not.toMatch(/reopen/i)
  })

  it('carries no programmes column (owner, 2026-08-02)', async () => {
    await loaded()
    // With one programme it could only ever say one thing. It returns when a second exists.
    expect(document.body.innerHTML).not.toMatch(/programme/i)
  })
})

describe('sorting', () => {
  it('arrives sorted by who is carrying the most right now', async () => {
    await loaded()
    const names = screen.getAllByRole('row').slice(1)
      .map((r) => r.querySelector('a')!.textContent)
    expect(names).toEqual(['Kavitha Raman', 'Hafiz Rahman'])
  })

  it('flips a column when its header is clicked, and says so to a screen reader', async () => {
    await loaded()
    const header = screen.getByText('admin.reviewers.colName').closest('th')!
    expect(header.getAttribute('aria-sort')).toBe('none')
    fireEvent.click(screen.getByText('admin.reviewers.colName'))
    await waitFor(() =>
      expect(screen.getByText('admin.reviewers.colName').closest('th')!.getAttribute('aria-sort'))
        .toBe('ascending'))
    const names = screen.getAllByRole('row').slice(1)
      .map((r) => r.querySelector('a')!.textContent)
    expect(names).toEqual(['Hafiz Rahman', 'Kavitha Raman'])
  })
})

describe('the Emails tab', () => {
  const TEMPLATES = [
    {
      kind: 'reviewer_assigned', enabled: true, to_student: false, to_reviewer: true,
      subject: 's', body: 'b', placeholders: ['ref'], updated_by_email: '',
      updated_at: null, last_sent_at: null, last_sent_orgs: 0,
    },
  ] as unknown as api.PartnerEmailTemplate[]

  beforeEach(() => {
    mockApi.getReviewerEmails.mockResolvedValue({
      templates: TEMPLATES, organisations: [], qualifying_count: 0,
      partner_count: 0, comms_enabled: true,
    } as unknown as api.PartnerEmailsPayload)
    // The tab also lists the seven emails nobody can edit. Its own request, so the auto-mock
    // must answer it or the card throws on mount.
    mockApi.getReviewerSystemEmails.mockResolvedValue({ emails: [] })
  })

  it('opens on the reviewers list, not the emails — the list is what the page is for', async () => {
    await loaded()
    expect(screen.queryByText('admin.reviewers.emails.title')).toBeNull()
  })

  it('reveals the five emails on the second click, and warns they are LIVE', async () => {
    await loaded()
    fireEvent.click(screen.getByText('admin.reviewers.tabEmails'))
    await waitFor(() => expect(screen.getByText('admin.reviewers.emails.title')).toBeTruthy())
    // The one thing a reader must not get wrong: switching one off really does stop it.
    expect(screen.getByText('admin.reviewers.emails.liveNote')).toBeTruthy()
    expect(mockApi.getReviewerEmails).toHaveBeenCalled()
  })

  it('asks the server for the REVIEWER family, never the partner list', async () => {
    // The Sources screen is "Partner emails"; a template about our own volunteers filed there
    // would be shelved where nobody looking for it would look.
    await loaded()
    fireEvent.click(screen.getByText('admin.reviewers.tabEmails'))
    await waitFor(() => expect(mockApi.getReviewerEmails).toHaveBeenCalled())
    expect(mockApi.getPartnerEmails).not.toHaveBeenCalled()
  })

  it('does not offer the tab to finance, which may READ the reviewers list', async () => {
    // Deciding what every volunteer is told is editorial, not financial.
    viewerRole = { role: 'finance' }
    await loaded()
    expect(screen.queryByText('admin.reviewers.tabEmails')).toBeNull()
  })
})

describe('the role gate', () => {
  it('refuses a reviewer rather than showing them their colleagues\' caseloads', async () => {
    viewerRole = { role: 'reviewer' }
    render(<AdminReviewersList />)
    await waitFor(() => expect(screen.getByText('apiErrors.superAdminRequired')).toBeTruthy())
    expect(screen.queryByText('Kavitha Raman')).toBeNull()
  })

  it('admits finance, which already reads the staff list', async () => {
    viewerRole = { role: 'finance' }
    render(<AdminReviewersList />)
    // getAllBy: the row exists twice (phone card + desktop table). The gate is what is under
    // test, so either rendering proves it.
    await waitFor(() => expect(screen.getAllByText('Kavitha Raman').length).toBeGreaterThan(0))
  })
})

describe('failure', () => {
  it('says the list could not be loaded instead of showing an empty table', async () => {
    mockApi.listReviewers.mockRejectedValue(new Error('boom'))
    render(<AdminReviewersList />)
    await waitFor(() => expect(screen.getByText('admin.reviewers.loadFailed')).toBeTruthy())
    expect(screen.queryByText('admin.reviewers.empty')).toBeNull()
  })

  it('says so plainly when there are no reviewers at all', async () => {
    mockApi.listReviewers.mockResolvedValue({ reviewers: [], programmes: giftChoices })
    render(<AdminReviewersList />)
    await waitFor(() => expect(screen.getByText('admin.reviewers.empty')).toBeTruthy())
  })
})

describe('the Admins tab (2026-09-09)', () => {
  /** The admins TABLE, not its phone cards — `StaffTable` draws both, like every list here. */
  const staffTable = () => within(document.querySelector('table.min-w-full, table') as HTMLElement)

  const openAdmins = async () => {
    await loaded()
    fireEvent.click(screen.getByText('admin.people.tabAdmins'))
    await waitFor(() => expect(screen.getAllByText('Dina Ismail').length).toBeGreaterThan(0))
  }

  it('lists the admins — the five people who had no directory at all until now', async () => {
    await openAdmins()
    expect(screen.getAllByText('Dina Ismail').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Shanti Subramaniam').length).toBeGreaterThan(0)
  })

  it('⚠ does NOT list reviewers on it — the two tabs are the owner\'s two categories', async () => {
    // If a reviewer leaked in, the tab would be the whole staff list under a narrower name, and
    // this page would be showing the same person twice — the fault the sprint exists to remove.
    await openAdmins()
    expect(screen.queryByText('Kavitha Raman')).toBeNull()
  })

  it('⚠ offers Revoke here, which is where it now lives', async () => {
    // It used to sit on Invitations. That page lists only people who have NOT arrived, and
    // revoking is something you do to somebody who has.
    await openAdmins()
    expect(screen.getAllByText('admin.revoke').length).toBeGreaterThan(0)
  })

  it('offers Restore on somebody switched off, not a second Revoke', async () => {
    await openAdmins()
    expect(screen.getAllByText('admin.restore').length).toBeGreaterThan(0)
  })

  it('⚠ shows finance the tab and NO way to switch anybody off', async () => {
    // Reading who has access is not the same power as removing it. Same gate Revoke had on
    // Invitations, moved with the control rather than widened.
    viewerRole = { role: 'finance' }
    await openAdmins()
    expect(screen.getAllByText('Dina Ismail').length).toBeGreaterThan(0)
    expect(screen.queryByText('admin.revoke')).toBeNull()
    expect(screen.queryByText('admin.restore')).toBeNull()
  })

  it('⚠ still offers the tab bar to finance, who may not edit the emails', async () => {
    // The bar used to render only for the roles that may edit emails. Admins is a READING tab, so
    // that gate would have hidden it from `finance` entirely.
    viewerRole = { role: 'finance' }
    await loaded()
    expect(screen.getByText('admin.people.tabAdmins')).toBeTruthy()
    expect(screen.queryByText('admin.reviewers.tabEmails')).toBeNull()
  })
})

describe('what the reviewers table gained (2026-09-09)', () => {
  it('says when somebody was last here', async () => {
    await loaded()
    expect(ui().getByText('04/09/2026')).toBeTruthy()
  })

  it('⚠ says NOT RECORDED for a blank, never "never signed in"', async () => {
    // The column is best-effort and empty for everybody predating it. A blank is our gap, not
    // theirs, and must never read as an accusation.
    await loaded()
    expect(ui().getByText('admin.reviewers.lastSeenUnknown')).toBeTruthy()
  })

  it('offers Revoke on a reviewer who still has access', async () => {
    await loaded()
    expect(ui().getAllByText('admin.revoke').length).toBeGreaterThan(0)
  })

  it('⚠ and Restore on a revoked one, who is STILL LISTED', async () => {
    // The reversal that makes Revoke usable at all: a revoked reviewer used to vanish from this
    // table, so pressing the button removed the only route back.
    mockApi.listReviewers.mockResolvedValue({
      reviewers: [{ ...REVIEWERS[0], is_active: false }] as unknown as api.AdminReviewer[],
      programmes: giftChoices,
    })
    render(<AdminReviewersList />)
    await waitFor(() => expect(screen.getAllByText('Kavitha Raman').length).toBeGreaterThan(0))
    expect(ui().getByText('admin.reviewers.status.revoked')).toBeTruthy()
    expect(ui().getByText('admin.restore')).toBeTruthy()
  })

  it('⚠ warns what a revoke STRANDS when they hold open cases', async () => {
    // Revoke flips one flag and touches nothing else: the cases stay assigned to somebody who
    // cannot open them. Kavitha holds three. The count has to be in the question.
    const confirm = jest.spyOn(window, 'confirm').mockReturnValue(false)
    await loaded()
    fireEvent.click(ui().getAllByText('admin.revoke')[0])
    expect(confirm).toHaveBeenCalledWith(
      expect.stringContaining('admin.reviewers.revokeConfirmOpen'))
    expect(mockApi.revokeAdmin).not.toHaveBeenCalled()   // said no; nothing happened
    confirm.mockRestore()
  })

  it('⚠ shows finance no Revoke at all', async () => {
    viewerRole = { role: 'finance' }
    await loaded()
    expect(ui().queryByText('admin.revoke')).toBeNull()
  })
})
