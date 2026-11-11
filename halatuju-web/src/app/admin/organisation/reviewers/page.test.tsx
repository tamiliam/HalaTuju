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
import { act as actA15 } from '@testing-library/react'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
let viewerRole: { role: string; is_super_admin?: boolean; page_keys?: string[] } = { role: 'org_admin' }
jest.mock('@/lib/admin-auth-context', () => ({
  useAdminAuth: () => ({ token: 'tok', role: viewerRole }),
}))
jest.mock('@/lib/admin-api')
// M1b: Team opens on Staff (`?tab=staff`, the default). Most tests below are about the Reviewers table, so
// they ask for it (`?tab=reviewers`); the Staff describe asks for nothing.
let tabParam: string | null = 'reviewers'
jest.mock('next/navigation', () => ({
  ...jest.requireActual('next/navigation'),
  useSearchParams: () => ({ get: (k: string) => (k === 'tab' ? tabParam : null) }),
}))
// M1b: the Staff tab's screen is its own chunk (`components/admin/StaffList`, tested there). The stand-in
// reads the list as the real one does on mount, so a test can tell whether Staff was ever drawn.
jest.mock('@/components/admin/StaffList', () => {
  const { useEffect } = jest.requireActual('react')
  const apiMock = jest.requireMock('@/lib/admin-api')
  return {
    __esModule: true,
    default: function StaffListStub({ canManage }: { canManage: boolean }) {
      useEffect(() => { apiMock.getStaffList({ token: 'tok' }) }, [])
      return <div data-testid="team-staff-screen" data-manage={canManage ? 'yes' : 'no'} />
    },
  }
})
// T3: the Mentors tab's screen is its own chunk (`components/mentors/MentorsAdmin`, tested there).
jest.mock('@/components/mentors/MentorsAdmin', () => ({
  __esModule: true,
  default: ({ AlsoIn, adding, onAddClose }: { AlsoIn: unknown; adding?: boolean; onAddClose?: () => void }) =>
    <div data-testid="team-mentors-screen" data-adding={adding ? 'yes' : 'no'}>
      {typeof AlsoIn === 'function' ? 'chips' : ''}
      <button type="button" data-testid="mock-mentor-sheet-close" onClick={() => onAddClose?.()} />
    </div>,
}))

const mockApi = api as jest.Mocked<typeof api>

const REVIEWERS = [
  {
    id: 5, name: 'Kavitha Raman', email: 'kavitha@example.org', role: 'reviewer',
    languages: ['ta', 'en'], open_now: 3, awaiting_review: 1, interviewing: 2, completed: 12, turnaround_days: 4.5, paused: false, paused_at: null,
    is_active: true, last_seen_at: '2026-09-04T09:00:00Z', gifts: [],
  },
  {
    id: 6, name: 'Hafiz Rahman', email: 'hafiz@example.org', role: 'qc',
    languages: [], open_now: 0, awaiting_review: 0, interviewing: 0, completed: 0, turnaround_days: null, paused: false, paused_at: null,
    is_active: true, last_seen_at: null, gifts: [],
  },
] as unknown as api.AdminReviewer[]

/** The organisation's gifts. The table never shows them (owner 2026-11-07: the profile does). */
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
  tabParam = 'reviewers'
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
  it('draws the columns the surface was approved with', async () => {
    await loaded()
    // Owner 2026-11-08: the first header reads "Name", as on Admins and Mentors.
    expect(ui().getByText('admin.nameHeader')).toBeTruthy()
    expect(ui().queryByText('admin.reviewers.colName')).toBeNull()
    for (const key of ['colAwaiting', 'colInterviewing', 'colCompleted',
      'colTurnaround', 'colStatus']) {
      expect(ui().getByText(`admin.reviewers.${key}`)).toBeTruthy()
    }
    // Owner 2026-11-07: no Languages column — the reviewer's own page shows them.
    expect(ui().queryByText('admin.reviewers.colLanguages')).toBeNull()
    // Team tables T2: the Role column became "Also in". T3 (owner): no permission column on the Team
    // tables — permissions are set only on the person's page.
    expect(ui().getByText('admin.team.colAlsoIn')).toBeTruthy()
    expect(ui().queryByText('admin.team.colKeys.reviewers')).toBeNull()
    expect(ui().queryByText('admin.reviewers.colRole')).toBeNull()
  })

  it('replaces Open now with its two halves, and greys a zero (request #51)', async () => {
    await loaded()
    expect(screen.queryByText('admin.reviewers.colOpen')).toBeNull()
    expect(ui().getByTestId('awaiting-5').textContent).toBe('1')
    expect(ui().getByTestId('interviewing-5').textContent).toBe('2')
    // Nothing awaiting review: greyed — the "can take more" signal the requester asked for.
    expect(ui().getByTestId('awaiting-6').className).toContain('text-ground-400')
    expect(ui().getByTestId('awaiting-5').className).not.toContain('text-ground-400')
    // The phone cards carry the same two figures.
    expect(within(cards()).getAllByText('admin.reviewers.colAwaiting').length).toBe(2)
    expect(within(cards()).getAllByText('admin.reviewers.colInterviewing').length).toBe(2)
  })

  it('opens each reviewer\'s own record from their name', async () => {
    await loaded()
    expect(ui().getByText('Kavitha Raman').closest('a')!.getAttribute('href'))
      .toBe('/admin/organisation/reviewers/5')
  })

  it('shows no languages on the table or the phone cards (owner 2026-11-07: on the profile)', async () => {
    await loaded()
    expect(screen.queryByText('admin.reviewers.lang.ta')).toBeNull()
    expect(screen.queryByText('admin.reviewers.lang.en')).toBeNull()
  })
})

