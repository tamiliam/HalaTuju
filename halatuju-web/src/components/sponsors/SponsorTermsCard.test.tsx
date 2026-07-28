/**
 * @jest-environment jsdom
 *
 * The Terms panel. What matters here is not that it renders — it is that it cannot offer an action
 * the server would refuse: editing a published version, or a publish button to someone who is not
 * a super admin. A button that can only fail is worse than no button.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import SponsorTermsCard from './SponsorTermsCard'
import * as api from '@/lib/admin-api'

jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const t = (k: string, p?: Record<string, string | number>) =>
  (p ? `${k}:${Object.values(p).join(',')}` : k)

const SUMMARY = {
  id: 1, version: '2026-sponsor-1', status: 'draft' as const, title_en: 'Joining',
  section_count: 2, created_by_email: 'a@x.com', published_by_email: '',
  published_at: null, archived_at: null, created_at: '2026-07-28T00:00:00Z',
  updated_at: '2026-07-28T00:00:00Z',
}

const SECTION = {
  order: 1, heading_en: 'Your gift is a gift', heading_ms: '', heading_ta: '',
  body_en: 'Nothing is repaid.', body_ms: '', body_ta: '',
  is_quiz_candidate: true,
  quiz_en: { tag: 'Your gift', plain: 'p', question: 'q?', options: ['a', 'b', 'c'], correct: 1, why: 'w' },
  quiz_ms: {}, quiz_ta: {}, quiz_generated_model: '',
}

const detail = (over: Partial<api.SponsorTermsDetail> = {}): api.SponsorTermsDetail => ({
  ...SUMMARY,
  title_ms: '', title_ta: '', intro_en: 'Short on purpose.', intro_ms: '', intro_ta: '',
  languages_available: ['en'], sections: [SECTION], acceptance_count: 0,
  ...over,
} as api.SponsorTermsDetail)

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getSponsorTermsList.mockResolvedValue({
    versions: [SUMMARY], active_version: '', sponsor_count: 9,
  })
  mockApi.getSponsorTerms.mockResolvedValue(detail())
  mockApi.validateSponsorTerms.mockResolvedValue({ ok: true, errors: [], warnings: [] })
})

describe('honesty about what is live', () => {
  it('says plainly that nothing is published yet', async () => {
    render(<SponsorTermsCard token="tok" isSuper t={t} />)
    await waitFor(() => expect(screen.getByText('admin.sponsors.terms.noneActiveTitle')).toBeTruthy())
    // A sponsor is not being asked to accept anything, and the panel must not imply otherwise.
    expect(screen.getByText('admin.sponsors.terms.noneActiveBody')).toBeTruthy()
  })

  it('drops that banner once a version is active', async () => {
    mockApi.getSponsorTermsList.mockResolvedValue({
      versions: [{ ...SUMMARY, status: 'active' }], active_version: '2026-sponsor-1',
      sponsor_count: 9,
    })
    render(<SponsorTermsCard token="tok" isSuper t={t} />)
    await waitFor(() => expect(screen.getByText('2026-sponsor-1')).toBeTruthy())
    expect(screen.queryByText('admin.sponsors.terms.noneActiveTitle')).toBeNull()
  })
})

describe('a published version cannot be edited', () => {
  it('locks the fields and explains why', async () => {
    mockApi.getSponsorTerms.mockResolvedValue(detail({ status: 'active' }))
    render(<SponsorTermsCard token="tok" isSuper t={t} />)
    await waitFor(() => expect(screen.getByText('2026-sponsor-1')).toBeTruthy())
    fireEvent.click(screen.getByText('2026-sponsor-1'))

    await waitFor(() => expect(
      screen.getByText(/admin\.sponsors\.terms\.readOnly/)).toBeTruthy())
    const title = screen.getByPlaceholderText('admin.sponsors.terms.titlePh') as HTMLInputElement
    expect(title.disabled).toBe(true)
  })

  it('leaves a draft editable', async () => {
    render(<SponsorTermsCard token="tok" isSuper t={t} />)
    await waitFor(() => expect(screen.getByText('2026-sponsor-1')).toBeTruthy())
    fireEvent.click(screen.getByText('2026-sponsor-1'))

    await waitFor(() => expect(screen.getByPlaceholderText('admin.sponsors.terms.titlePh')).toBeTruthy())
    const title = screen.getByPlaceholderText('admin.sponsors.terms.titlePh') as HTMLInputElement
    expect(title.disabled).toBe(false)
  })
})

describe('publishing is a super admin decision', () => {
  it('offers the button to a super', async () => {
    render(<SponsorTermsCard token="tok" isSuper t={t} />)
    await waitFor(() => expect(screen.getByText('2026-sponsor-1')).toBeTruthy())
    fireEvent.click(screen.getByText('2026-sponsor-1'))
    await waitFor(() => expect(screen.getByText('admin.sponsors.terms.publish')).toBeTruthy())
  })

  it('tells an org_admin who publishes instead of showing a button that would 403', async () => {
    render(<SponsorTermsCard token="tok" isSuper={false} t={t} />)
    await waitFor(() => expect(screen.getByText('2026-sponsor-1')).toBeTruthy())
    fireEvent.click(screen.getByText('2026-sponsor-1'))
    await waitFor(() => expect(screen.getByText('admin.sponsors.terms.superOnly')).toBeTruthy())
    expect(screen.queryByText('admin.sponsors.terms.publish')).toBeNull()
  })
})

describe('the publish checklist', () => {
  it('renders the labels the SERVER supplied, not its own copy of the rules', async () => {
    mockApi.validateSponsorTerms.mockResolvedValue({
      ok: false,
      errors: [{ code: 'C2', label: 'Every section needs an English heading and body.' }],
      warnings: [{ code: 'W1', label: 'Malay or Tamil is incomplete.' }],
    })
    render(<SponsorTermsCard token="tok" isSuper t={t} />)
    await waitFor(() => expect(screen.getByText('2026-sponsor-1')).toBeTruthy())
    fireEvent.click(screen.getByText('2026-sponsor-1'))

    await waitFor(() => expect(
      screen.getByText(/Every section needs an English heading/)).toBeTruthy())
    expect(screen.getByText(/Malay or Tamil is incomplete/)).toBeTruthy()
    // Blocked, so no publish button even for a super.
    expect(screen.queryByText('admin.sponsors.terms.publish')).toBeTruthy()
  })
})

describe('errors', () => {
  it('names the refusal rather than showing a raw code', async () => {
    mockApi.createSponsorTerms.mockRejectedValue({ code: 'version_exists' })
    render(<SponsorTermsCard token="tok" isSuper t={t} />)
    await waitFor(() => expect(screen.getByText('2026-sponsor-1')).toBeTruthy())

    fireEvent.change(screen.getByPlaceholderText('admin.sponsors.terms.newVersionPh'),
      { target: { value: '2026-sponsor-1' } })
    fireEvent.click(screen.getByText('admin.sponsors.terms.create'))

    await waitFor(() => expect(
      screen.getByText('admin.sponsors.terms.error.version_exists')).toBeTruthy())
  })
})
