/**
 * @jest-environment jsdom
 *
 * The versions table. What matters: it reports the live state honestly (nothing published yet is a
 * thing a sponsor-facing document must say out loud), the fifth column shows who PUBLISHED rather
 * than the contracts screen's lawyer-vetting column, and the Word-upload path cannot be submitted
 * without a file.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import SponsorTermsCard from './SponsorTermsCard'
import * as api from '@/lib/admin-api'

const push = jest.fn()
jest.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))
jest.mock('@/lib/admin-api')
const mockApi = api as jest.Mocked<typeof api>

const t = (k: string, p?: Record<string, string>) =>
  (p ? `${k}:${Object.values(p).join(',')}` : k)

const V = (over: Partial<api.SponsorTermsSummary> = {}): api.SponsorTermsSummary => ({
  id: 1, version: '2026-sponsor-1', status: 'draft', title_en: 'Joining',
  languages_available: ['en'], section_count: 13, created_by_email: 'a@x.com',
  published_by_email: '', published_at: null, archived_at: null,
  created_at: '2026-07-28T00:00:00Z', updated_at: '2026-07-28T00:00:00Z',
  ...over,
})

beforeEach(() => {
  jest.clearAllMocks()
  mockApi.getSponsorTermsList.mockResolvedValue({
    versions: [V()], active_version: '', sponsor_count: 9,
  })
})

describe('the versions table', () => {
  it('shows the version, its status and how many languages it can be served in', async () => {
    render(<SponsorTermsCard token="tok" t={t} />)
    await waitFor(() => expect(screen.getByText('2026-sponsor-1')).toBeTruthy())
    expect(screen.getByText('admin.sponsors.terms.status.draft')).toBeTruthy()
    expect(screen.getByText('en')).toBeTruthy()
  })

  it('shows PUBLISHED BY, not the contracts screen\'s "vetted by"', async () => {
    // The sponsor terms get no lawyer pass (owner, 2026-07-28), so a Vetted-by column could only
    // ever show an em-dash. Who made a version binding is the fact worth carrying.
    render(<SponsorTermsCard token="tok" t={t} />)
    await waitFor(() => expect(screen.getByText('2026-sponsor-1')).toBeTruthy())
    expect(screen.getByText('admin.sponsors.terms.colPublishedBy')).toBeTruthy()
    expect(screen.queryByText(/colVetted/)).toBeNull()
  })

  it('dashes the publisher on a draft — nobody has published it', async () => {
    render(<SponsorTermsCard token="tok" t={t} />)
    await waitFor(() => expect(screen.getByText('2026-sponsor-1')).toBeTruthy())
    expect(screen.getByText('—')).toBeTruthy()
  })

  it('names the publisher once a version is active', async () => {
    mockApi.getSponsorTermsList.mockResolvedValue({
      versions: [V({ status: 'active', published_by_email: 'su@x.com', languages_available: ['en', 'ms'] })],
      active_version: '2026-sponsor-1', sponsor_count: 9,
    })
    render(<SponsorTermsCard token="tok" t={t} />)
    await waitFor(() => expect(screen.getByText('su@x.com')).toBeTruthy())
    expect(screen.getByText('en · ms')).toBeTruthy()
  })

  it('opens the editor when a row is clicked', async () => {
    render(<SponsorTermsCard token="tok" t={t} />)
    await waitFor(() => expect(screen.getByText('2026-sponsor-1')).toBeTruthy())
    fireEvent.click(screen.getByText('2026-sponsor-1'))
    expect(push).toHaveBeenCalledWith('/admin/sponsors/terms/1')
  })
})

describe('honesty about what is live', () => {
  it('says plainly that nothing is published yet', async () => {
    render(<SponsorTermsCard token="tok" t={t} />)
    await waitFor(() => expect(screen.getByText('admin.sponsors.terms.noneActiveTitle')).toBeTruthy())
  })

  it('drops that banner once a version is active', async () => {
    mockApi.getSponsorTermsList.mockResolvedValue({
      versions: [V({ status: 'active' })], active_version: '2026-sponsor-1', sponsor_count: 9,
    })
    render(<SponsorTermsCard token="tok" t={t} />)
    await waitFor(() => expect(screen.getByText('2026-sponsor-1')).toBeTruthy())
    expect(screen.queryByText('admin.sponsors.terms.noneActiveTitle')).toBeNull()
  })
})

describe('creating a version', () => {
  it('offers start-blank, upload and copy-from', async () => {
    render(<SponsorTermsCard token="tok" t={t} />)
    await waitFor(() => expect(screen.getByText('2026-sponsor-1')).toBeTruthy())
    fireEvent.click(screen.getByText('admin.sponsors.terms.newVersion'))

    expect(screen.getByText('admin.sponsors.terms.startBlank')).toBeTruthy()
    expect(screen.getByText('admin.sponsors.terms.uploadDoc')).toBeTruthy()
    expect(screen.getByText(/admin\.sponsors\.terms\.copyFrom/)).toBeTruthy()
  })

  it('refuses the upload path without a file rather than creating an empty version', async () => {
    render(<SponsorTermsCard token="tok" t={t} />)
    await waitFor(() => expect(screen.getByText('2026-sponsor-1')).toBeTruthy())
    fireEvent.click(screen.getByText('admin.sponsors.terms.newVersion'))

    fireEvent.change(screen.getByPlaceholderText('admin.sponsors.terms.newVersionPh'),
      { target: { value: '2026-sponsor-2' } })
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'upload' } })
    fireEvent.click(screen.getByText('admin.sponsors.terms.create'))

    await waitFor(() => expect(
      screen.getByText('admin.sponsors.terms.uploadNeedsFile')).toBeTruthy())
    expect(mockApi.createSponsorTerms).not.toHaveBeenCalled()
  })

  it('names the refusal rather than showing a raw code', async () => {
    mockApi.createSponsorTerms.mockRejectedValue({ code: 'version_exists' })
    render(<SponsorTermsCard token="tok" t={t} />)
    await waitFor(() => expect(screen.getByText('2026-sponsor-1')).toBeTruthy())
    fireEvent.click(screen.getByText('admin.sponsors.terms.newVersion'))

    fireEvent.change(screen.getByPlaceholderText('admin.sponsors.terms.newVersionPh'),
      { target: { value: '2026-sponsor-1' } })
    fireEvent.click(screen.getByText('admin.sponsors.terms.create'))

    await waitFor(() => expect(
      screen.getByText('admin.sponsors.terms.error.version_exists')).toBeTruthy())
  })

  it('a blank draft lands straight in the editor', async () => {
    mockApi.createSponsorTerms.mockResolvedValue({ id: 7 } as api.SponsorTermsDetail)
    render(<SponsorTermsCard token="tok" t={t} />)
    await waitFor(() => expect(screen.getByText('2026-sponsor-1')).toBeTruthy())
    fireEvent.click(screen.getByText('admin.sponsors.terms.newVersion'))

    fireEvent.change(screen.getByPlaceholderText('admin.sponsors.terms.newVersionPh'),
      { target: { value: '2026-sponsor-2' } })
    fireEvent.click(screen.getByText('admin.sponsors.terms.create'))

    await waitFor(() => expect(push).toHaveBeenCalledWith('/admin/sponsors/terms/7'))
    expect(mockApi.importSponsorTermsDocx).not.toHaveBeenCalled()
  })
})