describe('the two figures that lie if you let them', () => {
  /** The turnaround cell of the row whose link points at `/…/<id>`. */
  const turnaroundOf = (id: number) => {
    const row = screen.getAllByRole('row').slice(1).find((r) =>
      r.querySelector('a')!.getAttribute('href')!.endsWith(`/${id}`))!
    return row.querySelectorAll('td')[5].textContent   // T2: Also in before it (T3: no permissions; 2026-11-07: no languages)
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

/** Owner 2026-11-07: gifts are shown and edited on the reviewer's own page, never on the table —
 *  even when the organisation runs several gifts. (The editor itself is tested in `[id]/page.test.tsx`.) */
describe('no gift chips on the table', () => {
  it('shows no gift chips and no pencil, on the table or the phone cards', async () => {
    const SABAH = { id: 9, code: 'sabah', name: 'Sabah Bursary', is_active: true }
    giftChoices = [...giftChoices, SABAH]
    mockApi.listReviewers.mockResolvedValue({
      reviewers: [{ ...REVIEWERS[0], gifts: [SABAH] }, REVIEWERS[1]], programmes: giftChoices })
    await loaded()
    expect(screen.queryByTestId('gifts-5')).toBeNull()
    expect(screen.queryByTestId('gifts-edit-5')).toBeNull()
    expect(screen.queryByText('Sabah Bursary')).toBeNull()
    expect(screen.queryByText('admin.reviewers.gifts.every')).toBeNull()
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
    const header = screen.getByText('admin.nameHeader').closest('th')!
    expect(header.getAttribute('aria-sort')).toBe('none')
    fireEvent.click(screen.getByText('admin.nameHeader'))
    await waitFor(() =>
      expect(screen.getByText('admin.nameHeader').closest('th')!.getAttribute('aria-sort'))
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
    // T4: the tab's other two sections — the admin list (keys from the server's registry) and the
    // mentor invitation (Invitations' own card and endpoint).
    mockApi.getTeamAdminEmails.mockResolvedValue({ emails: [{ key: 'payment_approval' }, { key: 'invoice' }] })
    mockApi.getInvitationEmails.mockResolvedValue({
      templates: [
        { ...TEMPLATES[0], kind: 'invite_admin', to_reviewer: false },
        { ...TEMPLATES[0], kind: 'invite_mentor', to_reviewer: false },
      ], organisations: [], qualifying_count: 0, partner_count: 0, comms_enabled: true,
    } as unknown as api.PartnerEmailsPayload)
  })

  it('T4: three sections in the order of the tables — Admin, Reviewer, Mentor', async () => {
    await loaded()
    fireEvent.click(screen.getByText('admin.reviewers.tabEmails'))
    await waitFor(() => expect(screen.getByTestId('team-admin-email-invoice')).toBeTruthy())
    const at = ['team-emails-admin', 'team-emails-reviewer', 'team-emails-mentor']
      .map((id) => document.body.innerHTML.indexOf(`data-testid="${id}"`))
    expect(at.every((x) => x >= 0)).toBe(true)
    expect([...at].sort((a, b) => a - b)).toEqual(at)
  })

  it('T4: the admin list is read-only — what, when, to whom; no switch, no editor', async () => {
    await loaded()
    fireEvent.click(screen.getByText('admin.reviewers.tabEmails'))
    const row = await screen.findByTestId('team-admin-email-payment_approval')
    expect(within(row).getByText('admin.team.emails.kind.payment_approval')).toBeTruthy()
    expect(within(row).getByText('admin.team.emails.when.payment_approval')).toBeTruthy()
    expect(within(row).getByText('admin.team.emails.to.payment_approval')).toBeTruthy()
    expect(within(screen.getByTestId('team-emails-admin')).queryByRole('switch')).toBeNull()
    expect(within(screen.getByTestId('team-emails-admin')).queryByRole('button')).toBeNull()
    expect(screen.getByText('admin.team.emails.adminNote')).toBeTruthy()
  })

  it('T4: the mentor section is the invitation card showing ONLY the mentor letter, with the line', async () => {
    await loaded()
    fireEvent.click(screen.getByText('admin.reviewers.tabEmails'))
    const mentor = screen.getByTestId('team-emails-mentor')
    await waitFor(() => expect(within(mentor).getByText('admin.invitations.emails.kind.invite_mentor')).toBeTruthy())
    expect(within(mentor).queryByText('admin.invitations.emails.kind.invite_admin')).toBeNull()
    expect(within(mentor).getByTestId('invitation-emails-note').textContent).toBe('admin.team.emails.mentorNone')
    expect(mockApi.getInvitationEmails).toHaveBeenCalled()
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

describe('the Terms tab (T4)', () => {
  it('opens for everyone who reads the page, with the three sections each marked Soon', async () => {
    viewerRole = { role: 'finance' }
    await loaded()
    fireEvent.click(screen.getByText('admin.reviewers.tabTerms'))
    for (const k of ['admin', 'reviewer', 'mentor']) {
      const sec = screen.getByTestId(`team-terms-${k}`)
      expect(within(sec).getByText(`admin.team.terms.${k}Title`)).toBeTruthy()
      expect(within(sec).getByText('admin.team.terms.soon')).toBeTruthy()
      expect(within(sec).getByText(`admin.team.terms.${k}Text`)).toBeTruthy()
    }
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

  it('shows no phone on the Admins tab even when the admin data carries one', async () => {
    mockApi.getAdmins.mockResolvedValue({ admins: ADMINS.map((a) => ({ ...a, phone: '012-000 0000' })) })
    await openAdmins()
    expect(document.querySelector('[data-testid^="team-phone-"]')).toBeNull()
    expect(document.body.textContent).not.toContain('012-000 0000')
  })

  it('M1a review fix 7: the Admins tab does not ask the API for phones (no `?phones=1`)', async () => {
    await openAdmins()
    expect(mockApi.getAdmins).toHaveBeenCalled()
    for (const call of mockApi.getAdmins.mock.calls) expect(call[1]).toBeFalsy()
  })

  it('⚠ does NOT list reviewers on it — the two tabs are the owner\'s two categories', async () => {
    // If a reviewer leaked in, the tab would be the whole staff list under a narrower name, and
    // this page would be showing the same person twice — the fault the sprint exists to remove.
    await openAdmins()
    expect(screen.queryByText('Kavitha Raman')).toBeNull()
  })

  it('⚠ M1b (owner O3): offers NO Revoke, Restore or Delete here — they moved to Staff', async () => {
    await openAdmins()
    expect(screen.queryByText('admin.revoke')).toBeNull()
    expect(screen.queryByText('admin.restore')).toBeNull()
    expect(screen.queryByText('admin.delete')).toBeNull()
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

describe('the Admins tab: a team member\'s name opens their page (2026-10-22)', () => {
  // Permissions live on the person's own page now, not in a card above this list.
  const WITH_ADMIN = [...ADMINS, { id: 14, name: 'Arun Pillai', email: 'arun@example.org',
    role: 'admin', is_active: true, is_super_admin: false, org_name: null,
    created_at: '2026-01-01T00:00:00Z' }] as unknown as api.AdminItem[]
  const hrefOf = (name: string) =>
    within(table()).getByText(name).closest('a')?.getAttribute('href') ?? null

  const openAdmins = async () => {
    mockApi.getAdmins.mockResolvedValue({ admins: WITH_ADMIN })
    await loaded()
    fireEvent.click(screen.getByText('admin.people.tabAdmins'))
    await waitFor(() => expect(screen.getAllByText('Arun Pillai').length).toBeGreaterThan(0))
  }

  it('links an active Admin to /admin/organisation/reviewers/admins/<id>', async () => {
    await openAdmins()
    expect(hrefOf('Arun Pillai')).toBe('/admin/organisation/reviewers/admins/14')
  })

  it('⚠ leaves a revoked person as plain text', async () => {
    await openAdmins()
    expect(hrefOf('Shanti Subramaniam')).toBeNull()          // revoked finance
  })

  // O10 (owner, 2026-11-10): the organisation admin's name opens their page, as every other admin's
  // does — where the page's own GET would answer (`manageable`, the `_staff_target_manageable` fence).
  const LEAD = { id: 21, name: 'Lead Person', email: 'lead@example.org', role: 'org_admin', is_active: true,
    is_super_admin: false, org_name: null, created_at: '2026-01-01T00:00:00Z' }
  const openWithLead = async (lead: Record<string, unknown>) => {
    mockApi.getAdmins.mockResolvedValue({ admins: [...WITH_ADMIN, lead] as unknown as api.AdminItem[] })
    await loaded()
    fireEvent.click(screen.getByText('admin.people.tabAdmins'))
    await waitFor(() => expect(screen.getAllByText('Lead Person').length).toBeGreaterThan(0))
  }

  it('O10: links the organisation admin for a super, whom the server lets manage them', async () => {
    viewerRole = { role: 'reviewer', is_super_admin: true }
    await openWithLead({ ...LEAD, manageable: true })
    expect(hrefOf('Lead Person')).toBe('/admin/organisation/reviewers/admins/21')
  })

  it('O10 (M1b): an organisation admin may open a fellow organisation admin\'s page — it is read-only there', async () => {
    await openWithLead({ ...LEAD, manageable: false })
    expect(hrefOf('Lead Person')).toBe('/admin/organisation/reviewers/admins/21')
    expect(hrefOf('Arun Pillai')).toBe('/admin/organisation/reviewers/admins/14')   // the rest unchanged
  })

  it('O10: a non-lead row the server says is not manageable still links nobody', async () => {
    mockApi.getAdmins.mockResolvedValue({ admins: [...WITH_ADMIN.slice(0, 3),
      { ...WITH_ADMIN[3], manageable: false }] as unknown as api.AdminItem[] })
    await loaded()
    fireEvent.click(screen.getByText('admin.people.tabAdmins'))
    await waitFor(() => expect(screen.getAllByText('Arun Pillai').length).toBeGreaterThan(0))
    expect(hrefOf('Arun Pillai')).toBeNull()
  })

  it('O10: a revoked organisation admin stays plain text, even for a super', async () => {
    viewerRole = { role: 'reviewer', is_super_admin: true }
    await openWithLead({ ...LEAD, is_active: false, manageable: true })
    expect(hrefOf('Lead Person')).toBeNull()
  })

  it('⚠ links nobody for a viewer who may not manage (finance)', async () => {
    viewerRole = { role: 'finance' }
    await openAdmins()
    expect(hrefOf('Arun Pillai')).toBeNull()
  })

  it('no longer offers a Permissions button or a card above the list', async () => {
    await openAdmins()
    expect(screen.queryByText('admin.permEditor.open')).toBeNull()
    expect(screen.queryByTestId('permission-editor')).toBeNull()
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

  it('⚠ M1b (owner O3): offers no Revoke on the Reviewers table — Suspend is on Staff', async () => {
    await loaded()
    expect(ui().queryByText('admin.revoke')).toBeNull()
    expect(within(cards()).queryByText('admin.revoke')).toBeNull()
  })

  it('⚠ a revoked reviewer is STILL LISTED, marked revoked, with no Restore here', async () => {
    mockApi.listReviewers.mockResolvedValue({
      reviewers: [{ ...REVIEWERS[0], is_active: false }] as unknown as api.AdminReviewer[],
      programmes: giftChoices,
    })
    render(<AdminReviewersList />)
    await waitFor(() => expect(screen.getAllByText('Kavitha Raman').length).toBeGreaterThan(0))
    expect(ui().getByText('admin.reviewers.status.revoked')).toBeTruthy()
    expect(ui().queryByText('admin.restore')).toBeNull()
  })

  it('⚠ shows finance no Revoke at all', async () => {
    viewerRole = { role: 'finance' }
    await loaded()
    expect(ui().queryByText('admin.revoke')).toBeNull()
  })
})

describe('the staff lifecycle (2026-10-09)', () => {
  const ASHA = { id: 21, name: 'Asha Devi', email: 'asha@example.org', role: 'admin',
    is_active: true, is_super_admin: false, org_name: null, created_at: '2026-01-01T00:00:00Z',
    manageable: true, deletable: true, work: {} } as unknown as api.AdminItem

  const openAdmins = async (admins: api.AdminItem[]) => {
    mockApi.getAdmins.mockResolvedValue({ admins })
    await loaded()
    fireEvent.click(screen.getByText('admin.people.tabAdmins'))
    await waitFor(() => expect(screen.getAllByText(admins[0].name).length).toBeGreaterThan(0))
  }
  const adminsTable = () => within(document.querySelector('[data-testid="table-scroller"]') as HTMLElement)

  afterEach(() => jest.restoreAllMocks())

  it('⚠ T2: offers NO Change role on either table — Finance and QC are no longer labels', async () => {
    await openAdmins([ASHA])
    expect(adminsTable().queryByText('admin.changeRole')).toBeNull()
    fireEvent.click(screen.getByText('admin.reviewers.tabReviewers'))
    await waitFor(() => expect(ui().getByText('Kavitha Raman')).toBeTruthy())
    expect(ui().queryByText('admin.changeRole')).toBeNull()
  })

  it('offers finance no Change role', async () => {
    viewerRole = { role: 'finance' }
    await loaded()
    expect(ui().queryByText('admin.changeRole')).toBeNull()
  })
})

describe('common profile S2: the photo; M1a (owner O16): never a phone on a group table', () => {
  it('shows the photo, and no phone even when an older payload still carries one', async () => {
    mockApi.listReviewers.mockResolvedValue({ programmes: giftChoices, reviewers: [
      { ...REVIEWERS[0], photo_url: 'https://signed/k.webp', phone: '011-1111 1111' },
      { ...REVIEWERS[1], photo_url: null, phone: null },
    ] as unknown as api.AdminReviewer[] })
    await loaded()
    expect(document.querySelector('[data-testid^="team-phone-"]')).toBeNull()
    expect(document.body.textContent).not.toContain('011-1111 1111')   // desktop table and phone cards
    const photos = ui().getAllByTestId('staff-avatar-photo') as HTMLImageElement[]
    expect(photos.map((p) => p.src)).toEqual(['https://signed/k.webp'])
    expect(ui().getAllByTestId('staff-avatar-initials').length).toBe(1)
  })
})

describe('common profile S2: the optional fourth language', () => {
  it('is not on the table either (owner 2026-11-07: languages live on the profile)', async () => {
    mockApi.listReviewers.mockResolvedValue({ programmes: giftChoices, reviewers: [
      { ...REVIEWERS[0], other_language: 'Kadazandusun' }, { ...REVIEWERS[1], other_language: '' },
    ] as unknown as api.AdminReviewer[] })
    await loaded()
    expect(screen.queryByText('Kadazandusun')).toBeNull()
    expect(screen.queryByTestId('other-language-5')).toBeNull()
  })
})

describe('Team tables T2: Admins · Reviewers, Add and Remove', () => {
  const ROHINI = { id: 31, name: 'Rohini Thiru', email: 'rohini@example.org', role: 'reviewer',
    is_active: true, is_super_admin: false, org_name: null, created_at: '2026-01-01T00:00:00Z',
    manageable: true, tables: ['admins', 'reviewers'], admin_keys: ['see_all', 'spending'],
    reviewer_keys: ['review'], lead: false, remove: { admins: null, reviewers: 'has_open_cases' },
  } as unknown as api.AdminItem
  const LEAD = { id: 32, name: 'Suresh T', email: 'suresh@example.org', role: 'org_admin',
    is_active: true, is_super_admin: false, org_name: null, created_at: '2026-01-01T00:00:00Z',
    manageable: false, tables: ['admins', 'reviewers', 'mentors'], admin_keys: [], reviewer_keys: ['review'],
    lead: true, remove: {} } as unknown as api.AdminItem
  const KAMALA = { id: 33, name: 'Kamala Devi', email: 'kamala@example.org', role: 'finance',
    is_active: true, is_super_admin: false, org_name: null, created_at: '2026-01-01T00:00:00Z',
    manageable: true, tables: ['admins'], admin_keys: ['payments_approve'], reviewer_keys: [],
    lead: false, remove: { admins: 'last_table' } } as unknown as api.AdminItem
  const adminsTable = () => within(document.querySelector('[data-testid="table-scroller"]') as HTMLElement)
  const rowOf = (name: string) => adminsTable().getByText(name).closest('tr') as HTMLElement

  const openAdmins = async () => {
    mockApi.getAdmins.mockResolvedValue({ admins: [LEAD, ROHINI, KAMALA] })
    await loaded()
    fireEvent.click(screen.getByText('admin.people.tabAdmins'))
    await waitFor(() => expect(screen.getAllByText('Kamala Devi').length).toBeGreaterThan(0))
  }

  it('shows the tabs in the owner order: Staff, Admins, Reviewers, Mentors, Emails, Terms', async () => {
    await loaded()
    const order = ['admin.staff.tab', 'admin.people.tabAdmins', 'admin.reviewers.tabReviewers', 'admin.team.tabMentors',
      'admin.reviewers.tabEmails', 'admin.reviewers.tabTerms']
    const at = order.map((k) => document.body.innerHTML.indexOf(k))
    expect(at.every((x) => x >= 0)).toBe(true)
    expect([...at].sort((a, b) => a - b)).toEqual(at)
  })

  it('seats a person by their TABLES: Rohini (role reviewer, admin keys) is in Admins too', async () => {
    await openAdmins()
    const row = rowOf('Rohini Thiru')
    expect(within(row).getByText('admin.team.chip.reviewers')).toBeTruthy()       // Also in
    // T3 (owner): no permission chips on the Team tables — the person's page holds them.
    expect(within(row).queryByText('admin.perm.see_all.name')).toBeNull()
    expect(within(row).queryByText('admin.perm.spending.name')).toBeNull()
    expect(within(row).getByTestId('remove-from-admins')).toBeTruthy()
  })

  it('the organisation admin reads "Organisation admin (lead)", with no editor and no Remove', async () => {
    await openAdmins()
    const row = rowOf('Suresh T')
    expect(within(row).getByText('admin.team.leadChip')).toBeTruthy()
    expect(within(row).queryByText('admin.team.edit.admins')).toBeNull()
    expect(within(row).queryByTestId('remove-from-admins')).toBeNull()
  })

  it('M1b: their LAST group keeps its Remove, which warns they become No group and sends to_no_group', async () => {
    mockApi.changeTeamTable.mockResolvedValue({ id: 33, table: 'admins', action: 'remove', dry_run: true,
      role: 'member', role_changed: true, added: [], removed: ['payments_approve'], consequences: [],
      finance_check_off: false, opens_admin_pages: false, becomes_member: true } as unknown as api.TeamTablePlan)
    await openAdmins()
    const row = rowOf('Kamala Devi')
    expect(within(row).queryByTestId('remove-note-admins')).toBeNull()        // O17: no inline hint
    fireEvent.click(within(row).getByTestId('remove-from-admins'))
    await waitFor(() => expect(mockApi.changeTeamTable).toHaveBeenCalledWith(
      'admins', 33, 'remove', true, { token: 'tok' }, true))
    expect(await screen.findByText('admin.team.becomesMember')).toBeTruthy()
    const go = screen.getByTestId('team-remove-confirm') as HTMLButtonElement
    await waitFor(() => expect(go.disabled).toBe(false))
    fireEvent.click(go)
    await waitFor(() => expect(mockApi.changeTeamTable).toHaveBeenCalledWith(
      'admins', 33, 'remove', false, { token: 'tok' }, true))
  })

  it('M1b (O17, TD-606): an Admins row served `not_arrived` is GREYED', async () => {
    mockApi.getAdmins.mockResolvedValue({ admins: [LEAD, ROHINI, { ...KAMALA, remove: { admins: 'not_arrived' } }] })
    await loaded()
    fireEvent.click(screen.getByText('admin.people.tabAdmins'))
    await waitFor(() => expect(screen.getAllByText('Kamala Devi').length).toBeGreaterThan(0))
    const row = rowOf('Kamala Devi')
    expect(within(row).queryByTestId('remove-from-admins')).toBeNull()
    const b = within(within(row).getByTestId('remove-greyed-admins')).getByText('admin.team.removeFrom.admins')
    expect(document.getElementById(b.getAttribute('aria-describedby')!)!.textContent).toBe('admin.refusal.not_arrived')
    fireEvent.click(b)
    expect(mockApi.changeTeamTable).not.toHaveBeenCalled()
  })

  it('M1b (O17, TD-606): an Admins row served `run_in_progress` is GREYED with its served run count', async () => {
    mockApi.getAdmins.mockResolvedValue({ admins: [LEAD, ROHINI,
      { ...KAMALA, remove: { admins: 'run_in_progress' }, runs_in_progress: 2 }] })
    await loaded()
    fireEvent.click(screen.getByText('admin.people.tabAdmins'))
    await waitFor(() => expect(screen.getAllByText('Kamala Devi').length).toBeGreaterThan(0))
    const row = rowOf('Kamala Devi')
    expect(within(row).queryByTestId('remove-from-admins')).toBeNull()
    const b = within(within(row).getByTestId('remove-greyed-admins')).getByText('admin.team.removeFrom.admins')
    // The i18n mock returns the key: the count rides on `.many` (2 runs).
    expect(document.getElementById(b.getAttribute('aria-describedby')!)!.textContent)
      .toBe('admin.refusal.run_in_progress.many')
    fireEvent.click(b)
    expect(mockApi.changeTeamTable).not.toHaveBeenCalled()
  })

  it('a person whose only table this is shows no chips and no retired label (owner 2026-11-07)', async () => {
    await openAdmins()
    const row = rowOf('Kamala Devi')
    expect(within(row).queryByText('admin.perm.payments_approve.name')).toBeNull()  // T3: no chips here
    expect(within(row).queryByText('admin.role.finance')).toBeNull()               // label retired
  })

  it('T3: no "Edit permissions" link and no permission column; the NAME opens the person page', async () => {
    await openAdmins()
    const row = rowOf('Rohini Thiru')
    expect(within(row).queryByText('admin.team.edit.admins')).toBeNull()
    expect(screen.queryByText('admin.team.colKeys.admins')).toBeNull()
    expect(within(row).getByText('Rohini Thiru').closest('a')!.getAttribute('href'))
      .toBe('/admin/organisation/reviewers/admins/31')
  })

  it('Remove asks first, says what it does from the dry run, and only then removes', async () => {
    mockApi.changeTeamTable.mockResolvedValue({ id: 31, table: 'admins', action: 'remove', dry_run: true,
      role: 'reviewer', role_changed: false, added: [], removed: ['see_all', 'spending'],
      consequences: [], finance_check_off: false, opens_admin_pages: false })
    await openAdmins()
    fireEvent.click(within(rowOf('Rohini Thiru')).getByTestId('remove-from-admins'))
    await waitFor(() => expect(mockApi.changeTeamTable).toHaveBeenCalledWith(
      'admins', 31, 'remove', true, { token: 'tok' }, false))
    expect(mockApi.changeTeamTable).toHaveBeenCalledTimes(1)
    const go = await screen.findByTestId('team-remove-confirm') as HTMLButtonElement
    await waitFor(() => expect(go.disabled).toBe(false))
    expect(screen.queryByTestId('team-remove-no-group')).toBeNull()     // not their last group
    fireEvent.click(go)
    await waitFor(() => expect(mockApi.changeTeamTable).toHaveBeenCalledWith(
      'admins', 31, 'remove', false, { token: 'tok' }, false))
  })

  it('⚠ Remove from Reviewers that makes them an Admin SAYS they will open the admin work pages', async () => {
    mockApi.listReviewers.mockResolvedValue({ reviewers: [{ ...REVIEWERS[0], tables: ['admins', 'reviewers'],
      reviewer_keys: ['review'], remove: { reviewers: null } }], programmes: giftChoices })
    mockApi.changeTeamTable.mockResolvedValue({ id: 5, table: 'reviewers', action: 'remove', dry_run: true,
      role: 'admin', role_changed: true, added: [], removed: ['review'], consequences: [],
      finance_check_off: false, opens_admin_pages: true })
    await loaded()
    fireEvent.click(ui().getByTestId('remove-from-reviewers'))
    expect(await screen.findByText('admin.team.opensAdminPages')).toBeTruthy()
  })

  it('M1b (O17): open cases GREY the Reviewers Remove, the reason and count in its tip — no inline note', async () => {
    mockApi.listReviewers.mockResolvedValue({ reviewers: [{ ...REVIEWERS[0], tables: ['admins', 'reviewers'],
      remove: { reviewers: 'has_open_cases' } }], programmes: giftChoices })
    await loaded()
    expect(ui().queryByTestId('remove-from-reviewers')).toBeNull()
    const b = within(ui().getByTestId('remove-greyed-reviewers')).getByText('admin.team.removeFrom.reviewers')
    expect(b.getAttribute('aria-disabled')).toBe('true')
    // The i18n mock returns the key: the count rides on `.many` (Kavitha holds 3 open cases).
    expect(document.getElementById(b.getAttribute('aria-describedby')!)!.textContent)
      .toBe('admin.refusal.has_open_cases.many')
    fireEvent.click(b)
    expect(mockApi.changeTeamTable).not.toHaveBeenCalled()
  })

  it('M1b (O17, TD-606): a reviewer row served `not_arrived` is GREYED, whatever the Admins list says', async () => {
    mockApi.listReviewers.mockResolvedValue({ reviewers: [{ ...REVIEWERS[1], tables: ['reviewers'],
      remove: { reviewers: 'not_arrived' } }], programmes: giftChoices })
    // The served code is the whole answer; the page no longer reads `first_seen_at` from the Admins list.
    mockApi.getAdmins.mockResolvedValue({ admins: [...ADMINS, { ...ADMINS[2], id: 6, first_seen_at: '2026-10-01T08:00:00Z' }] })
    render(<AdminReviewersList />)
    const grey = await waitFor(() => within(table()).getByTestId('remove-greyed-reviewers'))
    const b = within(grey).getByText('admin.team.removeFrom.reviewers')
    expect(document.getElementById(b.getAttribute('aria-describedby')!)!.textContent).toBe('admin.refusal.not_arrived')
    expect(within(table()).queryByTestId('remove-from-reviewers')).toBeNull()
  })

  it('M1b (O17, TD-606): a served `last_table` stays live, whatever the Admins list says', async () => {
    mockApi.listReviewers.mockResolvedValue({ reviewers: [{ ...REVIEWERS[1], tables: ['reviewers'],
      remove: { reviewers: 'last_table' } }], programmes: giftChoices })
    mockApi.getAdmins.mockResolvedValue({ admins: [{ ...ADMINS[2], id: 6, first_seen_at: null }] })
    render(<AdminReviewersList />)
    await waitFor(() => expect(within(table()).getByTestId('remove-from-reviewers')).toBeTruthy())
    expect(within(table()).queryByTestId('remove-greyed-reviewers')).toBeNull()
  })

  it('Add Reviewer lists the server candidates and adds the one picked', async () => {
    mockApi.getTeamCandidates.mockResolvedValue({ table: 'reviewers', candidates: [
      { id: 32, name: 'Suresh T', email: 'suresh@example.org', lead: true, mentor_only: false,
        tables: ['admins'], consequences: [] }] })
    mockApi.changeTeamTable.mockResolvedValue({ id: 32, table: 'reviewers', action: 'add', dry_run: true,
      role: 'org_admin', role_changed: false, added: ['review'], removed: [], consequences: [],
      finance_check_off: false, opens_admin_pages: false })
    await loaded()
    fireEvent.click(screen.getByTestId('team-add-reviewers-open'))
    await waitFor(() => expect(mockApi.getTeamCandidates).toHaveBeenCalledWith('reviewers', { token: 'tok' }))
    fireEvent.click(await screen.findByTestId('team-candidate-32'))
    await waitFor(() => expect(mockApi.changeTeamTable).toHaveBeenCalledWith(
      'reviewers', 32, 'add', true, { token: 'tok' }))
    const go = screen.getByTestId('team-add-confirm') as HTMLButtonElement
    await waitFor(() => expect(go.disabled).toBe(false))
    fireEvent.click(go)
    await waitFor(() => expect(mockApi.changeTeamTable).toHaveBeenCalledWith(
      'reviewers', 32, 'add', false, { token: 'tok' }))
  })

  it('Add sits on the tab row, after the tabs and outside the tablist (owner 2026-11-08)', async () => {
    await loaded()
    const add = screen.getByTestId('team-add-reviewers-open')
    const tablist = screen.getByRole('tablist')
    expect(tablist.contains(add)).toBe(false)              // a button in a tablist is not a tab
    expect(add.previousElementSibling?.contains(tablist)).toBe(true)   // same row, at its right end
  })

  it('⚠ offers no Add and no Remove to a viewer who may not edit permissions (admin)', async () => {
    viewerRole = { role: 'admin' }
    mockApi.listReviewers.mockResolvedValue({ reviewers: [{ ...REVIEWERS[0], remove: { reviewers: null } }],
      programmes: giftChoices })
    await loaded()
    expect(screen.queryByTestId('team-add-reviewers-open')).toBeNull()
    expect(screen.queryByTestId('remove-from-reviewers')).toBeNull()
  })

  it('T3: the Mentors tab mounts the Mentors table (its own chunk), handed the Also in chips', async () => {
    await loaded()
    fireEvent.click(screen.getByText('admin.team.tabMentors'))
    expect(await screen.findByTestId('team-mentors-screen')).toBeTruthy()
  })

  it('Add Mentor sits on the tab row too, and opens the Mentors screen\'s sheet (owner 2026-11-08)', async () => {
    await loaded()
    fireEvent.click(screen.getByText('admin.team.tabMentors'))
    const mentors = await screen.findByTestId('team-mentors-screen')
    expect(mentors.getAttribute('data-adding')).toBe('no')
    const add = screen.getByTestId('team-add-mentors-open')
    expect(add.textContent).toBe('admin.mentors.addMentor')
    expect(add.previousElementSibling?.contains(screen.getByRole('tablist'))).toBe(true)
    fireEvent.click(add)
    expect(screen.getByTestId('team-mentors-screen').getAttribute('data-adding')).toBe('yes')
    fireEvent.click(screen.getByTestId('mock-mentor-sheet-close'))
    expect(screen.getByTestId('team-mentors-screen').getAttribute('data-adding')).toBe('no')
  })

  it('⚠ no Add Mentor for a viewer who may not manage (admin)', async () => {
    viewerRole = { role: 'admin' }
    await loaded()
    fireEvent.click(screen.getByText('admin.team.tabMentors'))
    await screen.findByTestId('team-mentors-screen')
    expect(screen.queryByTestId('team-add-mentors-open')).toBeNull()
  })

  it('T3: the Mentors tab is offered only to who read the old Mentors page (not finance)', async () => {
    viewerRole = { role: 'finance' }
    await loaded()
    expect(screen.queryByText('admin.team.tabMentors')).toBeNull()
  })
})

describe('M1b: the group tables keep Add and Remove only (owner O3, O4)', () => {
  /** Kavitha has work on record; Hafiz has none; Dina is an organisation admin who also reviews. Each row
   *  is still served `deletable` / `work` — the table must draw none of it now. */
  const ROWS = [
    { ...REVIEWERS[0], deletable: false, work: { assigned_applications: 3 }, remove: { reviewers: null } },
    { ...REVIEWERS[1], deletable: true, work: {}, remove: { reviewers: null } },
    { ...REVIEWERS[1], id: 11, name: 'Dina Ismail', email: 'dina@example.org', role: 'org_admin',
      lead: true, deletable: true, work: {} },
  ] as unknown as api.AdminReviewer[]

  beforeEach(() => {
    mockApi.listReviewers.mockResolvedValue({ reviewers: ROWS, programmes: giftChoices })
  })

  it('draws no Revoke, Restore or Delete on the Reviewers table or its phone cards — Remove only', async () => {
    viewerRole = { role: 'reviewer', is_super_admin: true }      // even a super
    await loaded()
    for (const scope of [ui(), within(cards())]) {
      expect(scope.queryByText('admin.revoke')).toBeNull()
      expect(scope.queryByText('admin.restore')).toBeNull()
      expect(scope.queryByText('admin.delete')).toBeNull()
      expect(scope.queryByTestId('staff-delete')).toBeNull()
      expect(scope.queryByTestId('staff-delete-greyed')).toBeNull()
      expect(scope.getAllByTestId('remove-from-reviewers').length).toBe(2)
    }
  })

  it('draws no Revoke or Delete on the Admins table either, even for a super', async () => {
    viewerRole = { role: 'reviewer', is_super_admin: true }
    mockApi.getAdmins.mockResolvedValue({ admins: [
      { ...ADMINS[0], deletable: true, work: {} }, { ...ADMINS[1], deletable: false, work: { payment_runs: 1 } },
    ] as unknown as api.AdminItem[] })
    await loaded()
    fireEvent.click(screen.getByText('admin.people.tabAdmins'))
    await waitFor(() => expect(screen.getAllByText('Dina Ismail').length).toBeGreaterThan(0))
    expect(screen.queryByText('admin.delete')).toBeNull()
    expect(screen.queryByText('admin.revoke')).toBeNull()
    expect(screen.queryByText('admin.restore')).toBeNull()
    expect(mockApi.deleteAdmin).not.toHaveBeenCalled()
  })
})

describe('M1b: Team -> Staff, the first tab and the default', () => {
  beforeEach(() => { tabParam = null })

  it('lands on Staff when no tab is asked for, and the Staff tab is selected', async () => {
    render(<AdminReviewersList />)
    expect(await screen.findByTestId('team-staff-screen')).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'admin.staff.tab' }).getAttribute('aria-selected')).toBe('true')
    expect(screen.queryByTestId('table-scroller')).toBeNull()           // the Reviewers table is not drawn
  })

  it('lands on Staff for `?tab=staff` and for an unknown tab', async () => {
    tabParam = 'staff'
    const { unmount } = render(<AdminReviewersList />)
    expect(await screen.findByTestId('team-staff-screen')).toBeTruthy()
    unmount()
    tabParam = 'nonsense'
    render(<AdminReviewersList />)
    expect(await screen.findByTestId('team-staff-screen')).toBeTruthy()
  })

  it('`?tab=reviewers` still opens the Reviewers table', async () => {
    tabParam = 'reviewers'
    await loaded()
    expect(screen.queryByTestId('team-staff-screen')).toBeNull()
  })

  it('hands Staff the manage power only for a super or an organisation admin', async () => {
    render(<AdminReviewersList />)
    expect((await screen.findByTestId('team-staff-screen')).getAttribute('data-manage')).toBe('yes')
  })

  // M1b review: `admin/staff/` is on `team_roster` (team.view + mentoring.view), narrower than the page's
  // `team_read`. Finance reads Team but not the roster: no Staff tab, the Reviewers default, no 403.
  it('a finance reader (team_read, not team_roster) gets no Staff tab and lands on Reviewers', async () => {
    viewerRole = { role: 'finance' }
    await loaded()
    expect(screen.queryByRole('tab', { name: 'admin.staff.tab' })).toBeNull()
    expect(screen.getByRole('tab', { name: 'admin.reviewers.tabReviewers' }).getAttribute('aria-selected')).toBe('true')
    expect(screen.queryByTestId('team-staff-screen')).toBeNull()
    expect(mockApi.getStaffList).not.toHaveBeenCalled()
  })

  it('served doors decide: team_read without team_roster gets no Staff, even for `?tab=staff`', async () => {
    viewerRole = { role: 'org_admin', page_keys: ['invitations.view', 'team.view'] }
    tabParam = 'staff'
    await loaded()
    expect(screen.queryByRole('tab', { name: 'admin.staff.tab' })).toBeNull()
    expect(screen.queryByTestId('team-staff-screen')).toBeNull()
    expect(mockApi.getStaffList).not.toHaveBeenCalled()
  })

  it('served doors decide: team_roster opens Staff for a role the label list would not', async () => {
    viewerRole = { role: 'finance', page_keys: ['invitations.view', 'team.view', 'mentoring.view'] }
    render(<AdminReviewersList />)
    expect((await screen.findByTestId('team-staff-screen')).getAttribute('data-manage')).toBe('no')
    expect(mockApi.getStaffList).toHaveBeenCalled()
  })

  it('offers no Add button on the Staff tab (Add belongs to a group table)', async () => {
    render(<AdminReviewersList />)
    await screen.findByTestId('team-staff-screen')
    expect(screen.queryByTestId('team-add-admins-open')).toBeNull()
    expect(screen.queryByTestId('team-add-reviewers-open')).toBeNull()
  })
})

// A3.15: the loader reads the latest `t` through a ref instead of listing it (it used to carry a lint
// suppression). The mock above hands back a NEW `t` on every render, so a loader that listed `t`
// would read again on each re-render below; one that does not, reads exactly as often as before.
describe('the loader does not re-read when `t` changes identity (A3.15)', () => {
  it('listReviewers is called the same number of times after three more renders', async () => {
    const view = render(<AdminReviewersList />)
    await waitFor(() => expect(mockApi.listReviewers).toHaveBeenCalled())
    await actA15(async () => {})
    const before = mockApi.listReviewers.mock.calls.length
    view.rerender(<AdminReviewersList />)
    view.rerender(<AdminReviewersList />)
    view.rerender(<AdminReviewersList />)
    await actA15(async () => {})
    expect(mockApi.listReviewers).toHaveBeenCalledTimes(before)
  })
})
