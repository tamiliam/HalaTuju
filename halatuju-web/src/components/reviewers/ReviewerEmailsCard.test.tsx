/**
 * @jest-environment jsdom
 *
 * The Emails tab on Organisation → Reviewers, rendered — both halves of it.
 *
 * The five editable templates shipped on 2 August; the seven we maintain did not, and the owner's
 * reason for wanting them is precisely what these tests pin: *"their existence and content are
 * known to the org_admin. If not specified, they'll exist in the background without anyone paying
 * attention to them until something breaks."*
 *
 * So the claims here are about ABSENCE as much as presence. No switch and no Edit on the seven is
 * the statement being made, not an oversight, and a source-shape guard cannot see the difference —
 * only a rendered test notices when somebody adds a Toggle "for consistency".
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ReviewerEmailsCard from './ReviewerEmailsCard'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const t = (k: string) => k

const TEMPLATES = [
  { kind: 'reviewer_assigned', enabled: true, subject: 'A case for you', body: 'Dear reviewer',
    last_sent_at: null, to_reviewer: true },
  { kind: 'qc_returned', enabled: false, subject: 'Back to you', body: 'Dear reviewer',
    last_sent_at: null, to_reviewer: true },
] as unknown as api.PartnerEmailTemplate[]

const SYSTEM: api.ReviewerSystemEmail[] = [
  {
    key: 'partner_welcome',
    subject: 'Your HalaTuju partner access',
    body: 'Dear Reviewer,\n\nYou have been added to HalaTuju as a reviewer.',
    sensitive: true,
    wider_audience: false,
  },
  {
    key: 'verdict_escalation',
    subject: 'Overdue verdict needs attention — HT-0000',
    body: 'Hi,\n\nA B40 verdict is overdue and has been escalated.',
    sensitive: false,
    wider_audience: true,
  },
]

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getReviewerEmails.mockResolvedValue(
    { templates: TEMPLATES, qualifying: [] } as unknown as api.PartnerEmailsPayload)
  mockApi.getReviewerSystemEmails.mockResolvedValue({ emails: SYSTEM })
})

const loaded = async () => {
  render(<ReviewerEmailsCard token="tok" t={t} />)
  await waitFor(() =>
    expect(screen.getByText('admin.reviewers.emails.system.title')).toBeTruthy())
}

describe('the seven we maintain', () => {
  it('names each one and shows the subject without being asked', async () => {
    await loaded()
    expect(screen.getByText('admin.reviewers.emails.system.kind.partner_welcome')).toBeTruthy()
    // The subject is the line a person recognises an email by, so it is never behind a click.
    expect(screen.getByText('Your HalaTuju partner access')).toBeTruthy()
    expect(screen.getByText('Overdue verdict needs attention — HT-0000')).toBeTruthy()
  })

  it('shows the actual body on request — the whole point of listing them', async () => {
    await loaded()
    expect(screen.queryByText(/You have been added to HalaTuju/)).toBeNull()
    fireEvent.click(screen.getAllByText('admin.reviewers.emails.system.show')[0])
    expect(screen.getByText(/You have been added to HalaTuju/)).toBeTruthy()
  })

  it('says which one carries a password, and which reaches more than the reviewer', async () => {
    await loaded()
    expect(screen.getByText('admin.reviewers.emails.system.sensitive')).toBeTruthy()
    expect(screen.getByText('admin.reviewers.emails.system.widerAudience')).toBeTruthy()
  })

  it('offers NO switch and NO Edit on any of them', async () => {
    await loaded()
    // Two editable templates → exactly two toggles and two Edit links. If the seven ever grow
    // either, this count moves and the screen has started promising something it cannot do.
    expect(screen.getAllByRole('switch').length).toBe(2)
    expect(screen.getAllByText('admin.reviewers.emails.edit').length).toBe(2)
  })

  it('keeps the five usable when the seven cannot be loaded', async () => {
    // A reference list must never take down the controls somebody came here to operate.
    mockApi.getReviewerSystemEmails.mockRejectedValue(new Error('nope'))
    render(<ReviewerEmailsCard token="tok" t={t} />)
    await waitFor(() =>
      expect(screen.getByText('admin.reviewers.emails.kind.reviewer_assigned')).toBeTruthy())
    expect(screen.queryByText('admin.reviewers.emails.system.title')).toBeNull()
    expect(screen.queryByText('admin.reviewers.emails.loadError')).toBeNull()
  })
})
