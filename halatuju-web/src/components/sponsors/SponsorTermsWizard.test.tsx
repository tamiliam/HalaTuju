/**
 * @jest-environment jsdom
 *
 * The acceptance wizard. Four things have to hold, and none of them is "it renders":
 * a wrong answer never penalises, Accept is unreachable until every checkpoint is passed, the
 * signature is a TYPED NAME that is recorded rather than validated against the account, and a
 * version published mid-read sends them back to the start instead of recording an acceptance of
 * wording they never saw.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import SponsorTermsWizard from './SponsorTermsWizard'
import * as api from '@/lib/api'

jest.mock('next/link', () => ({
  __esModule: true,
  default: ({ href, children }: { href: string; children: React.ReactNode }) =>
    <a href={href}>{children}</a>,
}))
jest.mock('@/lib/i18n', () => ({
  useT: () => ({
    locale: 'en',
    t: (k: string, p?: Record<string, string>) =>
      (p ? `${k}:${Object.values(p).join(',')}` : k),
  }),
}))
jest.mock('@/lib/api')
const mockApi = api as jest.Mocked<typeof api>

const DOC = {
  version: '2026-sponsor-1', locale_used: 'en', title: 'Joining as a sponsor',
  intro: 'Short on purpose.',
  sections: [{ order: 1, heading: 'Your gift is a gift', body: 'Nothing is repaid.', has_quiz: true }],
}

const CHECKPOINT = {
  order: 1, tag: 'Your gift', plain: 'A donation, not a loan.',
  question: 'What comes back to you?',
  options: ['The money', 'Nothing — it was a gift', 'A share of earnings'],
  correct: 1, why: 'Nothing is repaid.',
}

const onAccepted = jest.fn()

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getSponsorTerms.mockResolvedValue({
    terms: DOC, signed_name: '', accepted_at: null,
    state: { terms_version: '2026-sponsor-1', terms_accepted: false, needs_terms: true, terms_basis: '' },
  })
  mockApi.getSponsorTermsQuiz.mockResolvedValue({
    version: '2026-sponsor-1', checkpoints: [CHECKPOINT],
  })
})

const openQuiz = async () => {
  render(<SponsorTermsWizard token="tok" accountName="Ve. Elanjelian" onAccepted={onAccepted} />)
  await waitFor(() => expect(screen.getByText('Joining as a sponsor')).toBeTruthy())
  fireEvent.click(screen.getByText('sponsorPortal.terms.startQuiz:1'))
}

describe('reading first', () => {
  it('shows the whole document before any question', async () => {
    render(<SponsorTermsWizard token="tok" accountName="A B" onAccepted={onAccepted} />)
    await waitFor(() => expect(screen.getByText('Joining as a sponsor')).toBeTruthy())
    expect(screen.getByText('1. Your gift is a gift')).toBeTruthy()
    expect(screen.getByText('Nothing is repaid.')).toBeTruthy()
  })

  it('links the privacy notice, because §12 names it and section bodies cannot hold links', async () => {
    render(<SponsorTermsWizard token="tok" accountName="A B" onAccepted={onAccepted} />)
    await waitFor(() => expect(screen.getByText('Joining as a sponsor')).toBeTruthy())
    expect(screen.getByText('sponsorAuth.privacyNotice').closest('a')?.getAttribute('href'))
      .toBe('/privacy')
  })
})

describe('the quiz', () => {
  it('a wrong answer explains itself and leaves the others live', async () => {
    await openQuiz()
    fireEvent.click(screen.getByText('The money'))
    expect(screen.getByText('sponsorPortal.terms.wrong')).toBeTruthy()
    expect((screen.getByText('Nothing — it was a gift') as HTMLButtonElement).disabled).toBe(false)
  })

  it('will not advance until the checkpoint is passed', async () => {
    await openQuiz()
    const next = screen.getByText('sponsorPortal.terms.toSign') as HTMLButtonElement
    expect(next.disabled).toBe(true)
    fireEvent.click(screen.getByText('The money'))          // wrong
    expect(next.disabled).toBe(true)
    fireEvent.click(screen.getByText('Nothing — it was a gift'))
    expect(next.disabled).toBe(false)
  })
})

describe('signing', () => {
  const reachSign = async () => {
    await openQuiz()
    fireEvent.click(screen.getByText('Nothing — it was a gift'))
    fireEvent.click(screen.getByText('sponsorPortal.terms.toSign'))
    await waitFor(() => expect(screen.getByText('sponsorPortal.terms.signTitle')).toBeTruthy())
  }

  it('shows their account name so they know what to type', async () => {
    await reachSign()
    expect(screen.getByText('Ve. Elanjelian')).toBeTruthy()
  })

  it('keeps Accept shut until something real is typed', async () => {
    await reachSign()
    const accept = screen.getByText('sponsorPortal.terms.accept') as HTMLButtonElement
    expect(accept.disabled).toBe(true)
    fireEvent.change(screen.getByLabelText('sponsorPortal.terms.typeName'),
      { target: { value: 'ab' } })
    expect(accept.disabled).toBe(true)
    fireEvent.change(screen.getByLabelText('sponsorPortal.terms.typeName'),
      { target: { value: 'Ve. Elanjelian' } })
    expect(accept.disabled).toBe(false)
  })

  it('records a DIFFERENT spelling rather than refusing it', async () => {
    // No IC to check against, and "Ve. Elanjelian" vs "Elanjelian Venugopal" is the same person.
    mockApi.acceptSponsorTerms.mockResolvedValue({} as api.SponsorAccount)
    await reachSign()
    fireEvent.change(screen.getByLabelText('sponsorPortal.terms.typeName'),
      { target: { value: 'Elanjelian Venugopal' } })
    fireEvent.click(screen.getByText('sponsorPortal.terms.accept'))

    await waitFor(() => expect(mockApi.acceptSponsorTerms).toHaveBeenCalledWith(
      { version: '2026-sponsor-1', signed_name: 'Elanjelian Venugopal', locale: 'en' },
      { token: 'tok' }))
    await waitFor(() => expect(onAccepted).toHaveBeenCalled())
  })

  it('a version published mid-read sends them back rather than recording it', async () => {
    mockApi.acceptSponsorTerms.mockRejectedValue({ status: 409 })
    await reachSign()
    fireEvent.change(screen.getByLabelText('sponsorPortal.terms.typeName'),
      { target: { value: 'Ve. Elanjelian' } })
    fireEvent.click(screen.getByText('sponsorPortal.terms.accept'))

    await waitFor(() => expect(screen.getByText('sponsorPortal.terms.versionChanged')).toBeTruthy())
    // Back to reading the (refetched) document, and nothing was reported as accepted.
    expect(screen.getByText('Joining as a sponsor')).toBeTruthy()
    expect(onAccepted).not.toHaveBeenCalled()
  })
})
