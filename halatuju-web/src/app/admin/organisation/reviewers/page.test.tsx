/**
 * @jest-environment jsdom
 *
 * The reviewers table, rendered (request #10, 2026-08-02).
 *
 * The pure sort rules have their own tests; these pin what the SCREEN promises — including the two
 * things that must NOT be on it. A column removed by owner decision comes back the moment somebody
 * adds it "for completeness", and only a rendered test notices.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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
  },
  {
    id: 6, name: 'Hafiz Rahman', email: 'hafiz@example.org', role: 'qc',
    languages: [], open_now: 0, completed: 0, turnaround_days: null, paused: false, paused_at: null,
  },
] as unknown as api.AdminReviewer[]

beforeEach(() => {
  jest.clearAllMocks()
  viewerRole = { role: 'org_admin' }
  mockApi.listReviewers.mockResolvedValue({ reviewers: REVIEWERS })
})

const loaded = async () => {
  render(<AdminReviewersList />)
  await waitFor(() => expect(screen.getByText('Kavitha Raman')).toBeTruthy())
}

describe('what the table shows', () => {
  it('draws the six columns the surface was approved with', async () => {
    await loaded()
    for (const key of ['colName', 'colRole', 'colLanguages', 'colOpen', 'colCompleted',
      'colTurnaround', 'colStatus']) {
      expect(screen.getByText(`admin.reviewers.${key}`)).toBeTruthy()
    }
  })

  it('opens each reviewer\'s own record from their name', async () => {
    await loaded()
    expect(screen.getByText('Kavitha Raman').closest('a')!.getAttribute('href'))
      .toBe('/admin/organisation/reviewers/5')
  })

  it('names the languages someone can actually interview in', async () => {
    await loaded()
    expect(screen.getByText('admin.reviewers.lang.ta')).toBeTruthy()
    expect(screen.getByText('admin.reviewers.lang.en')).toBeTruthy()
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
    await waitFor(() => expect(screen.getByText('Kavitha Raman')).toBeTruthy())
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
    mockApi.listReviewers.mockResolvedValue({ reviewers: [] })
    render(<AdminReviewersList />)
    await waitFor(() => expect(screen.getByText('admin.reviewers.empty')).toBeTruthy())
  })
})
