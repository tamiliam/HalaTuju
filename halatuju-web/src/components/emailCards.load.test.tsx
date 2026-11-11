/**
 * @jest-environment jsdom
 *
 * The four Emails cards read their list once per token (audit A3.15).
 *
 * Each card used to carry a lint suppression on its load effect because the effect words its error
 * with `t`, and `t` changes identity whenever the language or the catalogue changes. The fix reads
 * the latest `t` through a ref instead of listing it. What these pin, for every card:
 *   · a new `t` (a language switch) does NOT read the list again, and
 *   · a read that fails AFTER the switch is worded with the NEW `t`, not the one the effect began with.
 */
import { render, screen, waitFor } from '@testing-library/react'
import PartnerEmailsCard from '@/components/sources/PartnerEmailsCard'
import InvitationEmailsCard from '@/components/admin/InvitationEmailsCard'
import ReviewerEmailsCard from '@/components/reviewers/ReviewerEmailsCard'
import SponsorEmailsCard from '@/components/sponsors/SponsorEmailsCard'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

type T = (k: string) => string
const tOne: T = (k) => `one:${k}`
const tTwo: T = (k) => `two:${k}`

const CARDS: {
  name: string
  load: () => jest.Mock
  errorKey: string
  render: (t: T) => React.ReactElement
}[] = [
  { name: 'PartnerEmailsCard', load: () => mockApi.getPartnerEmails as unknown as jest.Mock,
    errorKey: 'admin.sources.emails.loadError',
    render: (t) => <PartnerEmailsCard token="tok" t={t} /> },
  { name: 'InvitationEmailsCard', load: () => mockApi.getInvitationEmails as unknown as jest.Mock,
    errorKey: 'admin.invitations.emails.loadError',
    render: (t) => <InvitationEmailsCard token="tok" t={t} /> },
  { name: 'ReviewerEmailsCard', load: () => mockApi.getReviewerEmails as unknown as jest.Mock,
    errorKey: 'admin.reviewers.emails.loadError',
    render: (t) => <ReviewerEmailsCard token="tok" t={t} /> },
  { name: 'SponsorEmailsCard', load: () => mockApi.getSponsorEmails as unknown as jest.Mock,
    errorKey: 'admin.sponsors.emails.loadError',
    render: (t) => <SponsorEmailsCard token="tok" t={t} /> },
]

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getReviewerSystemEmails.mockReturnValue(new Promise(() => {}))
})

describe.each(CARDS)('$name', (card) => {
  it('reads once, and a new `t` does not read again', async () => {
    const read = card.load()
    read.mockReturnValue(new Promise(() => {}))   // never settles: only the CALL count matters
    const { rerender } = render(card.render(tOne))
    expect(read).toHaveBeenCalledTimes(1)
    rerender(card.render(tTwo))
    rerender(card.render(tOne))
    expect(read).toHaveBeenCalledTimes(1)
  })

  it('words a failed read with the latest `t`', async () => {
    const read = card.load()
    let fail: (e: Error) => void = () => {}
    read.mockReturnValue(new Promise((_, reject) => { fail = reject }))
    const { rerender } = render(card.render(tOne))
    rerender(card.render(tTwo))
    fail(new Error('boom'))
    await waitFor(() => expect(screen.getByText(`two:${card.errorKey}`)).toBeTruthy())
  })
})
